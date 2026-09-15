import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core import security
from app.core.exceptions import (
    AccountDisabledError,
    AuthenticationError,
    EmailAlreadyRegisteredError,
    NotAuthenticatedError,
    OAuthAccountConflictError,
    OAuthEmailMissingError,
)
from app.infrastructure.persistence import mongodb_user_repository

logger = logging.getLogger(__name__)

class MongoDBAuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def signup(self, full_name: str, email: str, password: str) -> dict:
        existing = await mongodb_user_repository.get_user_by_email(self._db, email)
        if existing:
            raise EmailAlreadyRegisteredError()

        user = await mongodb_user_repository.create_user(
            self._db,
            full_name=full_name,
            email=email,
            password=password,
            auth_provider="local"
        )
        return user

    async def login(self, email: str, password: str) -> Tuple[dict, str, str]:
        user = await mongodb_user_repository.get_user_by_email(self._db, email)
        if not user or not user.get("password_hash"):
            raise AuthenticationError("Invalid email or password.")

        if not security.verify_password(password, user["password_hash"]):
            raise AuthenticationError("Invalid email or password.")

        if not user.get("is_active", True):
            raise AccountDisabledError()

        access_token, refresh_token = await self.create_login_session(user)
        return user, access_token, refresh_token

    async def create_login_session(self, user: dict) -> Tuple[str, str]:
        """Consolidated session creation for MongoDB users."""
        user_id = user["_id"]
        await mongodb_user_repository.update_last_login(self._db, user_id)
        
        access_token = security.create_access_token(user_id)
        refresh_token = security.create_refresh_token(user_id)
        
        # Store refresh token hash
        await self._store_refresh_token(user_id, refresh_token)
        
        return access_token, refresh_token

    async def _store_refresh_token(self, user_id: str, token: str):
        token_hash = security.hash_refresh_token(token)
        # In a real app, we'd extract expiry from JWT, but for now we'll use a default
        from datetime import timedelta
        from app.core.config import settings
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        
        await self._db.auth_sessions.insert_one({
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc)
        })

    async def refresh_tokens(self, refresh_token: str) -> Tuple[str, str]:
        try:
            user_id = security.decode_token(refresh_token, "refresh")
        except security.InvalidTokenError as exc:
            raise NotAuthenticatedError(str(exc)) from exc

        token_hash = security.hash_refresh_token(refresh_token)
        session = await self._db.auth_sessions.find_one({"token_hash": token_hash, "user_id": user_id})
        
        if not session:
            # Token might have been reused or revoked.
            # Security best practice: revoke all sessions for this user?
            raise NotAuthenticatedError("Invalid session.")

        # Rotate: delete old session
        await self._db.auth_sessions.delete_one({"_id": session["_id"]})
        
        user = await mongodb_user_repository.get_user_by_id(self._db, user_id)
        if not user or not user.get("is_active", True):
             raise NotAuthenticatedError("User not found or inactive.")

        new_access = security.create_access_token(user_id)
        new_refresh = security.create_refresh_token(user_id)
        await self._store_refresh_token(user_id, new_refresh)
        
        return new_access, new_refresh

    async def logout(self, refresh_token: str):
        token_hash = security.hash_refresh_token(refresh_token)
        await self._db.auth_sessions.delete_one({"token_hash": token_hash})

    async def get_user_from_access_token(self, token: str) -> dict:
        try:
            user_id = security.decode_token(token, "access")
            user = await mongodb_user_repository.get_user_by_id(self._db, user_id)
            if not user or not user.get("is_active", True):
                raise NotAuthenticatedError("User not found or inactive.")
            return user
        except security.InvalidTokenError as exc:
            raise NotAuthenticatedError(str(exc)) from exc

    async def authenticate_with_oauth(
        self,
        *,
        provider: str,
        provider_user_id: str,
        email: str | None,
        email_verified: bool,
        full_name: str | None,
        profile_image: str | None,
    ) -> dict:
        """Find-or-create the local user for a verified provider identity (MongoDB)."""
        existing_account = await mongodb_user_repository.get_oauth_account(
            self._db, provider=provider, provider_user_id=provider_user_id
        )
        if existing_account:
            user = await mongodb_user_repository.get_user_by_id(self._db, existing_account["user_id"])
            if not user or not user.get("is_active", True):
                raise AccountDisabledError()
            return user

        normalized_email = email.strip().lower() if email else None
        if not normalized_email:
            raise OAuthEmailMissingError()

        existing_user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if existing_user:
            if not email_verified:
                raise OAuthAccountConflictError()
            if not existing_user.get("is_active", True):
                raise AccountDisabledError()
            
            await mongodb_user_repository.create_oauth_account(
                self._db,
                user_id=existing_user["_id"],
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=normalized_email,
            )
            # Add to auth_providers if not already there
            if provider not in existing_user.get("auth_providers", []):
                providers = existing_user.get("auth_providers", []) + [provider]
                await mongodb_user_repository.update_user(self._db, existing_user["_id"], {"auth_providers": providers})
            
            return existing_user

        display_name = (full_name or normalized_email.split("@", 1)[0]).strip() or normalized_email
        user = await mongodb_user_repository.create_oauth_user(
            self._db,
            full_name=display_name,
            email=normalized_email,
            auth_provider=provider,
            provider_user_id=provider_user_id,
            profile_image=profile_image,
            is_email_verified=email_verified,
        )
        
        await mongodb_user_repository.create_oauth_account(
            self._db,
            user_id=user["_id"],
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=normalized_email,
        )
        return user
