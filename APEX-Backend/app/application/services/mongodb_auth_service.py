import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import pymongo
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    AccountDisabledError,
    AuthError,
    AuthenticationError,
    EmailAlreadyRegisteredError,
    EmailDeliveryFailedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidVerificationCodeError,
    InvalidVerificationTokenError,
    NotAuthenticatedError,
    OAuthAccountConflictError,
    OAuthEmailMissingError,
    TooManyVerificationAttemptsError,
    VerificationCodeExpiredError,
)
from app.infrastructure.email.email_service import (
    EmailDeliveryError,
    EmailNotConfiguredError,
    send_password_reset_email,
    send_verification_email,
)
from app.infrastructure.oauth.google_client import verify_id_token as verify_google_id_token
from app.infrastructure.persistence import mongodb_user_repository

logger = logging.getLogger(__name__)

class MongoDBAuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def signup(self, full_name: str, email: str, password: str, frontend_url: Optional[str] = None) -> dict:
        normalized_email = email.strip().lower() if email else ""
        existing = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if existing:
            raise EmailAlreadyRegisteredError()

        # Hash password securely using Argon2id
        password_hash = security.hash_password(password)

        # Generate cryptographically secure 6-digit verification code
        verification_code = f"{secrets.randbelow(1000000):06d}"
        code_hash = hashlib.sha256(verification_code.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        clean_name = (full_name or normalized_email.split("@")[0]).strip() or "User"

        # Create or update temporary pending signup record (do NOT insert user in `users` collection yet)
        await mongodb_user_repository.create_or_update_pending_signup(
            self._db,
            email=normalized_email,
            password_hash=password_hash,
            full_name=clean_name,
            verification_code_hash=code_hash,
            expires_at=expires_at,
        )

        try:
            await send_verification_email(
                to_email=normalized_email,
                user_name=clean_name,
                verification_code=verification_code,
            )
        except (EmailDeliveryError, EmailNotConfiguredError) as exc:
            logger.error("Verification email failed to deliver for email=%s: %s", normalized_email, exc)
            await mongodb_user_repository.delete_pending_signup(self._db, normalized_email)
            raise EmailDeliveryFailedError(
                "Unable to send the verification email. Please check configuration or try again later."
            ) from exc

        return {
            "email": normalized_email,
            "message": "Verification code sent to your email.",
        }

    def _is_user_active(self, user: dict | None) -> bool:
        """Check if user account is active. Missing fields gracefully default to active=True."""
        if not user or not isinstance(user, dict):
            return False
        # Explicit boolean false
        if user.get("is_active") is False:
            return False
        # Explicit boolean true on disabled / is_disabled
        if user.get("disabled") is True or user.get("is_disabled") is True:
            return False
        # Status field string values
        status = str(user.get("status", "")).strip().lower()
        if status in ("disabled", "inactive", "suspended", "banned", "deactivated"):
            return False
        return True

    async def login(self, email: str, password: str) -> Tuple[dict, str, str]:
        normalized_email = email.strip().lower() if email else ""
        if not normalized_email:
            raise InvalidCredentialsError()

        user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if not user or not user.get("password_hash"):
            raise InvalidCredentialsError()

        if not security.verify_password(password, user["password_hash"]):
            raise InvalidCredentialsError()

        # Enforce email verification for password/local users
        if not user.get("is_email_verified", False):
            raise EmailNotVerifiedError()

        if not self._is_user_active(user):
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

    async def _store_refresh_token(self, user_id: Any, token: str):
        token_hash = security.hash_refresh_token(token)
        from datetime import timedelta
        from app.core.config import settings
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        target_id = int(user_id) if (isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit())) else user_id

        await self._db.auth_sessions.insert_one({
            "user_id": target_id,
            "token_hash": token_hash,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc)
        })

    async def refresh_tokens(self, refresh_token: str) -> Tuple[str, str]:
        try:
            raw_user_id = security.decode_token(refresh_token, "refresh")
        except security.InvalidTokenError as exc:
            raise NotAuthenticatedError(str(exc)) from exc

        target_id = int(raw_user_id) if raw_user_id.isdigit() else raw_user_id
        token_hash = security.hash_refresh_token(refresh_token)
        session = await self._db.auth_sessions.find_one({
            "token_hash": token_hash,
            "$or": [{"user_id": target_id}, {"user_id": str(target_id)}]
        })
        
        if not session:
            # Token might have been reused or revoked.
            raise NotAuthenticatedError("Invalid session.")

        # Rotate: delete old session
        await self._db.auth_sessions.delete_one({"_id": session["_id"]})
        
        user = await mongodb_user_repository.get_user_by_id(self._db, target_id)
        if not user or not self._is_user_active(user):
             raise NotAuthenticatedError("User not found or inactive.")

        new_access = security.create_access_token(user["_id"])
        new_refresh = security.create_refresh_token(user["_id"])
        await self._store_refresh_token(user["_id"], new_refresh)
        
        return new_access, new_refresh

    async def logout(self, refresh_token: str):
        token_hash = security.hash_refresh_token(refresh_token)
        await self._db.auth_sessions.delete_one({"token_hash": token_hash})

    async def get_user_from_access_token(self, token: str) -> dict:
        try:
            user_id = security.decode_token(token, "access")
            user = await mongodb_user_repository.get_user_by_id(self._db, user_id)
            if not user or not self._is_user_active(user):
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
        """Find-or-create or safely link the local user for a verified provider identity (MongoDB)."""
        normalized_email = email.strip().lower() if email else None

        # 1. First check oauth_accounts for existing provider mapping
        existing_account = await mongodb_user_repository.get_oauth_account(
            self._db, provider=provider, provider_user_id=provider_user_id
        )
        if existing_account and existing_account.get("user_id") is not None:
            raw_uid = existing_account["user_id"]
            target_user = await mongodb_user_repository.get_user_by_id(self._db, raw_uid)
            if target_user:
                if not self._is_user_active(target_user):
                    logger.warning("OAuth login rejected: account is disabled for user_id=%s", target_user.get("_id"))
                    raise AccountDisabledError()

                # If OAuth verified the email, ensure user is marked verified
                if email_verified and not target_user.get("is_email_verified", False):
                    await mongodb_user_repository.verify_user_email(self._db, target_user["_id"])
                    target_user["is_email_verified"] = True

                # Ensure provider is in auth_providers list
                if provider not in target_user.get("auth_providers", []):
                    updates = {"auth_providers": target_user.get("auth_providers", []) + [provider]}
                    await mongodb_user_repository.update_user(self._db, target_user["_id"], updates)
                    target_user["auth_providers"] = updates["auth_providers"]

                return target_user
            else:
                logger.info(
                    "Found oauth_account with user_id=%s but user not found in users collection; resolving by verified email.",
                    raw_uid,
                )

        # 2. If not found by direct oauth_accounts ID mapping, resolve via verified email
        if not normalized_email:
            raise OAuthEmailMissingError()

        if not email_verified:
            raise OAuthAccountConflictError()

        existing_user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if existing_user:
            if not self._is_user_active(existing_user):
                logger.warning("OAuth login rejected: account is disabled for user_id=%s (email=%s)", existing_user.get("_id"), normalized_email)
                raise AccountDisabledError()

            # Safely sync / upsert oauth_accounts record
            await self._db.oauth_accounts.delete_many({
                "provider": provider,
                "provider_user_id": provider_user_id,
            })
            await mongodb_user_repository.create_oauth_account(
                self._db,
                user_id=existing_user["_id"],
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=normalized_email,
            )

            # Update user fields: mark is_email_verified=True and record provider
            updates: dict[str, Any] = {}
            if not existing_user.get("is_email_verified", False):
                updates["is_email_verified"] = True
            if provider not in existing_user.get("auth_providers", []):
                updates["auth_providers"] = existing_user.get("auth_providers", []) + [provider]
            if profile_image and not existing_user.get("profile_image"):
                updates["profile_image"] = profile_image
            if updates:
                await mongodb_user_repository.update_user(self._db, existing_user["_id"], updates)
                existing_user.update(updates)

            return existing_user

        # 3. Create new user for verified OAuth identity
        display_name = (full_name or normalized_email.split("@", 1)[0]).strip() or normalized_email
        user = await mongodb_user_repository.create_oauth_user(
            self._db,
            full_name=display_name,
            email=normalized_email,
            auth_provider=provider,
            provider_user_id=provider_user_id,
            profile_image=profile_image,
            is_email_verified=True,
        )

        await self._db.oauth_accounts.delete_many({
            "provider": provider,
            "provider_user_id": provider_user_id,
        })
        await mongodb_user_repository.create_oauth_account(
            self._db,
            user_id=user["_id"],
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=normalized_email,
        )
        return user


    async def forgot_password(self, email: str, frontend_url: str):
        normalized_email = email.strip().lower()
        user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if not user:
            # Silently return to prevent email enumeration
            return

        if not user.get("is_active", True):
            return

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        
        await mongodb_user_repository.create_password_reset_token(
            self._db,
            user_id=user["_id"],
            token=token,
            expires_at=expires_at,
            email=user["email"]
        )

        reset_link = f"{frontend_url.rstrip('/')}/reset-password?token={token}"
        
        # Here we would send the email.
        # We will integrate an email service to send the specific template.
        from app.infrastructure.email.email_service import send_password_reset_email
        await send_password_reset_email(
            to_email=user["email"],
            user_name=user.get("full_name", "User"),
            reset_link=reset_link
        )

    async def reset_password(self, token: str, new_password: str):
        token_doc = await mongodb_user_repository.get_password_reset_token(self._db, token)
        if not token_doc:
            raise AuthenticationError("Invalid or expired reset token.")

        if token_doc["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            await mongodb_user_repository.delete_password_reset_token(self._db, token)
            raise AuthenticationError("Invalid or expired reset token.")

        user_id = token_doc["user_id"]
        password_hash = security.hash_password(new_password)
        
        await mongodb_user_repository.update_user_password(self._db, user_id, password_hash)
        await mongodb_user_repository.delete_password_reset_token(self._db, token)

    async def verify_email_code(self, email: str, code: str) -> dict:
        """Validate 6-digit email verification code from pending_signups, create user in users collection, and clean up."""
        normalized_email = email.strip().lower() if email else ""
        clean_code = str(code).strip() if code else ""

        if not normalized_email or len(clean_code) != 6 or not clean_code.isdigit():
            raise InvalidVerificationCodeError("Invalid verification code.")

        # 1. Check if user already exists and is already verified
        existing_user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if existing_user and existing_user.get("is_email_verified", False):
            return existing_user

        # 2. Look up pending signup record
        pending = await mongodb_user_repository.get_pending_signup(self._db, normalized_email)

        # Legacy fallback if unverified user exists in `users` but not in `pending_signups`
        if not pending and existing_user and not existing_user.get("is_email_verified", False):
            record = await mongodb_user_repository.get_latest_email_verification(self._db, normalized_email)
            if record:
                if record.get("used_at") is not None:
                    raise InvalidVerificationCodeError("Verification code has expired or has already been used. Please request a new code.")
                expires_at = record["expires_at"]
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < datetime.now(timezone.utc):
                    raise VerificationCodeExpiredError("Verification code has expired. Please request a new code.")
                attempts = int(record.get("attempts", 0))
                if attempts >= 5:
                    await mongodb_user_repository.mark_email_verification_used(self._db, record["_id"])
                    raise TooManyVerificationAttemptsError("Too many incorrect attempts. Please request a new code.")
                submitted_hash = hashlib.sha256(clean_code.encode()).hexdigest()
                stored_hash = record.get("code_hash") or record.get("token_hash", "")
                if not secrets.compare_digest(submitted_hash, stored_hash):
                    updated_attempts = await mongodb_user_repository.increment_verification_attempts(self._db, record["_id"])
                    if updated_attempts >= 5:
                        await mongodb_user_repository.mark_email_verification_used(self._db, record["_id"])
                        raise TooManyVerificationAttemptsError("Too many incorrect attempts. Please request a new code.")
                    raise InvalidVerificationCodeError("Invalid verification code.")
                await mongodb_user_repository.mark_email_verification_used(self._db, record["_id"])
                await mongodb_user_repository.verify_user_email(self._db, existing_user["_id"])
                existing_user["is_email_verified"] = True
                return existing_user

        if not pending:
            raise InvalidVerificationCodeError("No pending registration found or verification code has expired. Please sign up again.")

        expires_at = pending["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise VerificationCodeExpiredError("Verification code has expired. Please request a new code.")

        attempts = int(pending.get("attempts", 0))
        if attempts >= 5:
            await mongodb_user_repository.delete_pending_signup(self._db, normalized_email)
            raise TooManyVerificationAttemptsError("Too many incorrect attempts. Please request a new code.")

        submitted_hash = hashlib.sha256(clean_code.encode()).hexdigest()
        stored_hash = pending.get("verification_code_hash", "")

        if not secrets.compare_digest(submitted_hash, stored_hash):
            updated_attempts = await mongodb_user_repository.increment_pending_signup_attempts(self._db, normalized_email)
            if updated_attempts >= 5:
                await mongodb_user_repository.delete_pending_signup(self._db, normalized_email)
                raise TooManyVerificationAttemptsError("Too many incorrect attempts. Please request a new code.")
            raise InvalidVerificationCodeError("Invalid verification code.")

        # Successfully verified! Create actual user in `users` collection
        if not existing_user:
            try:
                user = await mongodb_user_repository.create_user(
                    self._db,
                    full_name=pending.get("full_name", "User"),
                    email=normalized_email,
                    password_hash=pending["password_hash"],
                    auth_provider="local",
                    is_email_verified=True,
                )
            except Exception as exc:
                existing_user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
                if existing_user:
                    user = existing_user
                else:
                    raise exc
        else:
            user = existing_user
            if not user.get("is_email_verified", False):
                await mongodb_user_repository.verify_user_email(self._db, user["_id"])
                user["is_email_verified"] = True

        # Clean up temporary pending signup record
        await mongodb_user_repository.delete_pending_signup(self._db, normalized_email)

        return user

    async def resend_verification_code(self, email: str) -> None:
        """Resend fresh 6-digit verification code with 60-second cooldown rate limit."""
        normalized_email = email.strip().lower() if email else ""
        if not normalized_email:
            return

        # Check if already registered and verified
        user = await mongodb_user_repository.get_user_by_email(self._db, normalized_email)
        if user and user.get("is_email_verified", False):
            return

        # Look up pending signup record
        pending = await mongodb_user_repository.get_pending_signup(self._db, normalized_email)
        latest_record = None
        if not pending and user:
            latest_record = await mongodb_user_repository.get_latest_email_verification(self._db, normalized_email)

        if not pending and not user:
            # Silently return to prevent user enumeration
            return

        # Rate limiting: 60-second cooldown between resend requests for the same email
        updated_at = None
        if pending:
            updated_at = pending.get("updated_at") or pending.get("created_at")
        elif latest_record:
            updated_at = latest_record.get("created_at")

        if updated_at:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - updated_at).total_seconds() < 60:
                logger.info("Resend verification throttled for email=%s (cooldown active).", normalized_email)
                raise AuthError("Please wait at least 60 seconds before requesting a new verification code.")

        # Generate fresh 6-digit code (10 min expiry)
        verification_code = f"{secrets.randbelow(1000000):06d}"
        code_hash = hashlib.sha256(verification_code.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        if pending:
            await mongodb_user_repository.update_pending_signup_code(
                self._db,
                email=normalized_email,
                verification_code_hash=code_hash,
                expires_at=expires_at,
            )
            full_name = pending.get("full_name", "User")
        else:
            await mongodb_user_repository.invalidate_pending_email_verifications(self._db, normalized_email)
            await mongodb_user_repository.create_email_verification_code(
                self._db,
                user_id=user["_id"],
                email=user["email"],
                code_hash=code_hash,
                expires_at=expires_at,
            )
            full_name = user.get("full_name", "User")

        try:
            await send_verification_email(
                to_email=normalized_email,
                user_name=full_name,
                verification_code=verification_code,
            )
        except (EmailDeliveryError, EmailNotConfiguredError) as exc:
            logger.error("Failed to resend verification email for email=%s: %s", normalized_email, exc)
            raise EmailDeliveryFailedError(
                "Unable to send the verification email. Please try again later."
            ) from exc

    async def verify_email(self, token: str) -> dict:
        """Legacy token verification handler."""
        if not token or not token.strip():
            raise InvalidVerificationTokenError("Verification token is required.")

        token_hash = hashlib.sha256(token.strip().encode()).hexdigest()
        token_doc = await mongodb_user_repository.get_email_verification_token(self._db, token_hash)
        if not token_doc:
            raise InvalidVerificationTokenError("This verification link is invalid or has expired.")

        if token_doc.get("used_at") is not None:
            raise InvalidVerificationTokenError("This verification link has already been used.")

        expires_at = token_doc["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise InvalidVerificationTokenError("This verification link has expired. Please request a new one.")

        await mongodb_user_repository.mark_email_verification_token_used(self._db, token_hash)
        user_id = token_doc["user_id"]
        await mongodb_user_repository.verify_user_email(self._db, user_id)

        user = await mongodb_user_repository.get_user_by_id(self._db, user_id)
        if not user:
            raise InvalidVerificationTokenError("User associated with token not found.")

        return user

    async def resend_verification_email(self, email: str, frontend_url: Optional[str] = None) -> None:
        """Delegate resend_verification_email to resend_verification_code."""
        await self.resend_verification_code(email)

    async def authenticate_with_google_id_token(self, credential: str) -> Tuple[dict, str, str]:
        """Verify Google Identity Services ID token and log user in."""
        claims = await verify_google_id_token(credential)
        provider_user_id = claims["sub"]
        email = claims.get("email")
        email_verified = claims.get("email_verified", True)
        full_name = claims.get("name")
        picture = claims.get("picture")

        user = await self.authenticate_with_oauth(
            provider="google",
            provider_user_id=provider_user_id,
            email=email,
            email_verified=email_verified,
            full_name=full_name,
            profile_image=picture,
        )

        access_token, refresh_token = await self.create_login_session(user)
        return user, access_token, refresh_token

