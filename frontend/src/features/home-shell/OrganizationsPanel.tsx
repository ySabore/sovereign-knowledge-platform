import type { CSSProperties, ReactNode } from "react";
import { OrganizationSettingsPanel } from "../organization-settings/OrganizationSettingsPanel";
import { OrganizationSelect } from "../scope-select/OrganizationSelect";
import { useOrgShellTokens } from "../../context/OrgShellThemeContext";
import { BackNavButton } from "./BackNavButton";
import type { OrgChatProvider, Workspace } from "./types";
import type { OrganizationsPanelProps } from "./contracts";

function Btn({
  children,
  variant = "primary",
  onClick,
  disabled,
  style,
  htmlType = "button",
}: {
  children: ReactNode;
  variant?: "primary" | "ghost";
  onClick?: () => void;
  disabled?: boolean;
  style?: CSSProperties;
  htmlType?: "button" | "submit";
}) {
  const C = useOrgShellTokens();
  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "6px 13px",
    borderRadius: 7,
    fontSize: 11,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: C.sans,
    transition: "all .14s",
    opacity: disabled ? 0.5 : 1,
    border: "none",
  };
  const styles: Record<string, CSSProperties> = {
    primary: { background: C.accent, color: "white", boxShadow: `0 0 16px ${C.accentG}` },
    ghost: { background: "transparent", color: C.t2, border: `1px solid ${C.bd2}` },
  };
  return (
    <button type={htmlType} style={{ ...base, ...styles[variant], ...style }} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function Input({
  value,
  onChange,
  placeholder,
  required,
  disabled,
  style,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  style?: CSSProperties;
}) {
  const C = useOrgShellTokens();
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 7,
        padding: "7px 10px",
        fontSize: 12,
        color: C.t1,
        fontFamily: C.sans,
        outline: "none",
        width: "100%",
        opacity: disabled ? 0.55 : 1,
        ...style,
      }}
    />
  );
}

