import { expect, test } from "@playwright/test";
import { buildNavGroups, getNavLockState } from "../src/features/home-shell/useHomeNavState";

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
