import React from "react";
import { AUTH_ENABLED, useAuth } from "../auth";
import LoginPage from "./LoginPage";

export default function AuthGate({ children }) {
  const auth = useAuth();

  if (!AUTH_ENABLED) return children;

  if (auth.isLoading) {
    return (
      <div className="login-page">
        <div className="login-card">
          <p className="login-loading">Loading...</p>
        </div>
      </div>
    );
  }

  if (!auth.isAuthenticated) return <LoginPage />;

  return children;
}
