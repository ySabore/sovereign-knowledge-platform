import { FormEvent, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { clerkEnabled } from "../lib/clerkEnv";

export function LoginPage() {
  const { user, login, loading } = useAuth();
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && user) {
    return <Navigate to="/home" replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ minHeight: "100%", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div className="sk-panel" style={{ width: "100%", maxWidth: 400 }}>
        <h2 style={{ marginTop: 0 }}>Sign in</h2>
        <p className="sk-muted">Sovereign Knowledge Platform</p>
        <form onSubmit={onSubmit}>
          <label className="sk-label">Email</label>
          <input
            className="sk-input"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <label className="sk-label" style={{ marginTop: "0.75rem" }}>
            Password
          </label>
          <input
            className="sk-input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {err && (
            <p className="sk-error" style={{ marginTop: "0.75rem" }}>
              {err}
            </p>
          )}
          <button className="sk-btn" type="submit" disabled={busy || loading} style={{ marginTop: "1rem", width: "100%" }}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="sk-muted" style={{ marginTop: "1rem", fontSize: "0.8rem" }}>
          Use the seeded platform owner from <span className="sk-mono">scripts/seed.py</span> and your{" "}
          <span className="sk-mono">.env</span>.
        </p>
        {clerkEnabled && (
          <div style={{ marginTop: "1.25rem", paddingTop: "1.25rem", borderTop: "1px solid var(--border)" }}>
            <p className="sk-muted" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
              Or continue with Clerk (configure backend <span className="sk-mono">CLERK_*</span> to accept session tokens).
            </p>
            <Link className="sk-btn secondary" to="/sign-in" style={{ display: "inline-block", width: "100%", textAlign: "center" }}>
              Sign in with Clerk
            </Link>
            <p className="sk-muted" style={{ fontSize: "0.8rem", marginTop: "0.75rem" }}>
              New user? <Link to="/sign-up">Create a Clerk account</Link>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
