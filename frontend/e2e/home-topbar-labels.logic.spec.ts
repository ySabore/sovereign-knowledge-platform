import { expect, test } from "@playwright/test";
import { getPanelDisplayLabel } from "../src/features/home-shell/homeTopBarLabels";

test("uses workspace-aware label for team panel", () => {
  expect(
    getPanelDisplayLabel({
      panel: "team",
      ctxWorkspaceName: "Litigation",
      chatWorkspaceId: null,
    }),
  ).toBe("Team · Litigation");
});

test("uses conversation label for embedded chat", () => {
  expect(
    getPanelDisplayLabel({
      panel: "chats",
      ctxWorkspaceName: null,
      chatWorkspaceId: "ws-1",
    }),
  ).toBe("Chats · Conversation");
});

test("falls back to default docs label", () => {
  expect(
    getPanelDisplayLabel({
      panel: "docs",
      ctxWorkspaceName: null,
      chatWorkspaceId: null,
    }),
  ).toBe("Documents");
});
