import { SignIn } from "@clerk/clerk-react";
import { Link } from "react-router-dom";

export function ClerkSignInPage() {
  return (
    <div style={{ minHeight: "100%", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <p style={{ marginBottom: "1rem" }}>
          <Link to="/login">← Email / password sign-in</Link>
        </p>
        <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" fallbackRedirectUrl="/" />
      </div>
    </div>
  );
}
