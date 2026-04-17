import { useMemo } from "react";
import type { ReactNode } from "react";
import type { Panel } from "./types";

export const KNOWLEDGE_GATED_PANELS: Panel[] = ["chats", "team"];

/** Panels that require an active org in platform-wide scope. */
export const ORG_SCOPED_PANELS: Panel[] = [
  "workspaces",
  "chats",
  "team",
  "analytics",
  "docs",
  "connectors",
  "billing",
  "audit",
  "settings",
];

export type NavItem = {
  id: Panel | null;
  icon: ReactNode;
  label: string;
  badge?: number;
  badgeVariant?: "accent" | "danger";
  href?: string;
  disabled?: boolean;
  title?: string;
};

export type NavGroup = {
  label: string;
  items: NavItem[];
};

export function buildNavGroups(
  userIsPlatformOwner: boolean,
  canViewBilling: boolean,
  canViewAudit: boolean,
  canViewSettings: boolean,
  dashNavIcon: ReactNode,
): NavGroup[] {
  const enterpriseItems: NavItem[] = [];
  if (canViewBilling) enterpriseItems.push({ id: "billing", icon: "\u{1F4B3}", label: "Billing" });
  if (canViewAudit) enterpriseItems.push({ id: "audit", icon: "\u{1F6E1}", label: "Audit Log" });
  if (canViewSettings) enterpriseItems.push({ id: "settings", icon: "\u{2699}\u{FE0F}", label: "Settings" });

  const enterpriseGroup: NavGroup[] =
    enterpriseItems.length > 0
      ? [
          {
            label: "Enterprise",
            items: enterpriseItems,
          },
        ]
      : [];

  return userIsPlatformOwner
    ? [
        {
          label: "Platform",
          items: [{ id: "platform", icon: "\u{1F310}", label: "Overview" }],
        },
        {
          label: "Core app",
          items: [
            { id: "dashboard", icon: dashNavIcon, label: "Dashboard" },
            { id: "orgs", icon: "\u{1F3E2}", label: "Organizations" },
            { id: "workspaces", icon: "\u{2B21}", label: "Workspaces" },
            { id: "chats", icon: "\u{1F4AC}", label: "Chats" },
          ],
        },
        {
          label: "Knowledge",
          items: [
            { id: "team", icon: "\u{1F465}", label: "Team", badge: 12 },
            { id: "analytics", icon: "\u{1F4CA}", label: "Analytics" },
            { id: "docs", icon: "\u{1F4C4}", label: "Documents" },
            { id: "connectors", icon: "\u{1F50C}", label: "Connectors", badge: 1, badgeVariant: "danger" },
          ],
        },
        ...enterpriseGroup,
      ]
    : [
        {
          label: "Core app",
          items: [
            { id: "dashboard", icon: dashNavIcon, label: "Dashboard" },
            { id: "orgs", icon: "\u{1F3E2}", label: "Organizations" },
            { id: "workspaces", icon: "\u{2B21}", label: "Workspaces" },
            { id: "chats", icon: "\u{1F4AC}", label: "Chats" },
          ],
        },
        {
          label: "Knowledge",
          items: [
            { id: "team", icon: "\u{1F465}", label: "Team", badge: 12 },
            { id: "analytics", icon: "\u{1F4CA}", label: "Analytics" },
            { id: "docs", icon: "\u{1F4C4}", label: "Documents" },
            { id: "connectors", icon: "\u{1F50C}", label: "Connectors", badge: 1, badgeVariant: "danger" },
          ],
        },
        ...enterpriseGroup,
      ];
}

export function getNavLockState(
  panelId: Panel | null,
  needsOrganizationContext: boolean,
  selectedOrgId: string,
  orgHasIndexedDocuments: boolean | null,
  isPlatformOwner: boolean,
) {
  const orgLocked = Boolean(panelId && ORG_SCOPED_PANELS.includes(panelId) && needsOrganizationContext);
  const knowledgeLocked = Boolean(
    panelId &&
      KNOWLEDGE_GATED_PANELS.includes(panelId) &&
      selectedOrgId &&
      orgHasIndexedDocuments !== true &&
      !isPlatformOwner,
  );

  return {
    orgLocked,
    knowledgeLocked,
    navDisabled: orgLocked || knowledgeLocked,
    title: orgLocked
      ? "Select an organization from Platform overview or Organizations first"
      : knowledgeLocked
        ? "Index at least one document under Documents (any workspace) before Chats and Team"
        : undefined,
  };
}

type UseHomeNavStateArgs = {
  userIsPlatformOwner: boolean;
  canViewBilling: boolean;
  canViewAudit: boolean;
  canViewSettings: boolean;
  dashNavIcon: ReactNode;
  needsOrganizationContext: boolean;
  selectedOrgId: string;
  orgHasIndexedDocuments: boolean | null;
  isPlatformOwner: boolean;
  ctxWorkspaceId: string | null | undefined;
  setJumpToChatWsId: (id: string | undefined) => void;
  setChatWorkspaceId: (id: string | null) => void;
  setPanel: (panel: Panel) => void;
  navigate: (href: string) => void;
};

export function useHomeNavState({
  userIsPlatformOwner,
  canViewBilling,
  canViewAudit,
  canViewSettings,
  dashNavIcon,
  needsOrganizationContext,
  selectedOrgId,
  orgHasIndexedDocuments,
  isPlatformOwner,
  ctxWorkspaceId,
  setJumpToChatWsId,
  setChatWorkspaceId,
  setPanel,
  navigate,
}: UseHomeNavStateArgs) {
  const navGroups = useMemo(
    () => buildNavGroups(userIsPlatformOwner, canViewBilling, canViewAudit, canViewSettings, dashNavIcon),
    [userIsPlatformOwner, canViewBilling, canViewAudit, canViewSettings, dashNavIcon],
  );

  const onSelectNavItem = (item: NavItem) => {
    if (item.href) {
      navigate(item.href);
      return;
    }
    if (!item.id) return;

    const { orgLocked, knowledgeLocked } = getNavLockState(
      item.id,
      needsOrganizationContext,
      selectedOrgId,
      orgHasIndexedDocuments,
      isPlatformOwner,
    );
    if (orgLocked || knowledgeLocked) return;

    if (item.id === "chats") {
      setJumpToChatWsId(undefined);
      setChatWorkspaceId(ctxWorkspaceId ?? null);
    }
    setPanel(item.id);
  };

  return { navGroups, onSelectNavItem };
}
