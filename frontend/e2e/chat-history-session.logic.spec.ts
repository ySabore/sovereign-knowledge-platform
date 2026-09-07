import { expect, test } from "@playwright/test";
import { resolveChatHistorySessionId } from "../src/lib/chatHistorySession";

test("first message of a new conversation uses the created session id, not the stale null", () => {
  expect(resolveChatHistorySessionId({ explicitId: "sess-1", liveId: null })).toBe("sess-1");
});

test("falls back to the live session id when send() did not pass an explicit id", () => {
  expect(resolveChatHistorySessionId({ liveId: "sess-2" })).toBe("sess-2");
});

test("clears history when there is no session", () => {
  expect(resolveChatHistorySessionId({ liveId: null })).toBeNull();
  expect(resolveChatHistorySessionId({ explicitId: "", liveId: null })).toBeNull();
});
