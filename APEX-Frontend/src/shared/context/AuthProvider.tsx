
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { AuthContext, type AuthContextValue, type AuthUser } from "./AuthContext";
import { getMe, logOut } from "@/features/auth/services/authService";
import type { UserResponse } from "@/shared/types/domain";

/**
 * Auth state backed by FastAPI / MongoDB.
 * This is the single source of truth for the application's authentication state.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    setIsAuthLoading(true);
    try {
      const userProfile = await getMe();
      setCurrentUser(userProfile);
    } catch (err) {
      // 401 or network error - user is not logged in
      setCurrentUser(null);
    } finally {
      setIsAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial auth check on mount
    void checkAuth();
  }, [checkAuth]);

  const user = useMemo<AuthUser | null>(() => {
    if (!currentUser) return null;
    return {
      name: currentUser.fullName || currentUser.email.split("@")[0] || "User",
      email: currentUser.email,
    };
  }, [currentUser]);

  const handleLogout = async () => {
    await logOut();
    setCurrentUser(null);
    window.sessionStorage.clear();
    window.location.href = "/signin";
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: currentUser !== null,
      isAuthLoading,
      loading: isAuthLoading,
      user,
      currentUser,
      login: (newUser?: UserResponse) => {
        if (newUser) {
          setCurrentUser(newUser);
          setIsAuthLoading(false);
        } else {
          void checkAuth();
        }
      },
      logout: handleLogout,
    }),
    [user, currentUser, isAuthLoading, checkAuth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
