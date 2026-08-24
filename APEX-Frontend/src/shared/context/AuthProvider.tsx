import React, { useEffect, useMemo, useState } from "react";
import { onAuthStateChanged, signOut, type User as FirebaseUser } from "firebase/auth";
import { auth } from "@/firebase/firebase";
import { AuthContext, type AuthContextValue, type AuthUser } from "./AuthContext";

/**
 * Auth state backed by Firebase Authentication.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<FirebaseUser | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setCurrentUser(user);
      setIsAuthLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const user = useMemo<AuthUser | null>(() => {
    if (!currentUser) return null;
    return {
      name: currentUser.displayName || currentUser.email?.split("@")[0] || "User",
      email: currentUser.email || "",
    };
  }, [currentUser]);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: currentUser !== null,
      isAuthLoading,
      loading: isAuthLoading,
      user,
      currentUser,
      login: () => {},
      logout: async () => {
        await signOut(auth);
      },
    }),
    [user, currentUser, isAuthLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
