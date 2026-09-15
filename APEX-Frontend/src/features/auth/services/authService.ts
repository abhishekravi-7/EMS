

import { requestJson } from "@/services/http/client";
import { GITHUB_AUTH_LOGIN_URL, GOOGLE_AUTH_LOGIN_URL } from "@/services/config/env";
import type { UserResponse } from "@/shared/types/domain";

import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  signInWithRedirect,
  signInWithPopup,
  getRedirectResult,
  sendPasswordResetEmail,
  linkWithCredential,
  linkWithPopup,
  updatePassword,
  fetchSignInMethodsForEmail,
  setPersistence,
  browserLocalPersistence,
  browserSessionPersistence,
  EmailAuthProvider,
  GoogleAuthProvider,
  GithubAuthProvider,
  type User as FirebaseUser
} from "firebase/auth";
import { auth } from "@/firebase/firebase";


export interface SignUpRequest {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}



/**
 * Maps Firebase Auth errors to user-friendly messages.
 */
export function mapFirebaseError(code: string): string {
  switch (code) {
    case "auth/email-already-in-use":
      return "An account with this email already exists. Sign in or use 'Forgot password?' to set a password.";
    case "auth/account-exists-with-different-credential":
      return "An account already exists with this email using a different sign-in method. Please sign in with your original method (e.g. Google) or reset your password.";
    case "auth/provider-already-linked":
      return "This authentication provider is already linked to your account.";
    case "auth/credential-already-in-use":
      return "This credential is already linked to a different account.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/invalid-credential":
      return "Invalid email or password.";
    case "auth/weak-password":
      return "Password is too weak. Please use at least 8 characters.";
    case "auth/user-not-found":
      return "No account found with this email.";
    case "auth/wrong-password":
      return "Invalid email or password.";
    case "auth/popup-closed-by-user":
      return "Sign-in was cancelled.";
    case "auth/cancelled-popup-request":
      return "Only one sign-in popup can be open at a time.";
    case "auth/requires-recent-login":
      return "This operation requires a recent sign-in. Please sign in again.";
    case "auth/too-many-requests":
      return "Access to this account has been temporarily disabled due to many failed attempts. Please try again later or reset your password.";
    case "auth/network-request-failed":
      return "Network error. Please check your internet connection.";
    case "auth/internal-error":
      return "Internal authentication error. Please try again.";
    case "auth/invalid-api-key":
      return "Firebase Configuration Error: Invalid API Key. Please check your .env file.";
    case "auth/unauthorized-domain":
      return "This domain (localhost) is not authorized in the Firebase Console.";
    case "auth/operation-not-allowed":
      return "This sign-in method (Email/Google/GitHub) is disabled in the Firebase Console.";
    default:
      console.warn("[Auth] Unmapped error code:", code);
      // Return a descriptive string instead of "Unexpected error"
      return `Auth Error: ${code.replace("auth/", "").replace(/-/g, " ")}`;
  }
}

interface FirebaseErrorLike {
  code?: string;
  message?: string;
}

function extractFirebaseErrorMessage(error: unknown): string {
  console.error("[Auth] Raw Firebase Error:", error);
  if (error && typeof error === "object") {
    const fbErr = error as FirebaseErrorLike;
    // Firebase JS SDK errors typically have a .code property
    return fbErr.code || fbErr.message || "unknown-error";
  }
  return typeof error === "string" ? error : "unknown-error";
}

export async function signUp(payload: SignUpRequest): Promise<FirebaseUser> {
  try {
    const userCredential = await createUserWithEmailAndPassword(
      auth,
      payload.email,
      payload.password
    );
    await updateProfile(userCredential.user, {
      displayName: payload.fullName
    });
    return userCredential.user;
  } catch (error) {
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }
}


export interface SignInRequest {
  email: string;
  password: string;
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

 * Sign in with email/password.
 * Session is persisted across browser closes by default.
 */
export async function signIn(payload: SignInRequest): Promise<FirebaseUser> {
  try {
    // Always use local persistence (stays logged in across browser restarts)
    await setPersistence(auth, browserLocalPersistence);
    const userCredential = await signInWithEmailAndPassword(
      auth,
      payload.email,
      payload.password
    );
    return userCredential.user;
  } catch (error) {
    // If sign in fails, check whether the account was created with Google and has no password
    try {
      const methods = await fetchSignInMethodsForEmail(auth, payload.email);
      if (methods.includes("google.com") && !methods.includes("password")) {
        throw new Error(
          "This account was created with Google. Please sign in with Google or set a password for this account."
        );
      }
    } catch (fetchErr) {
      if (fetchErr instanceof Error && fetchErr.message.includes("This account was created with Google")) {
        throw fetchErr;
      }

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

 * Sign in with Google using Popup.
 * Popups are more reliable for React SPAs as they don't cause a full page reload.
 */
export async function signInWithGoogle(): Promise<FirebaseUser> {
  const provider = new GoogleAuthProvider();
  provider.addScope("email");
  provider.addScope("profile");
  try {
    const result = await signInWithPopup(auth, provider);
    return result.user;
  } catch (error) {
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }
}

/**
 * Sign in with GitHub using Popup.
 */
export async function signInWithGithub(): Promise<FirebaseUser> {
  const provider = new GithubAuthProvider();
  provider.addScope("read:user");
  provider.addScope("user:email");
  try {
    const result = await signInWithPopup(auth, provider);
    return result.user;
  } catch (error) {
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }

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
