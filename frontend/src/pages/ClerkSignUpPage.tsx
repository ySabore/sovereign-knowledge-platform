import { SignUp } from "@clerk/clerk-react";
import { Link, useSearchParams } from "react-router-dom";

export function ClerkSignUpPage() {
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/onboarding";
  return (
    <div style={{ minHeight: "100%", display: "grid", placeItems: "center", padding: "2rem" }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <p style={{ marginBottom: "1rem" }}>
          <Link to={`/login${redirectTo ? `?redirect=${encodeURIComponent(redirectTo)}` : ""}`}>← Email / password sign-in</Link>
        </p>
        <SignUp
          routing="path"
          path="/sign-up"
          signInUrl={`/sign-in${redirectTo ? `?redirect=${encodeURIComponent(redirectTo)}` : ""}`}
          fallbackRedirectUrl={redirectTo}
        />
      </div>
    </div>
  );
}
