/**
 * Session id used to reload chat history after a turn.
 *
 * `send()` is created on the render where the user clicked Send. For a brand-new
 * conversation that closure still has `activeSessionId === null`. Prefer the id
 * returned by session creation (or the live ref) so we do not treat the thread
 * as empty and wipe the UI after a successful stream.
 */
export function resolveChatHistorySessionId(options: {
  explicitId?: string | null;
  liveId: string | null;
}): string | null {
  const explicit = options.explicitId;
  if (typeof explicit === "string" && explicit.length > 0) {
    return explicit;
  }
  return options.liveId;
}
