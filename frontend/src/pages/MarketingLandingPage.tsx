import { useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import landingHtml from "../../../docs/sources/RefinedDocuments/landing-page.html?raw";
import { clerkEnabled } from "../lib/clerkEnv";

function wireLandingCtas(doc: Document, navigate: (to: string) => void) {
  const signInPath = clerkEnabled ? "/sign-in" : "/login";
  const signUpPath = clerkEnabled ? "/sign-up" : "/login";
  const targets = Array.from(doc.querySelectorAll("button,a"));
  for (const el of targets) {
    if (el.getAttribute("data-skp-wired") === "1") continue;
    const label = (el.textContent ?? "").trim().toLowerCase();
    if (label.includes("sign in")) {
      el.setAttribute("data-skp-wired", "1");
      el.addEventListener("click", (event) => {
        event.preventDefault();
        navigate(signInPath);
      });
      continue;
    }
    if (
      label.includes("request demo") ||
      label.includes("get started") ||
      label.includes("create account") ||
      label.includes("sign up")
    ) {
      el.setAttribute("data-skp-wired", "1");
      el.addEventListener("click", (event) => {
        event.preventDefault();
        navigate(signUpPath);
      });
    }
  }
}

export function MarketingLandingPage() {
  const navigate = useNavigate();
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const onIframeLoad = useCallback(() => {
    const doc = iframeRef.current?.contentDocument;
    if (!doc?.body) return;
    wireLandingCtas(doc, navigate);
  }, [navigate]);

  return (
    <iframe
      ref={iframeRef}
      title="SKP Landing Page"
      srcDoc={landingHtml}
      onLoad={onIframeLoad}
      style={{
        display: "block",
        width: "100%",
        height: "100%",
        minHeight: "100vh",
        border: "none",
        background: "#080c14",
      }}
    />
  );
}
