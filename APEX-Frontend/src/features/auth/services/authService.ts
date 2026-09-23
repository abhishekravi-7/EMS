import { requestJson } from "@/services/http/client";
import { GITHUB_AUTH_LOGIN_URL, GOOGLE_AUTH_LOGIN_URL } from "@/services/config/env";
import type { UserResponse } from "@/shared/types/domain";

export interface SignUpRequest {
  fullName?: string;
  email: string;
  password: string;
  confirmPassword?: string;
}

export interface SignInRequest {
  email: string;
  password: string;
}

/**
 * Sign up a new user via the FastAPI backend (MongoDB).
 * Initiates pending registration and sends 6-digit verification code.
 */
export async function signUp(payload: SignUpRequest): Promise<{ email: string; message: string }> {
  return requestJson<{ email: string; message: string }>(
    "/auth/signup",
    "Registration failed",
    {
      method: "POST",
      body: payload,
    }
  );
}

/**
 * Sign in a user via the FastAPI backend (MongoDB).
 * The backend sets an HttpOnly access_token cookie.
 */
export async function signIn(payload: SignInRequest): Promise<UserResponse> {
  const response = await requestJson<{ user: UserResponse; message: string }>(
    "/auth/login",
    "Login failed",
    {
      method: "POST",
      body: payload,
    }
  );
  return response.user;
}

/**
 * Sign in with Google Identity Services ID Token (One Tap or Button).
 */
export async function signInWithGoogleIdToken(credential: string): Promise<UserResponse> {
  const response = await requestJson<{ user: UserResponse; message: string }>(
    "/auth/google",
    "Google sign in failed",
    {
      method: "POST",
      body: { credential },
    }
  );
  return response.user;
}

/**
 * Sign in with Google by redirecting to the backend OAuth initiation endpoint.
 */
export async function signInWithGoogle(intent: "signin" | "signup" = "signin"): Promise<void> {
  const url = `${GOOGLE_AUTH_LOGIN_URL}?intent=${encodeURIComponent(intent)}`;
  window.location.href = url;
}

/**
 * Sign in with GitHub by redirecting to the backend OAuth initiation endpoint.
 */
export async function signInWithGithub(intent: "signin" | "signup" = "signin"): Promise<void> {
  const url = `${GITHUB_AUTH_LOGIN_URL}?intent=${encodeURIComponent(intent)}`;
  window.location.href = url;
}

/**
 * Verify user email with a 6-digit verification code.
 */
export async function verifyEmailCode(email: string, code: string): Promise<{ user?: UserResponse; message: string }> {
  return requestJson<{ user?: UserResponse; message: string }>(
    "/auth/verify-email-code",
    "Email verification failed",
    {
      method: "POST",
      body: { email, code },
    }
  );
}

/**
 * Resend 6-digit email verification code.
 */
export async function resendVerificationCode(email: string): Promise<{ message: string }> {
  return requestJson<{ message: string }>(
    "/auth/resend-verification-code",
    "Resend verification code failed",
    {
      method: "POST",
      body: { email },
    }
  );
}

/**
 * Verify user email with a verification token (legacy).
 */
export async function verifyEmail(token: string): Promise<{ user?: UserResponse; message: string }> {
  return requestJson<{ user?: UserResponse; message: string }>(
    "/auth/verify-email",
    "Email verification failed",
    {
      method: "POST",
      body: { token },
    }
  );
}

/**
 * Resend verification email for an unverified account.
 */
export async function resendVerification(email: string): Promise<void> {
  await requestJson(
    "/auth/resend-verification-code",
    "Resend verification failed",
    {
      method: "POST",
      body: { email },
    }
  );
}

/**
 * Request a password reset email via the backend.
 */
export async function resetPassword(email: string): Promise<void> {
  await requestJson(
    "/auth/forgot-password",
    "Password reset request failed",
    {
      method: "POST",
      body: { email },
    }
  );
}

/**
 * Confirm the password reset with the token.
 */
export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await requestJson(
    "/auth/reset-password",
    "Password reset failed",
    {
      method: "POST",
      body: { token, newPassword },
    }
  );
}

/**
 * Log out the current user via the backend.
 */
export async function logOut(): Promise<void> {
  try {
    await requestJson("/auth/logout", "Logout failed", { method: "POST" });
  } catch (err) {
    console.error("Logout failed on server, but clearing local state anyway:", err);
  }
}

/**
 * Retrieves the profile of the currently logged-in user.
 */
export async function getMe(): Promise<UserResponse> {
  return requestJson<UserResponse>("/auth/me", "Failed to fetch user profile");
}
