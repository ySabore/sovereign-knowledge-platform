import { DashboardPage } from "../../pages/app/DashboardPage";
import { DocumentsPanel } from "../documents/DocumentsPanel";
import { KnowledgeAnalyticsPanel } from "../../components/KnowledgeAnalyticsPanel";
import { OrgDashboardAnalytics } from "../../components/OrgDashboardAnalytics";
import { PlatformOwnerDashboard } from "../../components/PlatformOwnerDashboard";
import { TeamManagementPanel } from "../../components/TeamManagementPanel";
import { OrganizationsPanel } from "./OrganizationsPanel";
import type { HomePanelRouterProps } from "./contracts";

export function HomePanelRouter(props: HomePanelRouterProps) {
  const {
    panel,
    user,
    orgs,
    allWorkspaces,
    workspaceCountByOrg,
    loading,
    enterOrganization,
    setPanel,
    selectedOrgId,
    navigate,
    showCreateOrg,
    setShowCreateOrg,
    err,
    createOrg,
    creating,
    newName,
    setNewName,
    newSlug,
    setNewSlug,
    newOrgChatProv,
    setNewOrgChatProv,
    newOrgChatModel,
    setNewOrgChatModel,
    newOrgOllamaBase,
    setNewOrgOllamaBase,
    isPlatformOwner,
    navigationScope,
    exitToPlatform,
    orgScreen,
    setOrgScreen,
    workspaces,
    loadingWs,
    setUploadWs,
    api,
    AllWorkspacesPanel,
    OrgDetailView,
    setWorkspaces,
    setAllWorkspaces,
    setJumpToWsId,
    setWorkspacesReloadNonce,
    loadOrgs,
    setActiveWorkspaceContext,
    scopedWorkspaces,
    ctxWorkspaceId,
    jumpToWsId,
    chatWorkspaceId,
    setChatWorkspaceId,
    brightMode,
    onEmbeddedChatWorkspaceChange,
    ChatsPanel,
    jumpToChatWsId,
    ConnectorsPanel,
    workspaceInContext,
    BillingPanel,
    AuditPanel,
    workspaceScopeIds,
    canManageOrgSettings,
    canManageWorkspaceSettings,
    SettingsPanel,
    uploadWs,
    UploadModal,
    setOrgs,
    setErr,
  } = props;
  return (
    <>
      {panel === "platform" && user?.is_platform_owner && (
        <PlatformOwnerDashboard
          orgs={orgs}
          totalWorkspaces={allWorkspaces.length}
          workspaceCountByOrg={workspaceCountByOrg}
          loadingOrgs={loading}
          onEnterOrganization={(id) => {
            enterOrganization(id);
            setPanel("dashboard");
          }}
          onOpenOrganizationsNav={() => setPanel("orgs")}
        />
      )}

      {panel === "dashboard" && (
        <OrgDashboardAnalytics
          organizationId={selectedOrgId || null}
          orgDisplayName={
            (selectedOrgId && orgs.find((o) => o.id === selectedOrgId)?.name)
            ?? "Organization"
          }
          onInviteTeam={() => setPanel("team")}
          onOpenOrganizations={() => setPanel("orgs")}
        />
      )}

      {panel === "orgs" && (
        <OrganizationsPanel
          user={user}
          orgs={orgs}
          selectedOrgId={selectedOrgId}
          isPlatformOwner={isPlatformOwner}
          navigationScope={navigationScope}
          orgScreen={orgScreen}
          workspaces={workspaces}
          loading={loading}
          loadingWs={loadingWs}
          err={err}
          showCreateOrg={showCreateOrg}
          creating={creating}
          newName={newName}
          newSlug={newSlug}
          newOrgChatProv={newOrgChatProv}
          newOrgChatModel={newOrgChatModel}
          newOrgOllamaBase={newOrgOllamaBase}
          setShowCreateOrg={setShowCreateOrg}
          setNewName={setNewName}
          setNewSlug={setNewSlug}
          setNewOrgChatProv={setNewOrgChatProv}
          setNewOrgChatModel={setNewOrgChatModel}
          setNewOrgOllamaBase={setNewOrgOllamaBase}
          setOrgScreen={setOrgScreen}
          setUploadWs={setUploadWs}
          setWorkspaces={setWorkspaces}
          setAllWorkspaces={setAllWorkspaces}
          setJumpToWsId={setJumpToWsId}
          setWorkspacesReloadNonce={setWorkspacesReloadNonce}
          setOrgs={setOrgs}
          setPanel={setPanel}
          createOrg={createOrg}
          enterOrganization={enterOrganization}
          exitToPlatform={exitToPlatform}
          loadOrgs={loadOrgs}
          api={api}
          OrgDetailView={OrgDetailView}
        />
      )}

      {panel === "workspaces" && (
        <AllWorkspacesPanel
          orgs={orgs}
          allWorkspaces={scopedWorkspaces}
          loadingWs={loadingWs}
          initialWsId={ctxWorkspaceId ?? jumpToWsId}
          isPlatformOwner={!!isPlatformOwner}
          onWorkspaceDeleted={async () => {
            setWorkspacesReloadNonce((n) => n + 1);
            setActiveWorkspaceContext(null, null);
          }}
          onSelectedWorkspaceChange={setActiveWorkspaceContext}
          onLaunchChat={(wsId) => {
            setChatWorkspaceId(wsId);
            setPanel("chats");
          }}
          onNavigateToTeam={() => setPanel("team")}
          onNavigateToConnectors={() => setPanel("connectors")}
          onWorkspaceUpdated={(updated) => {
            setAllWorkspaces((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
            if (updated.organization_id) {
              setWorkspaces((prev) => prev.map((w) => (w.id === updated.id ? updated : w)));
            }
          }}
        />
      )}

      {panel === "chats" && chatWorkspaceId && (
        <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <DashboardPage
            key={chatWorkspaceId}
            embedded
            embeddedBright={brightMode}
            workspaceId={chatWorkspaceId}
            onEmbeddedWorkspaceChange={onEmbeddedChatWorkspaceChange}
          />
        </div>
      )}
      {panel === "chats" && !chatWorkspaceId && (
        <ChatsPanel
          allWorkspaces={scopedWorkspaces}
          initialWsId={jumpToChatWsId}
          onOpenChat={(id) => setChatWorkspaceId(id)}
        />
      )}

      {panel === "connectors" && (
        <ConnectorsPanel orgs={orgs} workspaceScope={workspaceInContext} />
      )}

      {panel === "team" && (
        <TeamManagementPanel
          initialOrgId={(workspaceInContext?.organization_id || selectedOrgId) || undefined}
          scopedWorkspaceId={workspaceInContext?.id ?? null}
          scopedWorkspaceName={workspaceInContext?.name ?? null}
        />
      )}

      {panel === "analytics" && (
        <KnowledgeAnalyticsPanel
          organizationId={selectedOrgId || null}
          workspaceName={workspaceInContext?.name ?? null}
          organizationName={
            selectedOrgId ? orgs.find((o) => o.id === selectedOrgId)?.name ?? null : null
          }
        />
      )}

      {panel === "docs" && (
        <DocumentsPanel orgs={orgs} scopeOrganizationId={selectedOrgId || null} />
      )}

      {panel === "billing" && <BillingPanel />}

      {panel === "audit" && (
        <AuditPanel
          orgs={orgs}
          selectedOrgId={selectedOrgId}
          workspaceScopeIds={workspaceScopeIds}
        />
      )}

      {panel === "settings" && (
        <SettingsPanel
          orgs={orgs}
          selectedOrgId={selectedOrgId}
          onSelectOrg={(orgId) => {
            if (!orgId) {
              setErr("Select an organization to open settings.");
              return;
            }
            enterOrganization(orgId);
            setErr(null);
          }}
          onSavedOrg={(updated) => {
            setOrgs((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
          }}
          onSavedWorkspace={(updated) => {
            setWorkspaces((prev) => prev.map((ws) => (ws.id === updated.id ? updated : ws)));
            setAllWorkspaces((prev) => prev.map((ws) => (ws.id === updated.id ? updated : ws)));
          }}
          onOrgDeleted={async () => {
            await loadOrgs();
            setPanel("orgs");
          }}
          isPlatformOwner={isPlatformOwner}
          workspaces={scopedWorkspaces}
          canManageOrgSettings={canManageOrgSettings}
          canManageWorkspaceSettings={canManageWorkspaceSettings}
        />
      )}

      {uploadWs && <UploadModal ws={uploadWs} onClose={() => setUploadWs(null)} />}
    </>
  );
}
