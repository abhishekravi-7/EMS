import logging
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import user_id_ctx
from app.infrastructure.persistence import user_repository
from app.infrastructure.persistence.models import User

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
def init_firebase():
    if not firebase_admin._apps:
        try:
            # Try to initialize with service account if credentials are provided
            if settings.firebase_project_id and settings.firebase_private_key and settings.firebase_client_email:
                # The SDK requires the "type" field to be explicitly set
                cert_dict = {
                    "type": "service_account",
                    "project_id": settings.firebase_project_id,
                    "private_key": settings.firebase_private_key.replace('\\n', '\n'),
                    "client_email": settings.firebase_client_email,
                }
                cred = credentials.Certificate(cert_dict)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin initialized with service account.")
            else:
                # Fallback to default credentials
                firebase_admin.initialize_app()
                logger.info("Firebase Admin initialized with default credentials.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin: {e}")
            if settings.firebase_auth_enabled:
                raise RuntimeError("Firebase Auth is enabled but Admin SDK failed to initialize.")

# Helper to verify token and return local user
async def verify_firebase_token(
    db: Session,
    token: str
) -> User:
    try:
        # Verify the ID token
        decoded_token = firebase_auth.verify_id_token(token)
        firebase_uid = decoded_token['uid']
        email = decoded_token.get('email')
        name = decoded_token.get('name', email.split('@')[0] if email else 'User')

        if not email:
            raise HTTPException(status_code=401, detail="Firebase token missing email.")

        # Find or create local user
        user = user_repository.get_user_by_email(db, email)
        if user is None:
            # First time this Firebase user is seen — create a local shadow record
            user = user_repository.create_user(
                db,
                full_name=name,
                email=email,
                password_hash=None,
                auth_provider="firebase",
                provider_user_id=firebase_uid
            )
            logger.info(f"Created new local shadow record for Firebase user: {email}")

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled.")

        user_id_ctx.set(user.id)
        return user
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.")

# Reusable security scheme
auth_scheme = HTTPBearer()

async def get_firebase_user(
    db: Session,
    auth_creds: HTTPAuthorizationCredentials = Security(auth_scheme)
) -> User:
    return await verify_firebase_token(db, auth_creds.credentials)