export function OrganizationsPanel({
  user,
  orgs,
  selectedOrgId,
  isPlatformOwner,
  navigationScope,
  orgScreen,
  workspaces,
  loading,
  loadingWs,
  err,
  showCreateOrg,
  creating,
  newName,
  newSlug,
  newOrgChatProv,
  newOrgChatModel,
  newOrgOllamaBase,
  setShowCreateOrg,
  setNewName,
  setNewSlug,
  setNewOrgChatProv,
  setNewOrgChatModel,
  setNewOrgOllamaBase,
  setOrgScreen,
  setUploadWs,
  setWorkspaces,
  setAllWorkspaces,
  setJumpToWsId,
  setWorkspacesReloadNonce,
  setOrgs,
  setPanel,
  createOrg,
  enterOrganization,
  exitToPlatform,
  loadOrgs,
  api,
  OrgDetailView,
  onLaunchWorkspaceChat,
}: OrganizationsPanelProps) {
  const C = useOrgShellTokens();
  const selectStyle: CSSProperties = {
    width: "100%",
    background: C.bgCard,
    border: `1px solid ${C.bd}`,
    borderRadius: 8,
    padding: "7px 10px",
    fontSize: 12,
    color: C.t1,
    fontFamily: C.sans,
    boxSizing: "border-box",
  };

  return (
    <div style={{ padding: "22px 26px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 22 }}>
        <div>
          <div style={{ fontFamily: C.serif, fontSize: 24, color: C.t1, marginBottom: 4 }}>
            Organizations
          </div>
          <div style={{ fontSize: 12, color: C.t2 }}>
            Select an organization to view its details, workspaces, and settings.
          </div>
        </div>
        {user?.is_platform_owner && (
          <Btn variant="primary" onClick={() => setShowCreateOrg((v) => !v)}>
            {showCreateOrg ? "✕ Cancel" : "+ New Organization"}
          </Btn>
        )}
      </div>

      {err && (
        <div style={{ padding: "10px 14px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8, fontSize: 12, color: C.red, marginBottom: 16 }}>
          {err}
        </div>
      )}

      {showCreateOrg && user?.is_platform_owner && (
        <form onSubmit={createOrg} style={{
          background: C.bgCard, border: `1px solid rgba(37,99,235,0.35)`,
          borderRadius: 14, padding: "20px 22px", marginBottom: 20,
          boxShadow: "0 0 32px rgba(37,99,235,0.08)",
        }}>
          <div style={{ fontFamily: C.serif, fontSize: 18, color: C.t1, marginBottom: 16 }}>
            New Organization
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
            <Input value={newName} onChange={setNewName} placeholder="Acme Corp" required />
            <Input
              value={newSlug}
              onChange={(v) => setNewSlug(v.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
              placeholder="acme-corp"
              required
            />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <select
              value={newOrgChatProv}
              onChange={(e) => setNewOrgChatProv(e.target.value as OrgChatProvider)}
              style={selectStyle}
            >
              <option value="ollama">Ollama (self-hosted)</option>
              <option value="">Platform default (.env)</option>
              <option value="extractive">Extractive only</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
            <Input
              value={newOrgChatModel}
              onChange={setNewOrgChatModel}
              placeholder="e.g. llama3.2"
              disabled={newOrgChatProv === "extractive"}
            />
          </div>
          <Input
            value={newOrgOllamaBase}
            onChange={setNewOrgOllamaBase}
            placeholder="http://host.docker.internal:11434"
            disabled={
              newOrgChatProv === "extractive" ||
              newOrgChatProv === "openai" ||
              newOrgChatProv === "anthropic"
            }
          />
          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <Btn htmlType="submit" disabled={creating}>
              {creating ? "Creating…" : "Create organization"}
            </Btn>
            <Btn variant="ghost" onClick={() => setShowCreateOrg(false)}>
              Cancel
            </Btn>
          </div>
        </form>
      )}

      {!loading && orgs.length > 0 && (() => {
        const org = orgs.find((o) => o.id === selectedOrgId);
        return (
          <>
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.t3, marginBottom: 10 }}>
                Select Organization
              </div>
              <OrganizationSelect
                orgs={orgs}
                selectedId={selectedOrgId}
                allowEmpty={isPlatformOwner && navigationScope === "platform"}
                showBackToPlatform={isPlatformOwner && navigationScope === "organization"}
                onBackToPlatform={() => {
                  exitToPlatform();
                  setPanel("platform");
                }}
                onSelect={(id) => enterOrganization(id)}
              />
            </div>

            <div style={{ height: 1, background: C.bd, marginBottom: 24 }} />

            {!org && isPlatformOwner && navigationScope === "platform" && (
              <div style={{ fontSize: 13, color: C.t2, marginBottom: 16 }}>
                Choose an organization above to see details, workspaces, and actions for that org.
              </div>
            )}
            {org && (
              <>
                {orgScreen !== "overview" && (
                  <BackNavButton onClick={() => setOrgScreen("overview")}>
                    ← Back to organization
                  </BackNavButton>
                )}
                {orgScreen === "overview" && (
                  <OrgDetailView
                    org={org}
                    workspaces={workspaces}
                    loadingWs={loadingWs}
                    onOpenSettings={() => setOrgScreen("settings")}
                    onUploadClick={(ws) => setUploadWs(ws)}
                    onWorkspaceCreated={(wsId) => {
                      api.get<Workspace[]>(`/workspaces/org/${selectedOrgId}`)
                        .then(({ data }) => {
                          setWorkspaces(data);
                          setAllWorkspaces((prev) => {
                            const rest = prev.filter((w) => w.organization_id !== selectedOrgId);
                            return [...rest, ...data];
                          });
                        })
                        .catch(() => {});
                      if (wsId) { setJumpToWsId(wsId); setPanel("workspaces"); }
                    }}
                    onGoToWorkspace={(wsId) => {
                      if (wsId) setJumpToWsId(wsId);
                      setPanel("workspaces");
                    }}
                    onLaunchWorkspaceChat={onLaunchWorkspaceChat}
                    onNavigateToWorkspaces={() => setPanel("workspaces")}
                    onNavigateToTeam={() => setPanel("team")}
                    onNavigateToDocuments={() => setPanel("docs")}
                    onNavigateToConnectors={() => setPanel("connectors")}
                  />
                )}
                {orgScreen === "settings" && (
                  <OrganizationSettingsPanel
                    org={org}
                    canManageCloudCredentials={
                      Boolean(user?.is_platform_owner) ||
                      Boolean(user?.org_ids_as_owner?.includes(selectedOrgId))
                    }
                    showDangerZone={!!user?.is_platform_owner}
                    onSaved={(updated) => {
                      setOrgs((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
                    }}
                    onOrgDeleted={async () => {
                      await loadOrgs();
                      exitToPlatform();
                      setPanel("platform");
                      setWorkspacesReloadNonce((n) => n + 1);
                    }}
                  />
                )}
              </>
            )}
          </>
        );
      })()}
    </div>
  );
}
