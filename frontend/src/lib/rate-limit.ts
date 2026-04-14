/**
 * Parse FastAPI 429 responses from org-tier Redis limits (Upstash-compatible backend).
 * Body shape: `{ "detail": { "error": "rate_limit_exceeded", "limit", "remaining", "resetAt" } }`
 */

export type RateLimitDetail = {
  error: "rate_limit_exceeded";
  limit: number;
  remaining: number;
  resetAt: string;
};

export class RateLimitExceededError extends Error {
  readonly limit: number;
  readonly remaining: number;
  readonly resetAt: Date;
  readonly retryAfterSeconds: number | null;

  constructor(detail: RateLimitDetail, retryAfterSeconds: number | null, message?: string) {
    super(message ?? "Rate limit exceeded");
    this.name = "RateLimitExceededError";
    this.limit = detail.limit;
    this.remaining = detail.remaining;
    this.resetAt = new Date(detail.resetAt);
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function parseRateLimitDetail(detail: unknown): RateLimitDetail | null {
  if (!isRecord(detail)) return null;
  if (detail.error !== "rate_limit_exceeded") return null;
  const limit = Number(detail.limit);
  const remaining = Number(detail.remaining);
  const resetAt = detail.resetAt;
  if (!Number.isFinite(limit) || !Number.isFinite(remaining) || typeof resetAt !== "string") {
    return null;
  }
  return { error: "rate_limit_exceeded", limit, remaining, resetAt };
}

/** Axios/fetch response: status 429 and JSON body with FastAPI `detail` object. */
export function rateLimitFromHttpResponse(
  status: number,
  body: unknown,
  retryAfterHeader?: string | null,
): RateLimitExceededError | null {
  if (status !== 429) return null;
  if (!isRecord(body)) return null;
  const parsed = parseRateLimitDetail(body.detail);
  if (!parsed) return null;
  const ra = retryAfterHeader?.trim();
  const retryAfterSeconds = ra && /^\d+$/.test(ra) ? parseInt(ra, 10) : null;
  return new RateLimitExceededError(parsed, retryAfterSeconds);
}
