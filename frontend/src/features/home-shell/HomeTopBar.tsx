import { useOrgShellTokens } from "../../context/OrgShellThemeContext";
import type { NavigationScope, Panel, Workspace } from "./types";
import { getPanelDisplayLabel } from "./homeTopBarLabels";

type HomeTopBarProps = {
  panel: Panel;
  chatWorkspaceId: string | null;
  setChatWorkspaceId: (id: string | null) => void;
  scopedWorkspaces: Workspace[];
  ctxWorkspaceName: string | null | undefined;
  brightMode: boolean;
  setBrightMode: (updater: (v: boolean) => boolean) => void;
  initials: string;
  isPlatformOwner: boolean;
  navigationScope: NavigationScope;
  selectedOrgId: string;
  selectedOrgName: string | null;
  ctxWorkspaceId: string | null | undefined;
  exitToPlatform: () => void;
  setPanel: (panel: Panel) => void;
};

export function HomeTopBar({
  panel,
  chatWorkspaceId,
  setChatWorkspaceId,
  scopedWorkspaces,
  ctxWorkspaceName,
  brightMode,
  setBrightMode,
  initials,
  isPlatformOwner,
  navigationScope,
  selectedOrgId,
  selectedOrgName,
  ctxWorkspaceId,
  exitToPlatform,
  setPanel,
}: HomeTopBarProps) {
  const C = useOrgShellTokens();
  const panelLabel = getPanelDisplayLabel({ panel, ctxWorkspaceName, chatWorkspaceId });
  return (
    <>
      <div style={{
        height: 50, background: C.bgS, borderBottom: `1px solid ${C.bd}`,
        display: "flex", alignItems: "center", padding: "0 20px", gap: 12, flexShrink: 0,
      }}>
        {panel === "chats" && chatWorkspaceId && (
          <button
            type="button"
            className="skc-exit-embedded"
            onClick={() => setChatWorkspaceId(null)}
          >
            ← Chats
          </button>
        )}
        <div style={{ flex: 1, fontSize: 12, color: C.t3, display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            Platform /{" "}
            <span style={{ color: C.t1, fontWeight: 500 }}>
              {panelLabel}
            </span>
          </span>
          {panel === "chats" && chatWorkspaceId && scopedWorkspaces.length > 0 && (
            <select
              className="skc-workspace-select"
              value={chatWorkspaceId}
              onChange={(e) => setChatWorkspaceId(e.target.value)}
              aria-label="Workspace"
            >
              {scopedWorkspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          )}
        </div>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 4,
          padding: "2px 8px", borderRadius: 100, fontSize: 10, fontWeight: 600,
          background: "rgba(16,185,129,0.12)", color: C.green, border: "1px solid rgba(16,185,129,0.25)",
        }}>
          <span style={{ width: 5, height: 5, background: C.green, borderRadius: "50%", display: "inline-block" }} />
          {panel === "platform" || panel === "dashboard" ? "Live" : "Operational"}
        </span>
        <button
          type="button"
          aria-pressed={brightMode}
          title={brightMode ? "Switch to dark appearance" : "Switch to bright appearance"}
          onClick={() => setBrightMode((v) => !v)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "4px 10px",
            borderRadius: 8,
            border: `1px solid ${C.bd2}`,
            background: brightMode ? "rgba(37,99,235,0.12)" : "transparent",
            color: C.t2,
            fontSize: 11,
            fontWeight: 600,
            fontFamily: C.sans,
            cursor: "pointer",
          }}
        >
          <span aria-hidden style={{ fontSize: 13 }}>{brightMode ? "🌙" : "☀️"}</span>
          {brightMode ? "Dark" : "Bright"}
        </button>
        <div style={{
          width: 27, height: 27, borderRadius: "50%",
          background: "linear-gradient(135deg,#2563EB,#7C3AED)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, fontWeight: 700, color: "white", cursor: "pointer",
        }}>
          {initials}
        </div>
      </div>

      {isPlatformOwner && (
        <div
          style={{
            flexShrink: 0,
            padding: "8px 20px",
            borderBottom: `1px solid ${C.bd}`,
            background: C.bgE,
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexWrap: "wrap",
            fontSize: 11,
            color: C.t2,
          }}
        >
          <button
            type="button"
            onClick={() => {
              exitToPlatform();
              setPanel("platform");
            }}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              border: `1px solid ${navigationScope === "platform" ? C.accent : C.bd}`,
              background: navigationScope === "platform" ? "rgba(37,99,235,0.12)" : "transparent",
              color: C.t1,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: C.sans,
            }}
          >
            Platform
          </button>
          <span style={{ color: C.t3 }}>›</span>
          {navigationScope === "organization" && selectedOrgId ? (
            <>
              <span style={{ color: C.t1, fontWeight: 600 }}>
                {selectedOrgName ?? "Organization"}
              </span>
              {(ctxWorkspaceId || ctxWorkspaceName) && (
                <>
                  <span style={{ color: C.t3 }}>›</span>
                  <span style={{ color: C.t1 }}>{ctxWorkspaceName ?? "Workspace"}</span>
                </>
              )}
            </>
          ) : (
            <span style={{ color: C.t3, fontStyle: "italic" }}>
              Platform-wide — select an organization to scope the app
            </span>
          )}
        </div>
      )}
    </>
  );
}
