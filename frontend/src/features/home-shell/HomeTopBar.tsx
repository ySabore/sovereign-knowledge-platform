import { useEffect, useRef, useState } from "react";
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
  memberChatOnly?: boolean;
  onLogout?: () => void;
  onOpenAccountSettings?: () => void;
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
  memberChatOnly = false,
  onLogout,
  onOpenAccountSettings,
}: HomeTopBarProps) {
  const C = useOrgShellTokens();
  const [openUserMenu, setOpenUserMenu] = useState(false);
  const userMenuRef = useRef<HTMLDivElement | null>(null);
  const panelLabel = getPanelDisplayLabel({ panel, ctxWorkspaceName, chatWorkspaceId });
  const activeWorkspaceName =
    (chatWorkspaceId && scopedWorkspaces.find((w) => w.id === chatWorkspaceId)?.name)
    || ctxWorkspaceName
    || null;
  const activeWorkspaceIndex = chatWorkspaceId
    ? scopedWorkspaces.findIndex((w) => w.id === chatWorkspaceId)
    : -1;

  function cycleWorkspace(step: 1 | -1) {
    if (!chatWorkspaceId || scopedWorkspaces.length < 2 || activeWorkspaceIndex < 0) return;
    const nextIndex = (activeWorkspaceIndex + step + scopedWorkspaces.length) % scopedWorkspaces.length;
    setChatWorkspaceId(scopedWorkspaces[nextIndex].id);
  }

  useEffect(() => {
    function onDocumentMouseDown(e: MouseEvent) {
      const target = e.target as Node | null;
      if (!userMenuRef.current || !target) return;
      if (!userMenuRef.current.contains(target)) {
        setOpenUserMenu(false);
      }
    }
    document.addEventListener("mousedown", onDocumentMouseDown);
    return () => document.removeEventListener("mousedown", onDocumentMouseDown);
  }, []);

  return (
    <>
      <div style={{
        height: 50, background: C.bgS, borderBottom: `1px solid ${C.bd}`,
        display: "flex", alignItems: "center", padding: "0 20px", gap: 12, flexShrink: 0,
      }}>
        {panel === "chats" && chatWorkspaceId && !memberChatOnly && (
          <button
            type="button"
            className="skc-exit-embedded"
            onClick={() => setChatWorkspaceId(null)}
          >
            ← Chats
          </button>
        )}
        <div style={{ flex: 1, fontSize: 12, color: C.t3, display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
          {memberChatOnly ? (
            <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              <span style={{ color: C.t3 }}>Organization:</span>{" "}
              <span style={{ color: C.t1, fontWeight: 600 }}>{selectedOrgName ?? "Organization"}</span>
              {" · "}
              <span style={{ color: C.t3 }}>Workspace:</span>{" "}
              <span style={{ color: C.t1, fontWeight: 600 }}>{activeWorkspaceName ?? "Workspace"}</span>
            </span>
          ) : (
            <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              Platform /{" "}
              <span style={{ color: C.t1, fontWeight: 500 }}>
                {panelLabel}
              </span>
            </span>
          )}
          {panel === "chats" && chatWorkspaceId && scopedWorkspaces.length > 0 && (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <button
                type="button"
                className="skc-exit-embedded"
                onClick={() => cycleWorkspace(-1)}
                disabled={scopedWorkspaces.length < 2}
                aria-label="Previous workspace"
                title="Previous workspace"
                style={{
                  marginRight: 0,
                  padding: "3px 8px",
                  minWidth: 30,
                  justifyContent: "center",
                  opacity: scopedWorkspaces.length < 2 ? 0.45 : 1,
                }}
              >
                {"<"}
              </button>
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
              <button
                type="button"
                className="skc-exit-embedded"
                onClick={() => cycleWorkspace(1)}
                disabled={scopedWorkspaces.length < 2}
                aria-label="Next workspace"
                title="Next workspace"
                style={{
                  marginRight: 0,
                  padding: "3px 8px",
                  minWidth: 30,
                  justifyContent: "center",
                  opacity: scopedWorkspaces.length < 2 ? 0.45 : 1,
                }}
              >
                {">"}
              </button>
            </div>
          )}
        </div>
        {!memberChatOnly && (
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            padding: "2px 8px", borderRadius: 100, fontSize: 10, fontWeight: 600,
            background: "rgba(16,185,129,0.12)", color: C.green, border: "1px solid rgba(16,185,129,0.25)",
          }}>
            <span style={{ width: 5, height: 5, background: C.green, borderRadius: "50%", display: "inline-block" }} />
            {panel === "platform" || panel === "dashboard" ? "Live" : "Operational"}
          </span>
        )}
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
        <div ref={userMenuRef} style={{ position: "relative" }}>
          <button
            type="button"
            onClick={() => setOpenUserMenu((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={openUserMenu}
            title="Account menu"
            style={{
              width: 27, height: 27, borderRadius: "50%",
              background: "linear-gradient(135deg,#2563EB,#7C3AED)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 700, color: "white", cursor: "pointer",
              border: "none",
            }}
          >
            {initials}
          </button>
          {openUserMenu && (onLogout || onOpenAccountSettings) && (
            <div
              role="menu"
              style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                minWidth: 170,
                background: C.bgS,
                border: `1px solid ${C.bd}`,
                borderRadius: 10,
                padding: 6,
                boxShadow: "0 12px 30px rgba(2,6,23,0.28)",
                zIndex: 30,
              }}
            >
              {onOpenAccountSettings && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpenUserMenu(false);
                    onOpenAccountSettings();
                  }}
                  style={{
                    width: "100%",
                    border: "none",
                    background: "transparent",
                    color: C.t1,
                    cursor: "pointer",
                    textAlign: "left",
                    borderRadius: 8,
                    padding: "8px 10px",
                    fontSize: 12,
                    fontFamily: C.sans,
                    fontWeight: 600,
                  }}
                >
                  Profile & notifications
                </button>
              )}
              {onLogout && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setOpenUserMenu(false);
                    onLogout();
                  }}
                  style={{
                    width: "100%",
                    border: "none",
                    background: "transparent",
                    color: C.t1,
                    cursor: "pointer",
                    textAlign: "left",
                    borderRadius: 8,
                    padding: "8px 10px",
                    fontSize: 12,
                    fontFamily: C.sans,
                    fontWeight: 600,
                  }}
                >
                  Sign out
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {isPlatformOwner && !memberChatOnly && (
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
