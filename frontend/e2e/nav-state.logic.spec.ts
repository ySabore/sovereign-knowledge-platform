import { expect, test } from "@playwright/test";
import { buildNavGroups, getNavLockState } from "../src/features/home-shell/useHomeNavState";
import { shouldRedirectEmptyOrgToDocs } from "../src/features/home-shell/useOrgKnowledgeGate";

test("buildNavGroups includes platform section for platform owner", () => {
  const groups = buildNavGroups(true, true, true, true, "DASH");
  expect(groups[0]?.label).toBe("Platform");
  expect(groups.some((g) => g.items.some((i) => i.id === "platform"))).toBe(true);
});

test("buildNavGroups omits platform section for non-owner", () => {
  const groups = buildNavGroups(false, false, false, false, "DASH");
  expect(groups.some((g) => g.label === "Platform")).toBe(false);
});

test("getNavLockState marks org-scoped panel as locked without org context", () => {
  const lock = getNavLockState("workspaces", true, "", null, false);
  expect(lock.orgLocked).toBe(true);
  expect(lock.navDisabled).toBe(true);
  expect(lock.title).toContain("Select an organization");
});

test("getNavLockState marks knowledge panel as locked when no indexed docs", () => {
  const lock = getNavLockState("team", false, "org-123", false, false);
  expect(lock.knowledgeLocked).toBe(true);
  expect(lock.navDisabled).toBe(true);
  expect(lock.title).toContain("Index at least one document");
});

test("empty-org knowledge gate still sends admins from chats to documents", () => {
  expect(
    shouldRedirectEmptyOrgToDocs({
      isPlatformOwner: false,
      memberChatOnly: false,
      orgHasIndexedDocuments: false,
      panel: "chats",
      selectedOrgId: "org-123",
    }),
  ).toBe(true);
});

test("empty-org knowledge gate does not fight member chat-first landing", () => {
  expect(
    shouldRedirectEmptyOrgToDocs({
      isPlatformOwner: false,
      memberChatOnly: true,
      orgHasIndexedDocuments: false,
      panel: "chats",
      selectedOrgId: "org-123",
    }),
  ).toBe(false);
});

test("member chat-first and empty-org knowledge gate settle on chats", () => {
  let panel: "chats" | "docs" | "team" = "chats";
  const sequence: typeof panel[] = [];
  for (let i = 0; i < 6; i++) {
    if (
      shouldRedirectEmptyOrgToDocs({
        isPlatformOwner: false,
        memberChatOnly: true,
        orgHasIndexedDocuments: false,
        panel,
        selectedOrgId: "org-123",
      })
    ) {
      panel = "docs";
    } else if (panel !== "chats") {
      panel = "chats";
    }
    sequence.push(panel);
  }
  expect(sequence).toEqual(["chats", "chats", "chats", "chats", "chats", "chats"]);
});
