import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  signInWithPopup,
  sendPasswordResetEmail,
  linkWithCredential,
  linkWithPopup,
  updatePassword,
  fetchSignInMethodsForEmail,
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
    default:
      return "An unexpected error occurred. Please try again.";
  }
}

export async function signUp(payload: SignUpRequest): Promise<FirebaseUser> {
  try {
    const userCredential = await createUserWithEmailAndPassword(
      auth,
      payload.email,
      payload.password
    );

    // Update profile with full name
    await updateProfile(userCredential.user, {
      displayName: payload.fullName
    });

    return userCredential.user;
  } catch (error: any) {
    throw new Error(mapFirebaseError(error.code || error.message));
  }
}

export interface SignInRequest {
  email: string;
  password: string;
}

export async function signIn(payload: SignInRequest): Promise<FirebaseUser> {
  try {
    const userCredential = await signInWithEmailAndPassword(
      auth,
      payload.email,
      payload.password
    );
    return userCredential.user;
  } catch (error: any) {
    // If sign in fails, check whether the account was created with Google and has no password
    try {
      const methods = await fetchSignInMethodsForEmail(auth, payload.email);
      if (methods.includes("google.com") && !methods.includes("password")) {
        throw new Error(
          "This account was created with Google. Please sign in with Google or set a password for this account."
        );
      }
    } catch (fetchErr: any) {
      if (fetchErr.message && fetchErr.message.includes("This account was created with Google")) {
        throw fetchErr;
      }
    }
    throw new Error(mapFirebaseError(error.code || error.message));
  }
}

/**
 * Sign in with Google using Firebase.
 */
export async function signInWithGoogle(): Promise<FirebaseUser> {
  const provider = new GoogleAuthProvider();
  try {
    const result = await signInWithPopup(auth, provider);
    return result.user;
  } catch (error: any) {
    throw new Error(mapFirebaseError(error.code || error.message));
  }
}

/**
 * Sign in with GitHub using Firebase.
 */
export async function signInWithGithub(): Promise<FirebaseUser> {
  const provider = new GithubAuthProvider();
  try {
    const result = await signInWithPopup(auth, provider);
    return result.user;
  } catch (error: any) {
    throw new Error(mapFirebaseError(error.code || error.message));
  }
}

/**
 * Send a password reset email to the specified email address.
 * Enables Google-authenticated users to set a password and sign in with email/password.
 */
export async function resetPassword(email: string): Promise<void> {
  try {
    await sendPasswordResetEmail(auth, email);
  } catch (error: any) {
    throw new Error(mapFirebaseError(error.code || error.message));
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
  } catch (error: any) {
    if (error.code === "auth/provider-already-linked") {
      try {
        await updatePassword(user, password);
        await user.reload();
        return;
      } catch (updateErr: any) {
        throw new Error(mapFirebaseError(updateErr.code || updateErr.message));
      }
    }
    throw new Error(mapFirebaseError(error.code || error.message));
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
  } catch (error: any) {
    throw new Error(mapFirebaseError(error.code || error.message));
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
