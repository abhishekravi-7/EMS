import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  signInWithPopup,
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
      return "An account with this email already exists.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/invalid-credential":
      return "Invalid email or password.";
    case "auth/weak-password":
      return "Password is too weak.";
    case "auth/user-not-found":
      return "No account found with this email.";
    case "auth/wrong-password":
      return "Invalid email or password.";
    case "auth/popup-closed-by-user":
      return "Sign-in was cancelled.";
    case "auth/cancelled-popup-request":
      return "Only one sign-in popup can be open at a time.";
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
    throw new Error(mapFirebaseError(error.code));
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
    throw new Error(mapFirebaseError(error.code));
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
    throw new Error(mapFirebaseError(error.code));
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
    throw new Error(mapFirebaseError(error.code));
  }
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
