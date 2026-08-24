import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  updateProfile,
  signInWithPopup,
  GoogleAuthProvider,
  type User as FirebaseUser
} from "firebase/auth";
import { auth } from "@/firebase/firebase";

export interface SignUpRequest {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

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

export async function signInWithGoogle(): Promise<FirebaseUser> {
  const provider = new GoogleAuthProvider();
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

export async function getAuthToken(): Promise<string | null> {
  if (!auth.currentUser) return null;
  return auth.currentUser.getIdToken();
}
