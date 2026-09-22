"""Authentication endpoints: signup, login, me, refresh, logout.

Mounted at ``/api/auth/*`` — unversioned, like the other utility routers
(github, local-project, ...), see ``app/api/utility_router.py``. Thin
controller: request validation lives in ``app/schemas/auth_schema.py``,
business logic lives in ``app/application/services/mongodb_auth_service.py``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.deps import User, get_current_user
from app.application.services.mongodb_auth_service import MongoDBAuthService
from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthError
from app.infrastructure.oauth import github_client, google_client
from app.infrastructure.persistence.mongodb import get_mongodb
from app.schemas.auth_schema import (
    AuthResponse,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    MessageResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignupRequest,
    SignupResponse,
    UserResponse,
    VerifyEmailCodeRequest,
    VerifyEmailRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_TOKEN_COOKIE = "access_token"  
REFRESH_TOKEN_COOKIE = "refresh_token" 
GOOGLE_CODE_VERIFIER_COOKIE = "google_code_verifier" 

# Maps an internal AuthError.status to the public, stable code appended as
# `?oauth_error=<code>` on the sign-in redirect — never the exception's own
# (safe, but internal-vocabulary) message.
_OAUTH_ERROR_CODES: dict[str, str] = {
    "OAUTH_NOT_CONFIGURED": "provider_not_configured",
    "OAUTH_CANCELLED": "access_denied",
    "OAUTH_INVALID_STATE": "invalid_state",
    "OAUTH_PROVIDER_ERROR": "provider_error",
    "OAUTH_EMAIL_MISSING": "missing_email",
    "OAUTH_ACCOUNT_CONFLICT": "account_conflict",
    "ACCOUNT_DISABLED": "account_disabled",
}



def _set_auth_cookies(response: JSONResponse | RedirectResponse, access_token: str, refresh_token: str) -> None:
    """Set both JWTs as HttpOnly cookies."""
    common_cookie_options = {
        "httponly": True,
        "secure": settings.is_production,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **common_cookie_options,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        **common_cookie_options,
    )


def _clear_auth_cookies(response: JSONResponse) -> None:
    """Delete both cookies."""
    for cookie_name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE):
        response.delete_cookie(
            cookie_name,
            path="/",
            samesite=settings.cookie_samesite,
            secure=settings.is_production,
            httponly=True,
        )


def _auth_error_response(exc: AuthError) -> JSONResponse:
    logger.info("Auth request rejected (%s).", exc.status)
    return JSONResponse(status_code=exc.http_status, content={"detail": exc.message})


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=201,
    summary="Create a new account (email + password).",
)
async def signup(payload: SignupRequest) -> JSONResponse:
    """Stores pending signup in MongoDB, sends verification code, and returns status."""
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        clean_name = (payload.full_name or payload.email.split("@")[0]).strip() or "User"
        result = await service.signup(
            full_name=clean_name,
            email=payload.email,
            password=payload.password,
            frontend_url=settings.frontend_url,
        )
        logger.info("Pending signup created for email=%s.", result["email"])
        body = SignupResponse.model_validate(result).model_dump(by_alias=True, mode="json")
        return JSONResponse(status_code=201, content=body)
    except AuthError as exc:
        return _auth_error_response(exc)


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign in with email and password.",
)
async def login(payload: LoginRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        user, access_token, refresh_token = await service.login(
            email=payload.email, password=payload.password
        )
        user_data = dict(user)
        user_data["id"] = user_data.pop("_id")

        logger.info("User logged in via MongoDB (user_id=%s).", user_data["id"])
        body = AuthResponse(user=UserResponse.model_validate(user_data), message="Login successful.")
        response = JSONResponse(status_code=200, content=body.model_dump(by_alias=True, mode="json"))
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except AuthError as exc:
        return _auth_error_response(exc)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="The currently authenticated user.",
)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> JSONResponse:  # noqa: B008
    body = UserResponse.model_validate(current_user).model_dump(by_alias=True, mode="json")
    return JSONResponse(status_code=200, content=body)


@router.post(
    "/refresh",
    response_model=MessageResponse,
    summary="Rotate the access/refresh token pair.",
)
async def refresh(request: Request) -> JSONResponse:
    raw_refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not raw_refresh_token:
        return JSONResponse(status_code=401, content={"detail": "Refresh token is missing."})

    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        access_token, new_refresh_token = await service.refresh_tokens(raw_refresh_token)
        response = JSONResponse(status_code=200, content={"message": "Token refreshed."})
        _set_auth_cookies(response, access_token, new_refresh_token)
        return response
    except AuthError as exc:
        return _auth_error_response(exc)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Sign out and revoke the refresh token.",
)
async def logout(request: Request) -> JSONResponse:
    raw_refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    mongo_db = await get_mongodb()
    if mongo_db is not None and raw_refresh_token:
        await MongoDBAuthService(mongo_db).logout(raw_refresh_token)

    response = JSONResponse(status_code=200, content={"message": "Logged out."})
    _clear_auth_cookies(response)
    return response


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request a password reset email.",
)
async def forgot_password(payload: ForgotPasswordRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is not None:
        service = MongoDBAuthService(mongo_db)
        await service.forgot_password(email=payload.email, frontend_url=settings.frontend_url)
    
    return JSONResponse(status_code=200, content={"message": "If that email is in our system, we sent a password reset link."})


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password using a token.",
)
async def reset_password(payload: ResetPasswordRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        await service.reset_password(token=payload.token, new_password=payload.new_password)
        return JSONResponse(status_code=200, content={"message": "Password successfully reset."})
    except AuthError as exc:
        return _auth_error_response(exc)


@router.post(
    "/verify-email-code",
    response_model=AuthResponse,
    summary="Verify user email address using a 6-digit verification code.",
)
async def verify_email_code_api(payload: VerifyEmailCodeRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        user = await service.verify_email_code(email=payload.email, code=payload.code)
        access_token, refresh_token = await service.create_login_session(user)
        user_data = dict(user)
        user_data["id"] = user_data.pop("_id")
        logger.info("User verified email with code and established session (user_id=%s).", user_data["id"])
        body = AuthResponse(user=UserResponse.model_validate(user_data), message="Email verified successfully.")
        response = JSONResponse(status_code=200, content=body.model_dump(by_alias=True, mode="json"))
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except AuthError as exc:
        return _auth_error_response(exc)


@router.post(
    "/verify-email",
    response_model=AuthResponse,
    summary="Verify user email address using either 6-digit code or token.",
)
async def verify_email_api(payload: VerifyEmailRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        if payload.code and payload.email:
            user = await service.verify_email_code(email=payload.email, code=payload.code)
        elif payload.token:
            user = await service.verify_email(token=payload.token)
        else:
            return JSONResponse(status_code=400, content={"detail": "Verification code or token is required."})

        access_token, refresh_token = await service.create_login_session(user)
        user_data = dict(user)
        user_data["id"] = user_data.pop("_id")
        logger.info("User verified email and established session (user_id=%s).", user_data["id"])
        body = AuthResponse(
            user=UserResponse.model_validate(user_data),
            message="Email verified successfully.",
        )
        response = JSONResponse(status_code=200, content=body.model_dump(by_alias=True, mode="json"))
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except AuthError as exc:
        return _auth_error_response(exc)


@router.get(
    "/verify-email",
    summary="Verify user email address via link click in browser (legacy).",
)
async def verify_email_link(token: str) -> RedirectResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return RedirectResponse(
            url=f"{settings.frontend_url}/signin?verify_error=server_error",
            status_code=302,
        )

    service = MongoDBAuthService(mongo_db)
    try:
        await service.verify_email(token=token)
        return RedirectResponse(
            url=f"{settings.frontend_url}/signin?verified=true",
            status_code=302,
        )
    except AuthError:
        return RedirectResponse(
            url=f"{settings.frontend_url}/signin?verify_error=invalid_token",
            status_code=302,
        )


@router.post(
    "/resend-verification-code",
    response_model=MessageResponse,
    summary="Resend 6-digit email verification code.",
)
async def resend_verification_code_api(payload: ResendVerificationRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        await service.resend_verification_code(email=payload.email)
        return JSONResponse(
            status_code=200,
            content={"message": "Verification code sent to your email."},
        )
    except AuthError as exc:
        return _auth_error_response(exc)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend email verification code or link.",
)
async def resend_verification_api(payload: ResendVerificationRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is not None:
        service = MongoDBAuthService(mongo_db)
        try:
            await service.resend_verification_code(email=payload.email)
        except AuthError as exc:
            return _auth_error_response(exc)

    return JSONResponse(
        status_code=200,
        content={"message": "If an account requires verification, a verification code has been sent."},
    )


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Sign in or sign up using a Google Identity Services ID token.",
)
async def google_id_token_auth(payload: GoogleAuthRequest) -> JSONResponse:
    mongo_db = await get_mongodb()
    if mongo_db is None:
        return JSONResponse(status_code=503, content={"detail": "Database connection unavailable."})

    service = MongoDBAuthService(mongo_db)
    try:
        user, access_token, refresh_token = await service.authenticate_with_google_id_token(
            credential=payload.credential
        )
        user_data = dict(user)
        user_data["id"] = user_data.pop("_id")

        logger.info("User authenticated via Google ID token (user_id=%s).", user_data["id"])
        body = AuthResponse(user=UserResponse.model_validate(user_data), message="Sign in with Google successful.")
        response = JSONResponse(status_code=200, content=body.model_dump(by_alias=True, mode="json"))
        _set_auth_cookies(response, access_token, refresh_token)
        return response
    except AuthError as exc:
        return _auth_error_response(exc)
    except Exception as exc:
        logger.exception("Unexpected error during Google ID token authentication: %s", exc)
        return JSONResponse(
            status_code=400,
            content={"detail": "Google authentication failed. Please try again."},
        )


def _oauth_error_redirect(error_code: str, intent: str = "signin") -> RedirectResponse:
    target_page = "signup" if intent == "signup" else "signin"
    return RedirectResponse(
        url=f"{settings.frontend_url}/{target_page}?oauth_error={error_code}",
        status_code=302,
    )


def _oauth_success_redirect(access_token: str, refresh_token: str) -> RedirectResponse:
    response = RedirectResponse(url=f"{settings.frontend_url}/connect", status_code=302)
    _set_auth_cookies(response, access_token, refresh_token)
    return response


@router.get("/google/login", summary="Redirect the browser to Google's consent screen.")
async def google_login(intent: str = "signin") -> RedirectResponse:
    if not settings.google_oauth_configured:
        return _oauth_error_redirect("provider_not_configured", intent=intent)

    state = security.create_oauth_state_token("google", intent=intent)
    code_verifier, code_challenge = security.generate_pkce_pair()
    authorization_url = google_client.build_authorization_url(
        state=state, code_challenge=code_challenge
    )
    response = RedirectResponse(url=authorization_url, status_code=302)
    response.set_cookie(
        GOOGLE_CODE_VERIFIER_COOKIE,
        code_verifier,
        max_age=settings.oauth_state_expire_seconds,
        httponly=True,
        secure=settings.is_production,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return response


@router.get("/google/callback", summary="Google's OAuth redirect target.")
async def google_callback(request: Request) -> RedirectResponse:
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    code_verifier = request.cookies.get(GOOGLE_CODE_VERIFIER_COOKIE)

    intent = "signin"
    if state:
        try:
            state_payload = security.decode_oauth_state_token(state, expected_provider="google")
            intent = state_payload.get("intent", "signin")
        except security.InvalidTokenError:
            return _oauth_error_redirect("invalid_state", intent="signin")

    if request.query_params.get("error"):
        logger.info("Google OAuth denied/cancelled by the user (intent=%s).", intent)
        return _oauth_error_redirect("access_denied", intent=intent)

    if not state or not code or not code_verifier:
        return _oauth_error_redirect("invalid_state", intent=intent)

    try:
        profile = await google_client.exchange_code_for_profile(
            code=code, code_verifier=code_verifier
        )
        mongo_db = await get_mongodb()
        if mongo_db is None:
            return _oauth_error_redirect("server_error", intent=intent)

        if not profile.email_verified:
            return _oauth_error_redirect("missing_email", intent=intent)

        service = MongoDBAuthService(mongo_db)
        user_data = await service.authenticate_with_oauth(
            provider="google",
            provider_user_id=profile.provider_user_id,
            email=profile.email,
            email_verified=profile.email_verified,
            full_name=profile.full_name,
            profile_image=profile.profile_image,
        )
        access_token, refresh_token = await service.create_login_session(user_data)
        user_id_for_log = user_data["_id"]
    except AuthError as exc:
        logger.info("Google OAuth login rejected (%s, intent=%s).", exc.status, intent)
        return _oauth_error_redirect(_OAUTH_ERROR_CODES.get(exc.status, "server_error"), intent=intent)
    except Exception:
        logger.exception("Unexpected error completing Google OAuth login (intent=%s).", intent)
        return _oauth_error_redirect("server_error", intent=intent)

    logger.info("User authenticated via Google OAuth (user_id=%s, intent=%s).", user_id_for_log, intent)
    response = _oauth_success_redirect(access_token, refresh_token)
    response.delete_cookie(
        GOOGLE_CODE_VERIFIER_COOKIE,
        path="/",
        samesite=settings.cookie_samesite,
        secure=settings.is_production,
        httponly=True,
    )
    return response


@router.get("/github/login", summary="Redirect the browser to GitHub's consent screen.")
async def github_login(intent: str = "signin") -> RedirectResponse:
    if not settings.github_oauth_configured:
        return _oauth_error_redirect("provider_not_configured", intent=intent)

    state = security.create_oauth_state_token("github", intent=intent)
    authorization_url = github_client.build_authorization_url(state=state)
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/github/callback", summary="GitHub's OAuth redirect target.")
async def github_callback(request: Request) -> RedirectResponse:
    state = request.query_params.get("state")
    code = request.query_params.get("code")

    intent = "signin"
    if state:
        try:
            state_payload = security.decode_oauth_state_token(state, expected_provider="github")
            intent = state_payload.get("intent", "signin")
        except security.InvalidTokenError:
            return _oauth_error_redirect("invalid_state", intent="signin")

    if request.query_params.get("error"):
        logger.info("GitHub OAuth denied/cancelled by the user (intent=%s).", intent)
        return _oauth_error_redirect("access_denied", intent=intent)

    if not state or not code:
        return _oauth_error_redirect("invalid_state", intent=intent)

    try:
        profile = await github_client.exchange_code_for_profile(code=code)
        mongo_db = await get_mongodb()
        if mongo_db is None:
            return _oauth_error_redirect("server_error", intent=intent)

        if not profile.email_verified:
            return _oauth_error_redirect("missing_email", intent=intent)

        service = MongoDBAuthService(mongo_db)
        user_data = await service.authenticate_with_oauth(
            provider="github",
            provider_user_id=profile.provider_user_id,
            email=profile.email,
            email_verified=profile.email_verified,
            full_name=profile.full_name,
            profile_image=profile.profile_image,
        )
        access_token, refresh_token = await service.create_login_session(user_data)
        user_id_for_log = user_data["_id"]
    except AuthError as exc:
        logger.info("GitHub OAuth login rejected (%s, intent=%s).", exc.status, intent)
        return _oauth_error_redirect(_OAUTH_ERROR_CODES.get(exc.status, "server_error"), intent=intent)
    except Exception:
        logger.exception("Unexpected error completing GitHub OAuth login (intent=%s).", intent)
        return _oauth_error_redirect("server_error", intent=intent)

    logger.info("User authenticated via GitHub OAuth (user_id=%s, intent=%s).", user_id_for_log, intent)
    return _oauth_success_redirect(access_token, refresh_token)

