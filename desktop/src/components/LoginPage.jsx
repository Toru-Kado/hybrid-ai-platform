import React, { useState } from "react";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { login, register, confirmRegistration } = useAuth();
  const [view, setView] = useState("signin"); // signin | register | confirm
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmCode, setConfirmCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSignIn(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err.message || "Sign in failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(email, password);
      setView("confirm");
    } catch (err) {
      setError(err.message || "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await confirmRegistration(email, confirmCode);
      await login(email, password);
    } catch (err) {
      setError(err.message || "Confirmation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">TK-AI</h1>

        <div className="login-tabs">
          <button
            className={`login-tab ${view === "signin" ? "active" : ""}`}
            onClick={() => { setView("signin"); setError(""); }}
            type="button"
          >
            Sign In
          </button>
          <button
            className={`login-tab ${view === "register" || view === "confirm" ? "active" : ""}`}
            onClick={() => { setView("register"); setError(""); }}
            type="button"
          >
            Register
          </button>
        </div>

        {error && <div className="login-error">{error}</div>}

        {view === "signin" && (
          <form onSubmit={handleSignIn} className="login-form">
            <label className="login-label">
              Email
              <input
                type="email"
                className="login-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={loading}
              />
            </label>
            <label className="login-label">
              Password
              <input
                type="password"
                className="login-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                disabled={loading}
              />
            </label>
            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
        )}

        {view === "register" && (
          <form onSubmit={handleRegister} className="login-form">
            <label className="login-label">
              Email
              <input
                type="email"
                className="login-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={loading}
              />
            </label>
            <label className="login-label">
              Password
              <input
                type="password"
                className="login-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                minLength={8}
                disabled={loading}
              />
            </label>
            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? "Creating account..." : "Create Account"}
            </button>
          </form>
        )}

        {view === "confirm" && (
          <form onSubmit={handleConfirm} className="login-form">
            <p className="login-hint">
              A verification code was sent to <strong>{email}</strong>.
            </p>
            <label className="login-label">
              Verification Code
              <input
                type="text"
                className="login-input"
                value={confirmCode}
                onChange={(e) => setConfirmCode(e.target.value)}
                required
                autoComplete="one-time-code"
                disabled={loading}
              />
            </label>
            <button type="submit" className="login-submit" disabled={loading}>
              {loading ? "Verifying..." : "Verify & Sign In"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
