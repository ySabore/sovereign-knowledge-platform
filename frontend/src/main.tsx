import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ClerkAuthRoot } from "./clerk/ClerkAuthRoot";
import { clerkEnabled } from "./lib/clerkEnv";
import App from "./App";
import "./index.css";

function RootTree() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        {clerkEnabled ? (
          <ClerkAuthRoot />
        ) : (
          <AuthProvider>
            <App />
          </AuthProvider>
        )}
      </BrowserRouter>
    </ErrorBoundary>
  );
}

function maybeWrapWithStrictMode(node: ReactNode) {
  // Clerk sign-in can trigger duplicate verification-code sends when mounted twice by StrictMode in dev.
  if (clerkEnabled) return node;
  return <StrictMode>{node}</StrictMode>;
}

createRoot(document.getElementById("root")!).render(maybeWrapWithStrictMode(<RootTree />));
