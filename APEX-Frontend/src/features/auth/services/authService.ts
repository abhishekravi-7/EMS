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
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }
}

/**
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
 * Must be called once on app load (in App.tsx / auth context).
 * Completes the redirect-based OAuth sign-in and returns the signed-in user,
 * or null if no redirect was pending.
 */
export async function handleRedirectResult(): Promise<FirebaseUser | null> {
  try {
    const result = await getRedirectResult(auth);
    return result ? result.user : null;
  } catch (error) {
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }
}

/**
 * Send a password reset email to the specified address.
 */
export async function resetPassword(email: string): Promise<void> {
  console.log("[Auth] Requesting password reset for:", email);
  try {
    // We use the simplest possible call first to avoid any configuration-related failures
    // such as unauthorized redirect URIs or action code settings.
    await sendPasswordResetEmail(auth, email);
    console.log("[Auth] Password reset request successful (according to SDK)");
  } catch (error: any) {
    const errorCode = error.code || extractFirebaseErrorMessage(error);
    console.error("[Auth] Firebase Reset Password Error Object:", error);
    console.error("[Auth] Firebase Reset Password Error Code:", errorCode);

    // Specifically handle the case where the feature might be disabled in Firebase
    if (errorCode === "auth/operation-not-allowed") {
      throw new Error("Password reset is currently disabled in the Firebase Console. Please enable it in Authentication > Templates.");
    }

    throw new Error(mapFirebaseError(errorCode));
  }
}

/**
 * Links email/password credentials to the currently signed-in user account.
 */
export async function linkPasswordToAccount(password: string): Promise<void> {
  const user = auth.currentUser;
  if (!user || !user.email) {
    throw new Error("No authenticated user found to link password.");
  }
  try {
    const credential = EmailAuthProvider.credential(user.email, password);
    await linkWithCredential(user, credential);
    await user.reload();
  } catch (error) {
    const fbErr = error as FirebaseErrorLike;
    if (fbErr && fbErr.code === "auth/provider-already-linked") {
      try {
        await updatePassword(user, password);
        await user.reload();
        return;
      } catch (updateErr) {
        throw new Error(mapFirebaseError(extractFirebaseErrorMessage(updateErr)));
      }
    }
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }
}

/**
 * Links Google provider to the currently signed-in user account.
 */
export async function linkGoogleToAccount(): Promise<FirebaseUser> {
  const user = auth.currentUser;
  if (!user) {
    throw new Error("No authenticated user found to link Google account.");
  }
  const provider = new GoogleAuthProvider();
  try {
    const result = await linkWithPopup(user, provider);
    await user.reload();
    return result.user;
  } catch (error) {
    throw new Error(mapFirebaseError(extractFirebaseErrorMessage(error)));
  }
}

/**
 * Returns the list of provider IDs linked to the current user (e.g. ['google.com', 'password']).
 */
export function getUserProviders(user?: FirebaseUser | null): string[] {
  const targetUser = user || auth.currentUser;
  if (!targetUser || !targetUser.providerData) return [];
  return targetUser.providerData.map((p) => p.providerId);
}

/**
 * Checks if the user is authenticated solely through Google and has no password linked.
 */
export function isGoogleOnlyUser(user?: FirebaseUser | null): boolean {
  const providers = getUserProviders(user);
  return providers.includes("google.com") && !providers.includes("password");
}

export async function logOut(): Promise<void> {
  await signOut(auth);
}

/**
 * Retrieves the Firebase ID token for the current user.
 * Use this to include in the Authorization header for backend API calls.
 */
export async function getAuthToken(): Promise<string | null> {
  if (!auth.currentUser) return null;
  return auth.currentUser.getIdToken();
}
