import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { parseRateLimitDetail } from "../lib/rate-limit";
import { ensureFreshClerkTokenIfNeeded, forceRefreshClerkToken } from "../lib/clerkTokenBridge";

const baseURL = import.meta.env.VITE_API_BASE?.trim() || "/api";

export const api = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use(async (config) => {
  await ensureFreshClerkTokenIfNeeded();
  const token = localStorage.getItem("skp_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  return config;
});

type RetryConfig = InternalAxiosRequestConfig & { _skpClerk401Retry?: boolean };

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const config = error.config as RetryConfig | undefined;
    if (!config || status !== 401) return Promise.reject(error);

    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
    const msg = typeof detail === "string" ? detail : "";
    const looksLikeClerkJwtExpiry =
      msg.includes("Session expired") ||
      msg.includes("Clerk session token") ||
      msg.includes("new Clerk session");

    if (!looksLikeClerkJwtExpiry || config._skpClerk401Retry) {
      return Promise.reject(error);
    }

    await forceRefreshClerkToken();
    config._skpClerk401Retry = true;
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${localStorage.getItem("skp_token") ?? ""}`;
    return api.request(config);
  },
);

/** Clerk throws this when the Frontend API call fails (network, blockers, bad key), not our FastAPI. */
function formatClerkClientError(err: object): string | null {
  const e = err as {
    code?: string;
    name?: string;
    message?: string;
    status?: number;
    clerkTraceId?: string;
    errors?: Array<{ message?: string; longMessage?: string }>;
  };
  const msg = e.message?.trim() ?? "";
  const looksClerk =
    e.code === "api_response_error" ||
    e.name === "ClerkAPIResponseError" ||
    msg.includes("api_response_error") ||
    msg.includes('code="api_response_error"');
  if (!looksClerk) return null;

  const head = msg || "Clerk could not complete the request.";
  const sub = e.errors?.[0];
  const extra =
    sub?.longMessage?.trim() && sub.longMessage !== e.message
      ? sub.longMessage.trim()
      : sub?.message?.trim() && sub.message !== e.message
        ? sub.message.trim()
        : "";
  const meta = [
    typeof e.status === "number" ? `HTTP ${e.status}` : "",
    e.clerkTraceId ? `trace ${e.clerkTraceId}` : "",
  ]
    .filter(Boolean)
    .join(", ");

  const hint =
    "This is a Clerk session/API issue (not your app API). Check ad blockers, VPN, offline mode, " +
    "that requests to your Clerk domain are allowed, and that VITE_CLERK_PUBLISHABLE_KEY matches the dashboard.";

  return ["Clerk:", head, extra, meta ? `(${meta})` : "", hint].filter(Boolean).join(" ");
}

function collectErrorChain(err: unknown): unknown[] {
  const out: unknown[] = [];
  let cur: unknown = err;
  const seen = new Set<unknown>();
  while (cur && typeof cur === "object" && !seen.has(cur)) {
    seen.add(cur);
    out.push(cur);
    cur = (cur as { cause?: unknown }).cause;
  }
  return out;
}

export function apiErrorMessage(err: unknown): string {
  if (!err || typeof err !== "object") return "Request failed";

  for (const link of collectErrorChain(err)) {
    if (link && typeof link === "object") {
      const clerkMsg = formatClerkClientError(link as object);
      if (clerkMsg) return clerkMsg;
    }
  }

  const ax = err as AxiosError<{ detail?: string | { msg: string }[] | Record<string, unknown> }>;
  const d = ax.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join("; ");
  const rl = parseRateLimitDetail(d);
  if (rl) {
    return `Rate limit exceeded (limit ${rl.limit}; resets ${rl.resetAt})`;
  }

  const status = ax.response?.status;
  const statusText = ax.response?.statusText;
  const code = ax.code;

  if (!ax.response) {
    const msgStr = typeof ax.message === "string" ? ax.message : "";
    const codeStr = typeof code === "string" ? code : "";
    const looksLikeClerkTransport =
      codeStr === "api_response_error" ||
      msgStr.includes("api_response_error") ||
      `${msgStr} ${codeStr}`.includes("api_response_error");
    if (looksLikeClerkTransport) {
      for (const link of collectErrorChain(err)) {
        if (link && typeof link === "object") {
          const cm = formatClerkClientError(link as object);
          if (cm) return cm;
        }
      }
      return (
        "Clerk could not refresh your session (api_response_error) before this request reached the app API. " +
        "Check the browser Network tab for blocked calls to Clerk, VPN/ad blockers, and that VITE_CLERK_PUBLISHABLE_KEY matches your instance. " +
        "If you only use email/password login, rebuild the latest frontend (HS256 tokens skip Clerk refresh) or remove VITE_CLERK_PUBLISHABLE_KEY from the web build."
      );
    }
    const parts = [ax.message || "No response from server"];
    if (code) parts.push(`(${code})`);
    if (!ax.message && typeof navigator !== "undefined" && !navigator.onLine) {
      parts.push("You appear to be offline.");
    }
    return parts.join(" ");
  }

  const bodyUnknown = ax.response.data as unknown;
  if (typeof bodyUnknown === "string" && bodyUnknown.trim()) {
    const snippet = bodyUnknown.length > 200 ? `${bodyUnknown.slice(0, 200)}…` : bodyUnknown;
    return status ? `HTTP ${status}: ${snippet}` : snippet;
  }

  const base = (typeof ax.message === "string" ? ax.message.trim() : "") || "Request failed";
  if (status) {
    return statusText ? `${base} (HTTP ${status} ${statusText})` : `${base} (HTTP ${status})`;
  }
  return base;
}
