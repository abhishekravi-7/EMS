
import { requestJson } from "@/services/http/client";
import { GITHUB_AUTH_LOGIN_URL, GOOGLE_AUTH_LOGIN_URL } from "@/services/config/env";
import type { UserResponse } from "@/shared/types/domain";

export interface SignUpRequest {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export interface SignInRequest {
  email: string;
  password: string;
  rememberMe?: boolean;
}

/**
 * Sign up a new user via the FastAPI backend (MongoDB).
 */
export async function signUp(payload: SignUpRequest): Promise<UserResponse> {
  const response = await requestJson<{ user: UserResponse; message: string }>(
    "/auth/signup",
    "Registration failed",
    {
      method: "POST",
      body: payload,
    }
  );
  return response.user;
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
 * Sign in with Google by redirecting to the backend OAuth initiation endpoint.
 */
export async function signInWithGoogle(): Promise<void> {
  window.location.href = GOOGLE_AUTH_LOGIN_URL;
}

/**
 * Sign in with GitHub by redirecting to the backend OAuth initiation endpoint.
 */
export async function signInWithGithub(): Promise<void> {
  window.location.href = GITHUB_AUTH_LOGIN_URL;
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
