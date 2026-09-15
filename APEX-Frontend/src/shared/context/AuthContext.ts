import { createContext, useContext } from "react";
import type { User as FirebaseUser } from "firebase/auth";

export interface AuthUser {
  name: string;
  email: string;
}

export interface AuthContextValue {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  user: AuthUser | null;
  currentUser: FirebaseUser | null; // Firebase user object
  loading: boolean;                // Alias for isAuthLoading for Firebase convention
  login: (user: FirebaseUser) => void;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
