import { createContext, useContext } from "react";

export interface AuthUser {
  name: string;
  email: string;
}

export interface AuthContextValue {
  isAuthenticated: boolean;
  isAuthLoading: boolean;   // true until the initial /api/auth/me check completes
  user: AuthUser | null;
  login: (user: AuthUser) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
