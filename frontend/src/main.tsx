import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ClerkAuthRoot } from "./clerk/ClerkAuthRoot";
import { clerkEnabled } from "./lib/clerkEnv";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
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
  </StrictMode>,
);
