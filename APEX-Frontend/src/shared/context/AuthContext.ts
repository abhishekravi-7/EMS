import { createContext, useContext } from "react";
import type { UserResponse } from "@/shared/types/domain";

export interface AuthUser {
  name: string;
  email: string;
}

export interface AuthContextValue {
  isAuthenticated: boolean;
  isAuthLoading: boolean;
  user: AuthUser | null;
  currentUser: UserResponse | null;
  loading: boolean;
  login: (user?: UserResponse) => void;
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
