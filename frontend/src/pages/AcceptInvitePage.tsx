import { Link, useSearchParams } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { clerkEnabled } from "../lib/clerkEnv";

type AcceptedMember = {
  email: string;
  organization_id: string;
  role: string;
};

export function AcceptInvitePage() {
  const { user, loading, refreshMe } = useAuth();
  const [searchParams] = useSearchParams();
  const token = (searchParams.get("token") || "").trim();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<AcceptedMember | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [attempted, setAttempted] = useState(false);

  const redirectToHere = useMemo(() => {
    const p = new URLSearchParams();
    p.set("redirect", `/accept-invite${token ? `?token=${encodeURIComponent(token)}` : ""}`);
    return p.toString();
  }, [token]);

  useEffect(() => {
    // New token or account: allow one fresh auto-attempt.
    setAttempted(false);
    setErr(null);
  }, [token, user?.id]);

  useEffect(() => {
    if (loading || !user || !token || busy || done || attempted) return;
    setBusy(true);
    setAttempted(true);
    setErr(null);
    void api
      .post<AcceptedMember>("/organizations/invites/accept", { token })
      .then(async ({ data }) => {
        setDone(data);
        await refreshMe();
      })
      .catch((ex) => setErr(apiErrorMessage(ex)))
      .finally(() => setBusy(false));
  }, [loading, user, token, busy, done, attempted, refreshMe]);

  return (
    <div style={{ minHeight: "100%", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div className="sk-panel" style={{ width: "100%", maxWidth: 560 }}>
        <h2 style={{ marginTop: 0 }}>Accept organization invite</h2>
        {!token && (
          <p className="sk-error">
            This invite link is missing a token. Open the invite email link again, or ask for a resend.
          </p>
        )}

        {token && loading && <p className="sk-muted">Checking your session…</p>}

        {token && !loading && !user && (
          <>
            <p className="sk-muted">
              Sign in with the same email address that received this invite, then return to this page.
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Link className="sk-btn secondary" to={`/login?${redirectToHere}`}>
                Email/password sign-in
              </Link>
              {clerkEnabled && (
                <Link className="sk-btn" to={`/sign-in?${redirectToHere}`}>
                  Sign in with Clerk
                </Link>
              )}
            </div>
          </>
        )}

        {token && user && busy && <p className="sk-muted">Accepting invite…</p>}

        {done && (
          <>
            <p style={{ color: "var(--ok)", marginBottom: "0.5rem" }}>
              Invite accepted for <strong>{done.email}</strong>.
            </p>
            <p className="sk-muted">
              Role: <span className="sk-mono">{done.role}</span>. You can now open your organization workspace.
            </p>
            <div style={{ marginTop: "1rem" }}>
              <Link className="sk-btn" to="/home">
                Go to Home
              </Link>
            </div>
          </>
        )}

        {!busy && !done && err && (
          <>
            <p className="sk-error">{err}</p>
            <p className="sk-muted" style={{ marginTop: "0.5rem" }}>
              If this says token is invalid/used, ask the inviter to resend and use the latest link.
            </p>
            <div style={{ marginTop: "0.75rem" }}>
              <button type="button" className="sk-btn secondary" onClick={() => setAttempted(false)}>
                Try again
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
