/**
 * Lets the API client refresh the Clerk session JWT before requests / after401,
 * without importing Clerk in axios. ClerkTokenSync registers the refresh impl once mounted.
 */

import { notifySkpAuthChanged } from "./authEvents";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim());

let refreshImpl: (() => Promise<string | null>) | null = null;

/** Called from ClerkTokenSync — replaces prior impl when Clerk remounts. */
export function registerClerkTokenRefresh(fn: () => Promise<string | null>): void {
  refreshImpl = fn;
}

export function unregisterClerkTokenRefresh(): void {
  refreshImpl = null;
}

function decodeJwtPart(token: string, index: 0 | 1): Record<string, unknown> | null {
  try {
    const part = token.split(".")[index];
    if (!part) return null;
    const base64 = part.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "===".slice((base64.length + 3) % 4);
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function decodeJwtTimes(token: string): { exp: number; iat?: number } | null {
  const p = decodeJwtPart(token, 1);
  if (!p || typeof p.exp !== "number") return null;
  const iat = typeof p.iat === "number" ? p.iat : undefined;
  return { exp: p.exp, iat };
}

/**
 * How many seconds before `exp` we should mint a replacement.
 * Clerk default session *JWT* lifetimes are often 60s; refreshing only in the last 90s never triggers for those tokens.
 */
function clerkRefreshLeadSeconds(exp: number, iat: number | undefined): number {
  const ttlFull = iat != null ? Math.max(1, exp - iat) : 3600;
  if (ttlFull <= 120) {
    return Math.max(8, Math.floor(ttlFull * 0.33));
  }
  if (ttlFull <= 900) {
    return Math.max(30, Math.floor(ttlFull * 0.22));
  }
  return 120;
}

/**
 * Only the FastAPI password-login JWT uses HS256. Clerk session tokens use other algs (RS256, ES256, …).
 * We skip Clerk `getToken()` refresh for HS256 so email/password sessions are not broken when a publishable key is present. Everything else is refreshed like before the regression.
 */
export function skpTokenIsPasswordJwt(token: string | null): boolean {
  if (!token) return false;
  const h = decodeJwtPart(token, 0);
  return h?.alg === "HS256";
}

/**
 * True when the stored JWT should be rotated before the next API call.
 * - Password (HS256): refresh when within `withinSecondsForPassword` of exp (matches long-lived API tokens).
 * - Clerk session JWT: use a fraction of total lifetime so ~60s Clerk tokens refresh ~20s before exp, not “always” or “never”.
 */
export function skpTokenNeedsRefresh(withinSecondsForPassword = 120): boolean {
  const raw = localStorage.getItem("skp_token");
  if (!raw) return false;
  const times = decodeJwtTimes(raw);
  if (!times) return true;
  const now = Date.now() / 1000;
  const ttlRemaining = times.exp - now;
  if (ttlRemaining <= 0) return true;
  if (skpTokenIsPasswordJwt(raw)) {
    return ttlRemaining < withinSecondsForPassword;
  }
  const lead = clerkRefreshLeadSeconds(times.exp, times.iat);
  return ttlRemaining < lead;
}

/** Fetches a new Clerk JWT and stores it; no-op if Clerk is off or not registered. */
export async function ensureFreshClerkTokenIfNeeded(): Promise<void> {
  if (!clerkEnabled || !refreshImpl) return;
  const raw = localStorage.getItem("skp_token");
  if (!raw || skpTokenIsPasswordJwt(raw)) return;
  if (!skpTokenNeedsRefresh()) return;
  try {
    const t = await refreshImpl();
    if (t) {
      localStorage.setItem("skp_token", t);
      notifySkpAuthChanged();
    }
  } catch {
    /* Do not block the HTTP request if Clerk is unreachable; API may still accept the current JWT. */
  }
}

/** Force refresh (e.g. after 401). */
export async function forceRefreshClerkToken(): Promise<string | null> {
  if (!clerkEnabled || !refreshImpl) return null;
  const raw = localStorage.getItem("skp_token");
  if (!raw || skpTokenIsPasswordJwt(raw)) return null;
  try {
    const t = await refreshImpl();
    if (t) {
      localStorage.setItem("skp_token", t);
      notifySkpAuthChanged();
    }
    return t;
  } catch {
    return null;
  }
}
