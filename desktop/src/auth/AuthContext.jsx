import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { AUTH_ENABLED } from "./config";
import {
  signIn as cognitoSignIn,
  signUp as cognitoSignUp,
  confirmSignUp as cognitoConfirmSignUp,
  signOut as cognitoSignOut,
  getCurrentSession,
} from "./cognito";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(AUTH_ENABLED);

  useEffect(() => {
    if (!AUTH_ENABLED) return;

    getCurrentSession().then((session) => {
      if (session) {
        const payload = session.getIdToken().decodePayload();
        setUser({ email: payload.email || payload.sub });
      }
      setIsLoading(false);
    });
  }, []);

  const login = useCallback(async (email, password) => {
    const session = await cognitoSignIn(email, password);
    const payload = session.getIdToken().decodePayload();
    setUser({ email: payload.email || payload.sub });
  }, []);

  const register = useCallback(async (email, password) => {
    await cognitoSignUp(email, password);
  }, []);

  const confirmRegistration = useCallback(async (email, code) => {
    await cognitoConfirmSignUp(email, code);
  }, []);

  const logout = useCallback(() => {
    cognitoSignOut();
    setUser(null);
  }, []);

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    confirmRegistration,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
