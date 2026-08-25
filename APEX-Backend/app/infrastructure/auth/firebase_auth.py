from datetime import datetime, timezone
from typing import Optional, Dict
import logging
import jwt
from jwt import PyJWKClient

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth, credentials
except ImportError:
    firebase_admin = None
    firebase_auth = None
    credentials = None

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import user_id_ctx
from app.infrastructure.persistence import user_repository
from app.infrastructure.persistence.models import User

logger = logging.getLogger(__name__)

_GOOGLE_JWKS_URL = "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_GOOGLE_JWKS_URL, cache_keys=True)
    return _jwks_client


def is_firebase_token(token: str) -> bool:
    """Check if the provided JWT token is a Firebase ID token (RS256)."""
    if not token or not isinstance(token, str):
        return False
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "RS256":
            return True
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        iss = unverified_payload.get("iss", "")
        if "securetoken.google.com" in iss:
            return True
    except Exception:
        pass
    return False


# Initialize Firebase Admin SDK
def init_firebase() -> None:
    if not settings.firebase_auth_enabled:
        return

    if firebase_admin is None or credentials is None:
        error_msg = (
            "Firebase Auth is enabled (FIREBASE_AUTH_ENABLED=true), but 'firebase-admin' "
            "package is not installed. Install it with: pip install firebase-admin"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    if not getattr(firebase_admin, "_apps", None):
        try:
            # Try to initialize with service account if credentials are provided
            if settings.firebase_project_id and settings.firebase_private_key and settings.firebase_client_email:
                cred = credentials.Certificate({
                    "type": "service_account",
                    "project_id": settings.firebase_project_id,
                    "private_key": settings.firebase_private_key.replace('\\n', '\n'),
                    "client_email": settings.firebase_client_email,
                })
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin initialized with service account.")
            else:
                # Fallback to default credentials (e.g. from GOOGLE_APPLICATION_CREDENTIALS env var)
                firebase_admin.initialize_app()
                logger.info("Firebase Admin initialized with default credentials.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin: {e}")
            if settings.firebase_auth_enabled:
                raise RuntimeError(f"Firebase Auth is enabled but Admin SDK failed to initialize: {e}") from e


def _verify_and_decode_firebase_token(token: str) -> Dict:
    """Verify Firebase ID token via Admin SDK or Google JWKS public keys."""
    # 1. Admin SDK if initialized
    if firebase_auth is not None and firebase_admin is not None and getattr(firebase_admin, "_apps", None):
        try:
            return firebase_auth.verify_id_token(token)
        except Exception as admin_err:
            logger.debug("Firebase Admin SDK verification failed, attempting JWKS fallback: %s", admin_err)

    # 2. Cryptographic verification with Google's JWKS public keys via PyJWT
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
        project_id = (settings.firebase_project_id or "").strip()
        options = {"verify_aud": bool(project_id)}
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=project_id if project_id else None,
            options=options,
        )
    except Exception as jwks_err:
        logger.error(f"Firebase token cryptographic verification failed: {jwks_err}")
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.") from jwks_err


# Helper to verify token and return local user
async def verify_firebase_token(
    db: Optional[Session],
    token: str
) -> User:
    try:
        # Verify the ID token
        decoded_token = _verify_and_decode_firebase_token(token)
        firebase_uid = decoded_token.get("uid") or decoded_token.get("sub") or decoded_token.get("user_id")
        email = decoded_token.get("email")
        name = decoded_token.get("name", email.split("@")[0] if email else "User")

        if not email:
            raise HTTPException(status_code=401, detail="Firebase token missing email.")

        if db is None or not settings.database_enabled:
            fake_user = User()
            fake_user.id = 0
            fake_user.full_name = name
            fake_user.email = email
            fake_user.role = "USER"
            fake_user.is_active = True
            fake_user.is_email_verified = True
            fake_user.created_at = datetime.now(timezone.utc)
            fake_user.last_login_at = datetime.now(timezone.utc)
            user_id_ctx.set(fake_user.id)
            return fake_user

        # Find or create local user in PostgreSQL
        user = user_repository.get_user_by_email(db, email)
        if user is None:
            # First time this Firebase user is seen — create a local shadow record
            user = user_repository.create_user(
                db,
                full_name=name,
                email=email,
                password_hash=None, # Firebase handles passwords
                auth_provider="firebase",
                provider_user_id=firebase_uid
            )
            logger.info(f"Created new local shadow record for Firebase user: {email}")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled.")

        user_id_ctx.set(user.id)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

# Reusable security scheme
auth_scheme = HTTPBearer()

async def get_firebase_user(
    db: Optional[Session],
    auth_creds: HTTPAuthorizationCredentials = Security(auth_scheme)
) -> User:
    return await verify_firebase_token(db, auth_creds.credentials)
