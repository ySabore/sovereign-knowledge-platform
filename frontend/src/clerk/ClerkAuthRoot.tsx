import { ClerkProvider, useAuth as useClerkSession, useClerk } from "@clerk/clerk-react";
import { useEffect, useRef, useState } from "react";
import { AuthProvider } from "../context/AuthContext";
import { SkeletonBlock } from "../components/Skeleton";
import { notifySkpAuthChanged } from "../lib/authEvents";
import {
  registerClerkTokenRefresh,
  skpTokenIsPasswordJwt,
  unregisterClerkTokenRefresh,
} from "../lib/clerkTokenBridge";
import { PLATFORM_DISPLAY_NAME } from "../lib/platformDisplayName";
import App from "../App";

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim() || "";

/** Overrides Clerk’s default “Sign in to {application name}” (Dashboard name may still be an old slug). */
const clerkLocalization = {
  signIn: {
    start: {
      title: `Sign in to ${PLATFORM_DISPLAY_NAME}`,
      titleCombined: `Sign in to ${PLATFORM_DISPLAY_NAME}`,
    },
  },
  signUp: {
    start: {
      title: `Sign up to ${PLATFORM_DISPLAY_NAME}`,
      titleCombined: `Sign up to ${PLATFORM_DISPLAY_NAME}`,
    },
  },
};

/** Writes Clerk session JWT into `skp_token` for the API client. */
function ClerkTokenSync() {
  const { isLoaded, isSignedIn, getToken } = useClerkSession();
  const getTokenRef = useRef(getToken);
  getTokenRef.current = getToken;

  useEffect(() => {
    if (!isLoaded) return;
    let cancelled = false;
    (async () => {
      const prev = localStorage.getItem("skp_token");
      if (isSignedIn) {
        try {
          const t = await getTokenRef.current();
          if (t) {
            localStorage.setItem("skp_token", t);
          } else {
            const cur = localStorage.getItem("skp_token");
            if (cur && !skpTokenIsPasswordJwt(cur)) {
              localStorage.removeItem("skp_token");
            }
          }
        } catch {
          /* Transient Clerk failure: keep token so the app keeps working; refresh runs again on the next call. */
        }
      } else {
        const raw = localStorage.getItem("skp_token");
        if (raw && !skpTokenIsPasswordJwt(raw)) {
          localStorage.removeItem("skp_token");
        }
      }
      if (cancelled) return;
      const next = localStorage.getItem("skp_token");
      if (prev !== next) notifySkpAuthChanged();
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoaded, isSignedIn]);

  /** Let axios refresh before API calls / retry after 401 (Clerk session JWTs are short-lived). */
  useEffect(() => {
    if (!isLoaded || !isSignedIn) {
      unregisterClerkTokenRefresh();
      return;
    }
    registerClerkTokenRefresh(async () => {
      try {
        return await getTokenRef.current({ skipCache: true });
      } catch {
        try {
          return await getTokenRef.current();
        } catch {
          return null;
        }
      }
    });
    return () => unregisterClerkTokenRefresh();
  }, [isLoaded, isSignedIn]);

  /** Proactive mint so `skp_token` does not sit past `exp` between API calls. */
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    const tick = async () => {
      try {
        const t = await getTokenRef.current({ skipCache: true });
        if (t) {
          const prev = localStorage.getItem("skp_token");
          localStorage.setItem("skp_token", t);
          if (prev !== t) notifySkpAuthChanged();
        }
      } catch {
        /* network / Clerk hiccup — next interval or request interceptor will retry */
      }
    };
    /* Short Clerk session JWTs (~60s) need frequent mints; 25s keeps ahead of exp without hammering getToken. */
    const id = window.setInterval(() => void tick(), 25_000);
    const onVis = () => {
      if (document.visibilityState === "visible") void tick();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [isLoaded, isSignedIn]);

  return null;
}

/**
 * Once Clerk reports `isLoaded`, keep rendering `<App />` even if `isLoaded` flickers false later.
 * Otherwise the whole tree unmount/remount feels like a full page reload.
 */
function ClerkLoadedShell() {
  const { isLoaded } = useClerkSession();
  const [clerkReady, setClerkReady] = useState(false);
  useEffect(() => {
    if (isLoaded) setClerkReady(true);
  }, [isLoaded]);

  if (!clerkReady) {
    return (
      <div style={{ padding: "2rem" }}>
        <p className="sk-muted" style={{ marginBottom: "1rem" }}>
          Loading…
        </p>
        <SkeletonBlock lines={4} />
      </div>
    );
  }
  return <App />;
}

function ClerkAuthInner() {
  const { signOut } = useClerk();
  return (
    <AuthProvider onClearExternalAuth={() => signOut()}>
      <ClerkTokenSync />
      <ClerkLoadedShell />
    </AuthProvider>
  );
}

export function ClerkAuthRoot() {
  if (!publishableKey) {
    return (
      <AuthProvider>
        <App />
      </AuthProvider>
    );
  }

  return (
    <ClerkProvider publishableKey={publishableKey} afterSignOutUrl="/login" localization={clerkLocalization}>
      <ClerkAuthInner />
    </ClerkProvider>
  );
}
