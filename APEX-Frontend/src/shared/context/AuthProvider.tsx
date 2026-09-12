import React, { useEffect, useMemo, useState } from "react";
import { onAuthStateChanged, signOut, getRedirectResult, type User as FirebaseUser } from "firebase/auth";
import { auth } from "@/firebase/firebase";
import { AuthContext, type AuthContextValue, type AuthUser } from "./AuthContext";

/**
 * Auth state backed by Firebase Authentication.
 * This is the single source of truth for the application's authentication state.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<FirebaseUser | null>(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  useEffect(() => {
    // Fix: BFCache (Back-Forward Cache) causes the page to be restored from cache
    // after a signInWithRedirect flow, which drops the Vite WebSocket and prevents
    // getRedirectResult from being called. Force a reload if the page is restored
    // from BFCache so the auth redirect result is always processed on a fresh load.
    const handlePageShow = (e: PageTransitionEvent) => {
      if (e.persisted) {
        // Page was restored from BFCache — reload to re-run redirect result handling
        window.location.reload();
      }
    };
    window.addEventListener('pageshow', handlePageShow);

    // Listen for authentication state changes from Firebase
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      console.log("[Auth] State changed:", user ? user.email : "Logged out");
      setCurrentUser(user);
      setIsAuthLoading(false);
    });

    return () => {
      window.removeEventListener('pageshow', handlePageShow);
      unsubscribe();
    };
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
      login: (newUser: FirebaseUser) => {
        setCurrentUser(newUser);
        setIsAuthLoading(false);
      },
      logout: async () => {
        await signOut(auth);
      },
    }),
    [user, currentUser, isAuthLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
