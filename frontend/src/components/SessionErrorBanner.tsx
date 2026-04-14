import { useAuth } from "../context/AuthContext";

/** Shows API error after Clerk sign-in when `/auth/me` fails (e.g. missing email on session JWT). */
function clerkSetupHint(detail: string): string | null {
  const d = detail.toLowerCase();
  if (!d.includes("clerk") && !d.includes("email") && !d.includes("mapped to a user")) return null;
  return (
    "If you use Clerk: set CLERK_ENABLED=true and CLERK_ISSUER on the API (Frontend API URL), " +
    "and add an email claim under Clerk → Sessions → Customize session token " +
    '(e.g. "email": "{{user.primary_email_address.email_address}}"), then sign out and back in.'
  );
}

export function SessionErrorBanner() {
  const { sessionError, clearSessionError } = useAuth();
  if (!sessionError) return null;
  const hint = clerkSetupHint(sessionError);
  return (
    <div
      role="alert"
      style={{
        margin: 0,
        padding: "12px 16px",
        background: "rgba(220, 38, 38, 0.12)",
        borderBottom: "1px solid rgba(220, 38, 38, 0.35)",
        color: "#fecaca",
        fontSize: 14,
        lineHeight: 1.5,
      }}
    >
      <strong style={{ display: "block", marginBottom: 6 }}>Sign-in could not finish</strong>
      {sessionError}
      {hint ? (
        <div style={{ marginTop: 10, fontSize: 13, opacity: 0.95, maxWidth: 720 }}>{hint}</div>
      ) : null}
      <button
        type="button"
        onClick={() => clearSessionError()}
        style={{
          marginLeft: 12,
          padding: "4px 10px",
          fontSize: 12,
          cursor: "pointer",
          background: "transparent",
          border: "1px solid rgba(255,255,255,0.3)",
          borderRadius: 6,
          color: "inherit",
        }}
      >
        Dismiss
      </button>
    </div>
  );
}
