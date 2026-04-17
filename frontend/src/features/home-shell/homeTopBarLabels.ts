import type { Panel } from "./types";

type LabelArgs = {
  panel: Panel;
  ctxWorkspaceName: string | null | undefined;
  chatWorkspaceId: string | null;
};

export function getPanelDisplayLabel({
  panel,
  ctxWorkspaceName,
  chatWorkspaceId,
}: LabelArgs): string {
  if (panel === "platform") return "Platform overview";
  if (panel === "dashboard") return "Dashboard";
  if (panel === "team") return ctxWorkspaceName ? `Team · ${ctxWorkspaceName}` : "Team";
  if (panel === "orgs") return "Organizations";
  if (panel === "workspaces") return "Workspaces";
  if (panel === "chats") return chatWorkspaceId ? "Chats · Conversation" : "Chats";
  if (panel === "analytics") return ctxWorkspaceName ? `Analytics · ${ctxWorkspaceName}` : "Analytics";
  if (panel === "connectors") return ctxWorkspaceName ? `Connectors · ${ctxWorkspaceName}` : "Connectors";
  if (panel === "billing") return "Billing";
  if (panel === "audit") return "Audit log";
  if (panel === "settings") return "Settings";
  return "Documents";
}
