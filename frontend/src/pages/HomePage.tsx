import {
  Fragment,
  type ChangeEvent,
  type CSSProperties,
  type Dispatch,
  type FormEvent,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { fetchPublicConfig } from "../lib/publicConfig";
import { KnowledgeAnalyticsPanel } from "../components/KnowledgeAnalyticsPanel";
import { OrgDashboardAnalytics } from "../components/OrgDashboardAnalytics";
import { PlatformOwnerDashboard } from "../components/PlatformOwnerDashboard";
import { TeamManagementPanel } from "../components/TeamManagementPanel";
import { WorkspaceConnectorsPanel } from "../components/WorkspaceConnectorsPanel";
import { useAuth } from "../context/AuthContext";
import { usePlatformNavigation } from "../context/PlatformNavigationContext";
import { useOrgsOutlet } from "../layouts/ProtectedAppShell";
import {
  OrgShellTokensContext,
  OrgShellUiContext,
  ORG_SHELL_TOKENS_BRIGHT,
  ORG_SHELL_TOKENS_DARK,
  persistOrgBrightMode,
  readOrgBrightModeFromStorage,
  useOrgShellTokens,
} from "../context/OrgShellThemeContext";
import { DashboardPage } from "./app/DashboardPage";
import { OrganizationSelect } from "../features/scope-select/OrganizationSelect";
import { WorkspaceSelect } from "../features/scope-select/WorkspaceSelect";
import { OrganizationSettingsPanel } from "../features/organization-settings/OrganizationSettingsPanel";
import { DocumentsPanel } from "../features/documents/DocumentsPanel";
import { HomePanelRouter } from "../features/home-shell/HomePanelRouter";
import { BackNavButton } from "../features/home-shell/BackNavButton";
import type { Org, OrgChatProvider, OrgScreen, Panel, Workspace } from "../features/home-shell/types";
import type { AllWorkspacesPanelProps, ChatsPanelProps } from "../features/home-shell/contracts";
import { useHomeWorkspaceState } from "../features/home-shell/useHomeWorkspaceState";
import { useOrgKnowledgeGate } from "../features/home-shell/useOrgKnowledgeGate";
import { getNavLockState, useHomeNavState } from "../features/home-shell/useHomeNavState";
import { HomeSidebar } from "../features/home-shell/HomeSidebar";
import { HomeTopBar } from "../features/home-shell/HomeTopBar";

// ─── Types ────────────────────────────────────────────────────────────────────
type OrgRetrievalStrategy = "" | "heuristic" | "hybrid" | "rerank";

const URL_PANELS: Panel[] = [
  "platform",
  "dashboard",
  "orgs",
  "workspaces",
  "chats",
  "team",
  "connectors",
  "docs",
  "analytics",
  "billing",
  "audit",
  "settings",
];

function panelFromQuery(value: string | null): Panel | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  return (URL_PANELS as string[]).includes(normalized) ? (normalized as Panel) : null;
}

function orgChatProviderFromApi(v: string | null | undefined): OrgChatProvider {
  if (v === "extractive" || v === "ollama" || v === "openai" || v === "anthropic") return v;
  return "";
}

function orgRetrievalStrategyFromApi(v: string | null | undefined): OrgRetrievalStrategy {
  if (v === "heuristic" || v === "hybrid" || v === "rerank") return v;
  return "";
}
type Document = {
  id: string;
  filename: string;
  status: string;
  ingestion_job_id?: string | null;
  ingestion_job_status?: string | null;
  ingestion_job_error?: string | null;
  page_count: number | null;
  chunk_count?: number;
  created_at?: string;
};
/** Tier 1 + Tier 2 + Tier 3 — must match `ALLOWED_UPLOAD_EXTENSIONS` in app/services/ingestion.py */
const DOCUMENT_UPLOAD_ACCEPT =
  ".pdf,.docx,.txt,.md,.markdown,.html,.htm,.pptx,.xlsx,.xls,.csv,.rtf,.eml,.msg,.epub,.mobi,.png,.jpg,.jpeg,.webp,.tif,.tiff";

const dashNavIcon = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
  </svg>
);

// ─── Static connector catalogue ───────────────────────────────────────────────
const CONNECTORS = [
  { id: "confluence", emoji: "📘", name: "Confluence", desc: "Sync pages, spaces, and team wikis automatically." },
  { id: "notion", emoji: "📓", name: "Notion", desc: "Index databases, pages, and nested docs." },
  { id: "github", emoji: "🐙", name: "GitHub", desc: "Connect repos, PRs, issues, and markdown docs." },
  { id: "gdrive", emoji: "📁", name: "Google Drive", desc: "Pull Docs, Sheets, and Slides into your knowledge base." },
  { id: "jira", emoji: "🎫", name: "Jira", desc: "Index tickets, epics, and project documentation." },
  { id: "slack", emoji: "💬", name: "Slack", desc: "Surface answers from channels and threads." },
  { id: "zendesk", emoji: "🎯", name: "Zendesk", desc: "Connect your support knowledge base and tickets." },
  { id: "sharepoint", emoji: "📊", name: "SharePoint", desc: "Sync SharePoint sites, lists, and libraries." },
  { id: "linear", emoji: "⬡", name: "Linear", desc: "Index issues, cycles, and project docs." },
  { id: "intercom", emoji: "💌", name: "Intercom", desc: "Pull help articles and conversation threads." },
  { id: "salesforce", emoji: "☁️", name: "Salesforce", desc: "Bring in accounts, cases, and knowledge articles." },
  { id: "dropbox", emoji: "📦", name: "Dropbox", desc: "Connect files, Paper docs, and team folders." },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function Dot({ color }: { color: string }) {
  return (
    <span style={{ display: "inline-block", width: 5, height: 5, borderRadius: "50%", background: color, marginRight: 4 }} />
  );
}

function Badge({ label, color, bg, border }: { label: string; color: string; bg: string; border: string }) {
  const C = useOrgShellTokens();
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", padding: "2px 8px", borderRadius: 100,
      fontSize: 10, fontWeight: 600, color, background: bg, border: `1px solid ${border}`,
      fontFamily: C.sans,
    }}>
      {label}
    </span>
  );
}

function Btn({
  children, variant = "primary", onClick, disabled, style, htmlType = "button",
}: {
  children: React.ReactNode;
  variant?: "primary" | "ghost" | "danger";
  onClick?: () => void;
  disabled?: boolean;
  style?: React.CSSProperties;
  htmlType?: "button" | "submit";
}) {
  const C = useOrgShellTokens();
  const base: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 13px",
    borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: C.sans, transition: "all .14s", opacity: disabled ? 0.5 : 1, border: "none",
  };
  const styles: Record<string, React.CSSProperties> = {
    primary: { background: C.accent, color: "white", boxShadow: `0 0 16px ${C.accentG}` },
    ghost: { background: "transparent", color: C.t2, border: `1px solid ${C.bd2}` },
    danger: { background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.25)" },
  };
  return (
    <button
      type={htmlType}
      style={{ ...base, ...styles[variant], ...style }}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function Input({
  value, onChange, placeholder, required, disabled, style, type,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  style?: React.CSSProperties;
  type?: "text" | "password";
}) {
  const C = useOrgShellTokens();
  return (
    <input
      type={type ?? "text"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      style={{
        background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 7,
        padding: "7px 10px", fontSize: 12, color: C.t1, fontFamily: C.sans,
        outline: "none", width: "100%", opacity: disabled ? 0.55 : 1, ...style,
      }}
    />
  );
}

// ─── Wide org dropdown (with search) ─────────────────────────────────────────
// ─── Org detail — stats tile ───────────────────────────────────────────────────

// ─── Org detail — stats tile ───────────────────────────────────────────────────
function StatTile({
  icon, label, value, sub, color, onClick, title,
}: {
  icon: string;
  label: string;
  value: string | number;
  sub?: string;
  color?: string;
  /** When set, tile is keyboard-focusable and opens the matching left-nav section. */
  onClick?: () => void;
  title?: string;
}) {
  const C = useOrgShellTokens();
  const [hover, setHover] = useState(false);
  const interactive = Boolean(onClick);
  const shell: React.CSSProperties = {
    background: C.bgCard,
    border: `1px solid ${interactive && hover ? "rgba(37,99,235,0.45)" : C.bd}`,
    borderRadius: 12,
    padding: "16px 18px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    transition: "border-color .15s ease, box-shadow .15s ease",
    boxShadow: interactive && hover ? "0 0 0 1px rgba(37,99,235,0.12)" : "none",
    cursor: interactive ? "pointer" : "default",
    width: "100%",
    textAlign: "left" as const,
    font: "inherit",
    color: "inherit",
  } satisfies CSSProperties;
  const inner = (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3 }}>
          {label}
        </span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: color ?? C.t1, fontFamily: C.mono, lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 10, color: C.t3 }}>{sub}</div>}
    </>
  );
  if (interactive) {
    return (
      <button
        type="button"
        onClick={onClick}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={shell}
        title={title}
      >
        {inner}
      </button>
    );
  }
  return (
    <div style={shell}>
      {inner}
    </div>
  );
}

// ─── Org detail — full sections view ──────────────────────────────────────────
function OrgDetailView({
  org,
  workspaces,
  loadingWs,
  onUploadClick,
  onWorkspaceCreated,
  onGoToWorkspace,
  onLaunchWorkspaceChat,
  onOpenSettings,
  onNavigateToWorkspaces,
  onNavigateToTeam,
  onNavigateToDocuments,
  onNavigateToConnectors,
}: {
  org: Org;
  workspaces: Workspace[];
  loadingWs: boolean;
  onUploadClick: (ws: Workspace) => void;
  onWorkspaceCreated: (wsId?: string) => void;
  onGoToWorkspace: (wsId?: string) => void;
  onLaunchWorkspaceChat?: (wsId: string) => void;
  onOpenSettings: () => void;
  onNavigateToWorkspaces: () => void;
  onNavigateToTeam: () => void;
  onNavigateToDocuments: () => void;
  onNavigateToConnectors: () => void;
}) {
  const C = useOrgShellTokens();
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [memberCount, setMemberCount] = useState<number | null>(null);
  const [documentCount, setDocumentCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setOverviewLoading(true);
    setMemberCount(null);
    setDocumentCount(null);
    void api
      .get<{ member_count: number; document_count: number }>(`/organizations/${org.id}/overview-stats`)
      .then(({ data }) => {
        if (!cancelled) {
          setMemberCount(data.member_count);
          setDocumentCount(data.document_count);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMemberCount(null);
          setDocumentCount(null);
        }
      })
      .finally(() => {
        if (!cancelled) setOverviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [org.id]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>

      {/* ── Identity header ── */}
      <div style={{
        background: C.bgCard, border: `1px solid ${C.bd}`,
        borderRadius: 16, padding: "24px 26px",
        backgroundImage: "linear-gradient(135deg, rgba(37,99,235,0.06) 0%, rgba(139,92,246,0.04) 100%)",
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 18 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14, flexShrink: 0,
            background: "linear-gradient(135deg,rgba(37,99,235,0.4),rgba(139,92,246,0.4))",
            border: "1px solid rgba(37,99,235,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 22, fontWeight: 700, color: "#bfdbfe",
          }}>
            {org.name.slice(0, 2).toUpperCase()}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 6 }}>
              <span style={{ fontFamily: C.serif, fontSize: 22, color: C.t1 }}>{org.name}</span>
              <Badge
                label={org.status === "active" ? "● Active" : "● " + org.status}
                color={org.status === "active" ? C.green : C.gold}
                bg={org.status === "active" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)"}
                border={org.status === "active" ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)"}
              />
              <Badge label="Business" color={C.purple} bg="rgba(139,92,246,0.12)" border="rgba(139,92,246,0.25)" />
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 24px" }}>
              {[
                { label: "Slug", value: `/${org.slug}` },
                { label: "ID", value: org.id.slice(0, 12) + "…" },
                { label: "Region", value: "us-east-1" },
                { label: "Plan", value: "Business · Unlimited" },
              ].map(({ label, value }) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{ fontSize: 10, color: C.t3, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.07em" }}>{label}</span>
                  <span style={{ fontSize: 10, color: C.t2, fontFamily: C.mono }}>{value}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            <Btn variant="ghost" style={{ fontSize: 11 }} onClick={onOpenSettings}>
              ⚙ Org Settings
            </Btn>
          </div>
        </div>
      </div>

      {/* ── Stats row ── */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.t3, marginBottom: 12 }}>
          Overview
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
          <StatTile
            icon="⬡"
            label="Workspaces"
            value={loadingWs ? "…" : workspaces.length}
            sub="Active environments"
            color={C.accent}
            onClick={onNavigateToWorkspaces}
            title="Open Workspaces in the left menu"
          />
          <StatTile
            icon="👥"
            label="Members"
            value={overviewLoading ? "…" : memberCount ?? "—"}
            sub="Organization roster"
            onClick={onNavigateToTeam}
            title="Open Team in the left menu"
          />
          <StatTile
            icon="📄"
            label="Documents"
            value={overviewLoading ? "…" : documentCount ?? "—"}
            sub="Indexed in this org"
            color={C.purple}
            onClick={onNavigateToDocuments}
            title="Open Documents in the left menu"
          />
          <StatTile
            icon="🔌"
            label="Connectors"
            value={CONNECTORS.length}
            sub="Available integrations"
            color={C.green}
            onClick={onNavigateToConnectors}
            title="Open Connectors in the left menu"
          />
        </div>
      </div>

      {/* ── Workspaces ── */}
      <div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.t3 }}>
            Workspaces
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 10, color: C.t3 }}>
              {loadingWs ? "Loading…" : `${workspaces.length} workspace${workspaces.length !== 1 ? "s" : ""}`}
            </span>
            {workspaces.length > 0 && (
              <button
                type="button"
                style={{ fontSize: 10, color: C.accent, background: "none", border: "none", cursor: "pointer" }}
                onClick={() => onGoToWorkspace()}
              >
                View all →
              </button>
            )}
          </div>
        </div>
        {loadingWs ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {[1, 2, 3].map((i) => (
              <div key={i} style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, height: 168, opacity: 0.4 }} />
            ))}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            {workspaces.map((ws, i) => (
              <WorkspaceCard
                key={ws.id}
                ws={ws}
                index={i}
                onUploadClick={onUploadClick}
                onGoToWorkspace={onGoToWorkspace}
                onLaunchChat={onLaunchWorkspaceChat}
              />
            ))}
            <NewWorkspaceCard orgId={org.id} onCreated={onWorkspaceCreated} />
          </div>
        )}
      </div>

    </div>
  );
}

type WsScreen = "overview" | "settings";

function WorkspaceSettingsPanel({
  ws,
  onSaved,
  workspaceCountInOrg,
  showDangerZone,
  onWorkspaceDeleted,
}: {
  ws: Workspace;
  onSaved: (ws: Workspace) => void;
  workspaceCountInOrg: number;
  showDangerZone?: boolean;
  onWorkspaceDeleted?: () => void | Promise<void>;
}) {
  const C = useOrgShellTokens();
  const [name, setName] = useState(ws.name);
  const [description, setDescription] = useState(ws.description ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    setName(ws.name);
    setDescription(ws.description ?? "");
    setErr(null);
    setOk(null);
  }, [ws.id]);

  async function save() {
    setSaving(true);
    setErr(null);
    setOk(null);
    try {
      const { data } = await api.patch<Workspace>(`/workspaces/${ws.id}`, {
        name: name.trim(),
        description: description,
      });
      onSaved(data);
      setOk("Saved.");
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontFamily: C.serif, fontSize: 20, color: C.t1, marginBottom: 4 }}>Workspace settings</div>
        <div style={{ fontSize: 12, color: C.t2 }}>Update workspace name and description.</div>
      </div>

      <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "18px 18px 16px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Name
            </div>
            <Input value={name} onChange={setName} placeholder="Workspace name" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Description
            </div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What knowledge is in this workspace, who uses it, and how?"
              rows={4}
              style={{
                width: "100%",
                background: C.bgE,
                border: `1px solid ${C.bd}`,
                borderRadius: 8,
                padding: "10px 12px",
                fontSize: 12,
                color: C.t1,
                fontFamily: C.sans,
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
                lineHeight: 1.6,
              }}
            />
          </div>
        </div>

        {err && <div style={{ marginTop: 12, fontSize: 11, color: C.red }}>✗ {err}</div>}
        {ok && <div style={{ marginTop: 12, fontSize: 11, color: C.green }}>✓ {ok}</div>}

        <div style={{ marginTop: 14, display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Btn variant="ghost" disabled={saving} onClick={() => { setName(ws.name); setDescription(ws.description ?? ""); }}>
            Reset
          </Btn>
          <Btn variant="primary" disabled={saving || !name.trim()} onClick={save}>
            {saving ? "Saving…" : "Save changes"}
          </Btn>
        </div>
      </div>

      {showDangerZone && onWorkspaceDeleted && (
        <div
          style={{
            marginTop: 18,
            padding: "16px 18px",
            background: "rgba(239,68,68,0.06)",
            border: "1px solid rgba(239,68,68,0.28)",
            borderRadius: 14,
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.red, marginBottom: 8 }}>
            Danger zone
          </div>
          {workspaceCountInOrg <= 1 ? (
            <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.5 }}>
              You cannot delete the only workspace in this organization. Create another workspace first, then you can remove this one.
            </div>
          ) : (
            <>
              <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.5, marginBottom: 12 }}>
                Delete <strong style={{ color: C.t1 }}>{ws.name}</strong> and all indexed documents and chats in it. This cannot be undone.
              </div>
              <Btn
                variant="ghost"
                style={{ borderColor: "rgba(239,68,68,0.45)", color: C.red }}
                onClick={async () => {
                  if (!window.confirm(`Permanently delete workspace “${ws.name}”?`)) return;
                  setErr(null);
                  try {
                    await api.delete(`/workspaces/${ws.id}`, { params: { confirm_name: ws.name } });
                    await onWorkspaceDeleted();
                  } catch (e) {
                    setErr(apiErrorMessage(e));
                  }
                }}
              >
                Delete workspace
              </Btn>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function WorkspaceOverviewFileUploadCard({ workspace }: { workspace: Workspace }) {
  const C = useOrgShellTokens();
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [uploadOk, setUploadOk] = useState<string | null>(null);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadErr(null);
    setUploadOk(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const { data } = await api.post<{ filename: string; chunk_count: number }>(
        `/documents/workspaces/${workspace.id}/upload`,
        body,
      );
      setUploadOk(`"${data.filename}" indexed — ${data.chunk_count} chunks.`);
    } catch (ex) {
      setUploadErr(apiErrorMessage(ex));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={uploading}
        style={{
          width: "100%",
          textAlign: "left",
          padding: "18px 18px 16px",
          borderRadius: 14,
          background: C.bgCard,
          border: `1px solid ${C.bd}`,
          cursor: uploading ? "wait" : "pointer",
          fontFamily: C.sans,
          transition: "border-color .15s, box-shadow .15s",
        }}
        onMouseEnter={(e) => {
          if (uploading) return;
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(37,99,235,0.45)";
          (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 0 20px rgba(37,99,235,0.12)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.borderColor = C.bd;
          (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
        }}
      >
        <div style={{ fontSize: 22, marginBottom: 8 }}>📁</div>
        <div style={{ fontSize: 14, fontWeight: 600, color: C.t1, marginBottom: 4 }}>Upload File</div>
        <div style={{ fontSize: 11, color: C.t3, lineHeight: 1.45, marginBottom: 10 }}>
          Manually upload documents (PDF, Office, text, Markdown, HTML, slides, spreadsheets, CSV, RTF); chunked and indexed.
        </div>
        <span style={{ fontSize: 11, color: C.accent, fontWeight: 600 }}>
          {uploading ? "Indexing…" : "Upload File ↑"}
        </span>
      </button>
      <input
        ref={fileRef}
        type="file"
        accept={DOCUMENT_UPLOAD_ACCEPT}
        style={{ display: "none" }}
        onChange={handleUpload}
        disabled={uploading}
      />
      {uploadErr && (
        <div style={{ fontSize: 10, color: C.red, lineHeight: 1.35, padding: "8px 2px 0" }}>{uploadErr}</div>
      )}
      {uploadOk && (
        <div style={{ fontSize: 10, color: C.green, lineHeight: 1.35, padding: "8px 2px 0" }}>✓ {uploadOk}</div>
      )}
    </div>
  );
}

// ─── Workspaces panel (org-style: dropdown + summary + action cards) ─────────
function AllWorkspacesPanel({
  orgs,
  allWorkspaces,
  loadingWs,
  initialWsId,
  onLaunchChat,
  onWorkspaceUpdated,
  onSelectedWorkspaceChange,
  onNavigateToTeam,
  onNavigateToConnectors,
  isPlatformOwner,
  onWorkspaceDeleted,
}: AllWorkspacesPanelProps) {
  const C = useOrgShellTokens();
  const [selectedWsId, setSelectedWsId] = useState<string>(initialWsId ?? "");
  const [screen, setScreen] = useState<WsScreen>("overview");
  const [summaryDraft, setSummaryDraft] = useState("");

  useEffect(() => {
    if (initialWsId && allWorkspaces.some((w) => w.id === initialWsId)) {
      setSelectedWsId(initialWsId);
      return;
    }
    if (allWorkspaces.length === 0) {
      setSelectedWsId("");
      return;
    }
    setSelectedWsId((prev) => (allWorkspaces.some((w) => w.id === prev) ? prev : allWorkspaces[0].id));
  }, [initialWsId, allWorkspaces]);

  const selectedWs = allWorkspaces.find((w) => w.id === selectedWsId);
  const selectedOrg = selectedWs ? orgs.find((o) => o.id === selectedWs.organization_id) : undefined;

  useEffect(() => {
    if (selectedWs) setSummaryDraft(selectedWs.description ?? "");
  }, [selectedWs?.id, selectedWs?.description]);

  useEffect(() => {
    setScreen("overview");
  }, [selectedWsId]);

  useEffect(() => {
    if (!onSelectedWorkspaceChange) return;
    if (!selectedWs) {
      onSelectedWorkspaceChange(null, null);
      return;
    }
    onSelectedWorkspaceChange(selectedWs.id, selectedWs.name);
  }, [selectedWs, onSelectedWorkspaceChange]);

  if (loadingWs) {
    return (
      <div style={{ padding: "22px 26px" }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 20 }}>Workspaces</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1, 2, 3].map((i) => (
            <div key={i} style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 12, height: 56, opacity: 0.4 }} />
          ))}
        </div>
      </div>
    );
  }

  if (allWorkspaces.length === 0) {
    return (
      <div style={{ padding: "22px 26px" }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 6 }}>Workspaces</div>
        <div style={{ fontSize: 12, color: C.t2, marginBottom: 24 }}>Knowledge environments across your organizations.</div>
        <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "52px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 38, marginBottom: 12 }}>⬡</div>
          <div style={{ fontFamily: C.serif, fontSize: 18, color: C.t1, marginBottom: 6 }}>No workspaces yet</div>
          <div style={{ fontSize: 12, color: C.t2 }}>Go to Organizations to create your first workspace.</div>
        </div>
      </div>
    );
  }

  if (!selectedWs) return null;

  function backToOverview() {
    setScreen("overview");
  }

  async function handleWorkspaceDeleted() {
    await onWorkspaceDeleted?.();
    setScreen("overview");
  }

  const pal = WS_PALETTE[allWorkspaces.findIndex((w) => w.id === selectedWs.id) % WS_PALETTE.length];

  return (
    <div style={{ padding: "22px 26px", overflowY: "auto", height: "100%" }}>

      {/* Breadcrumb when sub-screen */}
      {screen !== "overview" && (
        <BackNavButton onClick={backToOverview}>
          ← Back to workspace
        </BackNavButton>
      )}

      {screen === "overview" && (
        <>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
            <div>
              <div style={{ fontFamily: C.serif, fontSize: 24, color: C.t1, marginBottom: 4 }}>Workspaces</div>
              <div style={{ fontSize: 12, color: C.t2 }}>
                Select a workspace, then launch chat or manage connectors and team.
              </div>
            </div>
            <span style={{ fontSize: 11, color: C.t3 }}>{allWorkspaces.length} total</span>
          </div>

          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.t3, marginBottom: 10 }}>
              Select Workspace
            </div>
            <WorkspaceSelect
              workspaces={allWorkspaces}
              orgs={orgs}
              selectedId={selectedWsId}
              onSelect={(id) => setSelectedWsId(id)}
            />
          </div>

          <div style={{ height: 1, background: C.bd, margin: "22px 0" }} />

          {/* Identity strip */}
          <div style={{
            background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 16, padding: "20px 22px",
            marginBottom: 20,
            backgroundImage: "linear-gradient(135deg, rgba(37,99,235,0.06) 0%, rgba(139,92,246,0.04) 100%)",
          }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12, flexShrink: 0,
                background: pal.bg, border: `1px solid ${pal.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 15, fontWeight: 700, color: pal.text,
              }}>
                {selectedWs.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontFamily: C.serif, fontSize: 20, color: C.t1, marginBottom: 4 }}>{selectedWs.name}</div>
                <div style={{ fontSize: 11, color: C.t3, fontFamily: C.mono }}>
                  {selectedOrg?.name ?? "—"} · {selectedWs.id.slice(0, 12)}…
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexShrink: 0 }}>
                <Badge label="● Active" color={C.green} bg="rgba(16,185,129,0.1)" border="rgba(16,185,129,0.2)" />
                <Btn variant="ghost" style={{ fontSize: 11 }} onClick={() => setScreen("settings")}>
                  ⚙ Workspace Settings
                </Btn>
              </div>
            </div>

            <div style={{ marginTop: 18, borderTop: `1px solid ${C.bd}`, paddingTop: 16 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 8 }}>
                Workspace summary
              </div>
              <textarea
                value={summaryDraft}
                onChange={(e) => setSummaryDraft(e.target.value)}
                placeholder="Describe this workspace: what knowledge it holds, who it is for, and how it is used…"
                rows={3}
                style={{
                  width: "100%", background: C.bgE, border: `1px solid ${C.bd}`, borderRadius: 8,
                  padding: "10px 12px", fontSize: 12, color: C.t1, fontFamily: C.sans,
                  resize: "vertical", outline: "none", boxSizing: "border-box", lineHeight: 1.6,
                }}
              />
            </div>
          </div>

          {/* Action cards */}
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.t3, marginBottom: 12 }}>
            Actions
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12, marginBottom: 8 }}>
            <WorkspaceOverviewFileUploadCard workspace={selectedWs} />

            <button
              type="button"
              onClick={() => onLaunchChat(selectedWs.id)}
              style={{
                textAlign: "left", padding: "18px 18px 16px", borderRadius: 14,
                background: C.bgCard, border: `1px solid ${C.bd}`,
                cursor: "pointer", fontFamily: C.sans, transition: "border-color .15s, box-shadow .15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(37,99,235,0.45)";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 20px rgba(37,99,235,0.12)`;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = C.bd;
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
              }}
            >
              <div style={{ fontSize: 22, marginBottom: 8 }}>💬</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: C.t1, marginBottom: 4 }}>Launch Chat</div>
              <div style={{ fontSize: 11, color: C.t3, lineHeight: 1.45, marginBottom: 10 }}>
                Open the Chats screen for this workspace, then start a conversation.
              </div>
              <span style={{ fontSize: 11, color: C.accent, fontWeight: 600 }}>Go to Chats →</span>
            </button>

            <button
              type="button"
              onClick={() => onNavigateToConnectors?.()}
              style={{
                textAlign: "left", padding: "18px 18px 16px", borderRadius: 14,
                background: C.bgCard, border: `1px solid ${C.bd}`,
                cursor: "pointer", fontFamily: C.sans, transition: "border-color .15s, box-shadow .15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(37,99,235,0.45)";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 20px rgba(37,99,235,0.12)`;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = C.bd;
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
              }}
            >
              <div style={{ fontSize: 22, marginBottom: 8 }}>🔌</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: C.t1, marginBottom: 4 }}>Connectors</div>
              <div style={{ fontSize: 11, color: C.t3, lineHeight: 1.45, marginBottom: 10 }}>
                Sync Confluence, Drive, Notion, GitHub, and more into this workspace.
              </div>
              <span style={{ fontSize: 11, color: C.accent, fontWeight: 600 }}>Manage sources →</span>
            </button>

            <button
              type="button"
              onClick={() => onNavigateToTeam?.()}
              style={{
                textAlign: "left", padding: "18px 18px 16px", borderRadius: 14,
                background: C.bgCard, border: `1px solid ${C.bd}`,
                cursor: "pointer", fontFamily: C.sans, transition: "border-color .15s, box-shadow .15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(37,99,235,0.45)";
                (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 20px rgba(37,99,235,0.12)`;
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.borderColor = C.bd;
                (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
              }}
            >
              <div style={{ fontSize: 22, marginBottom: 8 }}>👥</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: C.t1, marginBottom: 4 }}>Teams</div>
              <div style={{ fontSize: 11, color: C.t3, lineHeight: 1.45, marginBottom: 10 }}>
                Invite members and manage roles for this workspace.
              </div>
              <span style={{ fontSize: 11, color: C.accent, fontWeight: 600 }}>View team →</span>
            </button>
          </div>
        </>
      )}

      {screen === "settings" && (
        <WorkspaceSettingsPanel
          ws={selectedWs}
          workspaceCountInOrg={allWorkspaces.filter((w) => w.organization_id === selectedWs.organization_id).length}
          showDangerZone={isPlatformOwner}
          onWorkspaceDeleted={handleWorkspaceDeleted}
          onSaved={(updated) => {
            onWorkspaceUpdated(updated);
          }}
        />
      )}
    </div>
  );
}

// ─── Chats panel ─────────────────────────────────────────────────────────────
function ChatsPanel({
  allWorkspaces, initialWsId, onOpenChat,
}: ChatsPanelProps) {
  const C = useOrgShellTokens();
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!initialWsId) return;
    const el = rowRefs.current[initialWsId];
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [initialWsId, allWorkspaces]);

  return (
    <div style={{ padding: "22px 26px" }}>
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>Chats</div>
        <div style={{ fontSize: 12, color: C.t2 }}>Pick a workspace to open chat (sidebar stays visible).</div>
      </div>
      {allWorkspaces.length === 0 ? (
        <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "52px 24px", textAlign: "center" }}>
          <div style={{ fontSize: 38, marginBottom: 12 }}>💬</div>
          <div style={{ fontFamily: C.serif, fontSize: 18, color: C.t1, marginBottom: 6 }}>No workspaces available</div>
          <div style={{ fontSize: 12, color: C.t2 }}>Create a workspace first, then launch chat from it.</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {allWorkspaces.map((ws) => {
            const focused = initialWsId === ws.id;
            return (
              <div
                key={ws.id}
                ref={(el) => { rowRefs.current[ws.id] = el; }}
                style={{
                  background: focused ? "rgba(37,99,235,0.1)" : C.bgCard,
                  border: focused ? "1px solid rgba(37,99,235,0.45)" : `1px solid ${C.bd}`,
                  borderRadius: 12,
                  padding: "16px 20px", display: "flex", alignItems: "center", gap: 16, cursor: "pointer",
                }}
                onClick={() => onOpenChat(ws.id)}
              >
                <div style={{
                  width: 38, height: 38, borderRadius: 9, flexShrink: 0,
                  background: "rgba(37,99,235,0.15)", border: "1px solid rgba(37,99,235,0.25)",
                  display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
                }}>
                  💬
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 2 }}>{ws.name}</div>
                  <div style={{ fontSize: 11, color: C.t3 }}>
                    Click to open chat · {ws.description || "Knowledge workspace"}
                  </div>
                </div>
                <svg viewBox="0 0 16 16" width="14" height="14" style={{ fill: C.t3, flexShrink: 0 }}>
                  <path d="M5.5 2L11 8l-5.5 6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Workspace card ───────────────────────────────────────────────────────────
const WS_PALETTE = [
  { bg: "rgba(37,99,235,0.18)", border: "rgba(37,99,235,0.35)", text: "#93c5fd" },
  { bg: "rgba(139,92,246,0.18)", border: "rgba(139,92,246,0.35)", text: "#c4b5fd" },
  { bg: "rgba(16,185,129,0.18)", border: "rgba(16,185,129,0.35)", text: "#6ee7b7" },
  { bg: "rgba(245,158,11,0.18)", border: "rgba(245,158,11,0.35)", text: "#fcd34d" },
  { bg: "rgba(239,68,68,0.18)",  border: "rgba(239,68,68,0.35)",  text: "#fca5a5" },
  { bg: "rgba(6,182,212,0.18)",  border: "rgba(6,182,212,0.35)",  text: "#67e8f9" },
];

function WorkspaceCard({
  ws, index, onUploadClick, onGoToWorkspace, onLaunchChat,
}: {
  ws: Workspace;
  index: number;
  onUploadClick: (ws: Workspace) => void;
  onGoToWorkspace: (wsId: string) => void;
  onLaunchChat?: (wsId: string) => void;
}) {
  const C = useOrgShellTokens();
  const navigate = useNavigate();
  const [hovered, setHovered] = useState(false);
  const pal = WS_PALETTE[index % WS_PALETTE.length];
  const initials = ws.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onGoToWorkspace(ws.id)}
      style={{
        background: C.bgCard,
        border: `1px solid ${hovered ? pal.border : C.bd}`,
        borderRadius: 14,
        padding: "20px 20px 16px",
        display: "flex",
        flexDirection: "column",
        gap: 0,
        transition: "border-color .18s, box-shadow .18s",
        boxShadow: hovered ? `0 0 24px ${pal.bg}` : "none",
        cursor: "pointer",
      }}
    >
      {/* Icon + name */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
        <div style={{
          width: 42, height: 42, borderRadius: 10,
          background: pal.bg, border: `1px solid ${pal.border}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, fontWeight: 700, color: pal.text,
          fontFamily: C.sans, flexShrink: 0,
        }}>
          {initials}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontWeight: 600, color: C.t1,
            marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {ws.name}
          </div>
          <div style={{
            fontSize: 11, color: C.t3, lineHeight: 1.5,
            overflow: "hidden", display: "-webkit-box",
            WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const,
          }}>
            {ws.description || "No description"}
          </div>
        </div>
        <svg viewBox="0 0 16 16" width="12" height="12" style={{ fill: "none", flexShrink: 0, opacity: hovered ? 1 : 0, transition: "opacity .15s" }}>
          <path d="M5.5 2L11 8l-5.5 6" stroke={pal.text} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>

      {/* Meta strip */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "8px 10px", background: C.bgE, borderRadius: 7,
        marginBottom: 14,
      }}>
        <span style={{ fontSize: 10, color: C.t3 }}>
          <span style={{ fontFamily: C.mono }}>id:</span>{" "}
          <span style={{ fontFamily: C.mono, color: C.t2 }}>{ws.id.slice(0, 8)}…</span>
        </span>
        <span style={{ flex: 1 }} />
        <Badge label="● Active" color={C.green} bg="rgba(16,185,129,0.1)" border="rgba(16,185,129,0.2)" />
      </div>

      {/* Actions — stop propagation so card click doesn't fire */}
      <div style={{ display: "flex", gap: 7 }} onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={() => (onLaunchChat ? onLaunchChat(ws.id) : navigate(`/dashboard/${ws.id}`))}
          style={{
            flex: 1, padding: "7px 0", borderRadius: 8,
            background: C.accent, border: "none", color: "white",
            fontSize: 11, fontWeight: 600, cursor: "pointer",
            fontFamily: C.sans, transition: "background .14s",
            boxShadow: `0 0 14px ${C.accentG}`,
          }}
        >
          ▶ Launch Chat
        </button>
        <button
          type="button"
          onClick={() => onUploadClick(ws)}
          style={{
            padding: "7px 12px", borderRadius: 8,
            background: "transparent", border: `1px solid ${C.bd2}`,
            color: C.t2, fontSize: 11, fontWeight: 600,
            cursor: "pointer", fontFamily: C.sans, transition: "all .14s",
          }}
        >
          ↑
        </button>
      </div>
    </div>
  );
}

// ─── New workspace card (create trigger) ──────────────────────────────────────
function NewWorkspaceCard({
  orgId, onCreated,
}: {
  orgId: string;
  onCreated: (wsId?: string) => void;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [hovered, setHovered] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      const { data } = await api.post<Workspace>(`/workspaces/org/${orgId}`, {
        name: name.trim(),
        description: desc.trim() || null,
      });
      setName("");
      setDesc("");
      setOpen(false);
      onCreated(data.id);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  if (open) {
    return (
      <div style={{
        background: C.bgCard, border: `1px solid rgba(37,99,235,0.4)`,
        borderRadius: 14, padding: "20px",
        boxShadow: `0 0 28px rgba(37,99,235,0.1)`,
      }}>
        <div style={{ fontFamily: C.serif, fontSize: 16, color: C.t1, marginBottom: 14 }}>
          New Workspace
        </div>
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: C.t3, marginBottom: 4, letterSpacing: "0.06em", textTransform: "uppercase" }}>Name *</div>
            <Input value={name} onChange={setName} placeholder="e.g. Legal Team, Engineering" required />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 600, color: C.t3, marginBottom: 4, letterSpacing: "0.06em", textTransform: "uppercase" }}>Description</div>
            <Input value={desc} onChange={setDesc} placeholder="What knowledge lives here?" />
          </div>
          {err && <div style={{ fontSize: 11, color: C.red }}>{err}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="primary" disabled={busy} onClick={() => {}}>
              {busy ? "Creating…" : "Create workspace"}
            </Btn>
            <Btn variant="ghost" onClick={() => { setOpen(false); setErr(null); }}>Cancel</Btn>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => setOpen(true)}
      style={{
        background: "transparent",
        border: `2px dashed ${hovered ? C.bd2 : C.bd}`,
        borderRadius: 14, padding: "20px",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        gap: 8, cursor: "pointer", minHeight: 160,
        transition: "border-color .18s",
      }}
    >
      <div style={{
        width: 36, height: 36, borderRadius: 9,
        background: "rgba(37,99,235,0.1)", border: `1px solid rgba(37,99,235,0.25)`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 18, color: C.accent,
      }}>
        +
      </div>
      <div style={{ fontSize: 12, fontWeight: 600, color: hovered ? C.t1 : C.t2 }}>New Workspace</div>
      <div style={{ fontSize: 10, color: C.t3, textAlign: "center" }}>
        Create an isolated knowledge scope
      </div>
    </div>
  );
}

// ─── Org selector ─────────────────────────────────────────────────────────────
function OrgSelector({
  orgs, selectedId, onSelect,
}: {
  orgs: Org[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const C = useOrgShellTokens();
  if (orgs.length === 0) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      {orgs.map((org) => {
        const active = org.id === selectedId;
        return (
          <button
            key={org.id}
            type="button"
            onClick={() => onSelect(org.id)}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "7px 14px", borderRadius: 9,
              border: `1px solid ${active ? "rgba(37,99,235,0.5)" : C.bd}`,
              background: active ? "rgba(37,99,235,0.12)" : C.bgCard,
              color: active ? C.t1 : C.t2,
              fontSize: 13, fontWeight: active ? 600 : 500,
              cursor: "pointer", fontFamily: C.sans,
              transition: "all .15s",
              boxShadow: active ? "0 0 20px rgba(37,99,235,0.12)" : "none",
            }}
          >
            <span style={{
              width: 22, height: 22, borderRadius: 5,
              background: active ? C.accent : "rgba(255,255,255,0.06)",
              border: `1px solid ${active ? "transparent" : C.bd}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, fontWeight: 700,
              color: active ? "white" : C.t3,
              flexShrink: 0,
            }}>
              {org.name[0].toUpperCase()}
            </span>
            {org.name}
            <span style={{
              fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 100,
              background: active ? "rgba(37,99,235,0.3)" : C.bd,
              color: active ? "#93c5fd" : C.t3,
            }}>
              {org.status}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ─── Connectors panel ─────────────────────────────────────────────────────────
function ConnectorsPanel({
  orgs,
  workspaceScope,
}: {
  orgs: Org[];
  /** When set (from Workspaces selection), show real workspace connector management. */
  workspaceScope: Workspace | null;
}) {
  const C = useOrgShellTokens();
  const [connected, setConnected] = useState<Set<string>>(new Set());

  if (workspaceScope) {
    return (
      <div style={{ padding: "18px 22px", overflowY: "auto", height: "100%" }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>
            Connectors · {workspaceScope.name}
          </div>
          <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.6 }}>
            Add and manage integrations for this workspace. New documents sync on a schedule — no manual uploads needed.
          </div>
        </div>
        <WorkspaceConnectorsPanel
          wsName={workspaceScope.name}
          organizationId={workspaceScope.organization_id}
          workspaceId={workspaceScope.id}
        />
      </div>
    );
  }

  return (
    <div style={{ padding: "18px 22px" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>
          Knowledge Connectors
        </div>
        <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.6 }}>
          Connect your existing tools to automatically index and sync content into your workspaces.
          New documents sync every few minutes — no manual uploads needed.
        </div>
        <div
          style={{
            marginTop: 12,
            padding: "10px 14px",
            borderRadius: 10,
            background: "rgba(37,99,235,0.08)",
            border: "1px solid rgba(37,99,235,0.22)",
            fontSize: 12,
            color: C.t2,
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: C.t1 }}>Workspace scope</strong> — Open{" "}
          <strong style={{ color: C.t1 }}>Workspaces</strong>, select a workspace, then return here to add connectors for that workspace.
        </div>
      </div>

      {/* Stats strip */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 20,
      }}>
        {[
          { label: "Available connectors", val: CONNECTORS.length, color: C.t1 },
          { label: "Connected", val: connected.size, color: C.green },
          { label: "Syncing now", val: 0, color: C.t3 },
        ].map((s) => (
          <div key={s.label} style={{
            background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 10,
            padding: "12px 14px", textAlign: "center",
          }}>
            <div style={{ fontFamily: C.serif, fontSize: 26, color: s.color, lineHeight: 1 }}>{s.val}</div>
            <div style={{ fontSize: 10, color: C.t3, marginTop: 3 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Connector grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px,1fr))", gap: 11,
      }}>
        {CONNECTORS.map((c) => {
          const isConn = connected.has(c.id);
          return (
            <div key={c.id} style={{
              background: C.bgCard,
              border: `1px solid ${isConn ? "rgba(16,185,129,0.28)" : C.bd}`,
              borderRadius: 12, padding: 16, transition: "border-color .2s",
            }}>
              <div style={{
                width: 38, height: 38, borderRadius: 8, border: `1px solid ${C.bd}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 19, marginBottom: 11,
              }}>
                {c.emoji}
              </div>
              <div style={{ fontSize: 12, fontWeight: 600, color: C.t1, marginBottom: 3 }}>{c.name}</div>
              <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.5, marginBottom: 12 }}>{c.desc}</div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                {isConn
                  ? <Badge label="● Connected" color={C.green} bg="rgba(16,185,129,0.12)" border="rgba(16,185,129,0.25)" />
                  : <Badge label="Available" color={C.t2} bg="rgba(148,163,184,0.08)" border={C.bd} />}
                <Btn
                  variant={isConn ? "danger" : "ghost"}
                  style={{ fontSize: 10, padding: "3px 10px" }}
                  onClick={() => {
                    setConnected((prev) => {
                      const next = new Set(prev);
                      if (next.has(c.id)) next.delete(c.id);
                      else next.add(c.id);
                      return next;
                    });
                  }}
                >
                  {isConn ? "Disconnect" : "Connect"}
                </Btn>
              </div>
            </div>
          );
        })}
      </div>

      <div style={{
        marginTop: 20, padding: "12px 16px",
        background: "rgba(37,99,235,0.06)", border: `1px solid rgba(37,99,235,0.2)`,
        borderRadius: 10, fontSize: 12, color: C.t2, lineHeight: 1.6,
      }}>
        <strong style={{ color: C.t1 }}>Enterprise connectors</strong> — Need Salesforce CRM, SAP, or a custom REST source?{" "}
        <span style={{ color: C.accent, cursor: "pointer", fontWeight: 500 }}>Contact your admin or upgrade your plan →</span>
      </div>
    </div>
  );
}

// ─── Billing panel ───────────────────────────────────────────────────────────────
type BillingOrg = { id: string; name: string };
type BillingPlan = {
  organization_id: string;
  plan: string;
  subscription_status: string | null;
  connectors_max: number;
  seats_max: number;
  queries_per_month: number;
  queries_per_day: number;
  queries_per_hour: number | null;
  queries_used_month: number;
  connectors_used: number;
  seats_used: number;
  billing_grace_until: string | null;
};
type BillingPlanTier = {
  plan: string;
  price_id: string | null;
  price_display?: string | null;
  connectors_max: number;
  seats_max: number;
  queries_per_month: number;
  queries_per_day: number;
  queries_per_hour: number | null;
};
type BillingPlansCatalog = {
  organization_id: string;
  current_plan: string;
  plans: BillingPlanTier[];
};
type BillingCheckoutResponse = {
  checkout_url: string;
  session_id: string;
};
type BillingPortalResponse = {
  portal_url: string;
};
type BillingInvoice = {
  invoice_id: string;
  number: string | null;
  status: string | null;
  currency: string;
  total_cents: number;
  amount_due_cents: number;
  amount_paid_cents: number;
  created_at: string | null;
  period_start_at: string | null;
  period_end_at: string | null;
  hosted_invoice_url: string | null;
  invoice_pdf_url: string | null;
};
type BillingInvoicesResponse = {
  organization_id: string;
  stripe_enabled: boolean;
  customer_id: string | null;
  invoices: BillingInvoice[];
};

function formatBillingPlanLabel(p: string) {
  return p ? `${p[0].toUpperCase()}${p.slice(1)}` : "Unknown";
}

function formatSubscriptionStatusLabel(raw: string | null) {
  if (!raw) return "Active";
  const s = raw.replace(/_/g, " ");
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

function BillingPanel() {
  const C = useOrgShellTokens();
  const planCompareRef = useRef<HTMLDivElement | null>(null);
  const [orgs, setOrgs] = useState<BillingOrg[]>([]);
  const [orgId, setOrgId] = useState("");
  const [plan, setPlan] = useState<BillingPlan | null>(null);
  const [planCatalog, setPlanCatalog] = useState<BillingPlanTier[]>([]);
  const [stripeEnabled, setStripeEnabled] = useState(false);
  const [rateLimitRedis, setRateLimitRedis] = useState(true);
  const [contactSalesEmail, setContactSalesEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [portalBusy, setPortalBusy] = useState(false);
  const [checkoutPlanBusy, setCheckoutPlanBusy] = useState<string | null>(null);
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<BillingOrg[]>("/organizations/me")
      .then((r) => {
        setOrgs(r.data);
        setOrgId((prev) => prev || r.data[0]?.id || "");
      })
      .catch((e) => setErr(apiErrorMessage(e)));
    void fetchPublicConfig()
      .then((cfg) => {
        setStripeEnabled(Boolean(cfg.features?.stripe_billing));
        setRateLimitRedis(Boolean(cfg.rate_limit_redis_enabled));
        setContactSalesEmail(typeof cfg.contact_sales_email === "string" && cfg.contact_sales_email.trim()
          ? cfg.contact_sales_email.trim()
          : null);
      })
      .catch(() => {
        setStripeEnabled(false);
        setRateLimitRedis(true);
        setContactSalesEmail(null);
      });
  }, []);

  const reloadBilling = useCallback(() => {
    if (!orgId) return;
    setErr(null);
    setLoading(true);
    void Promise.all([
      api.get<BillingPlan>(`/organizations/${orgId}/billing/plan`),
      api.get<BillingPlansCatalog>(`/organizations/${orgId}/billing/plans`),
      api.get<BillingInvoicesResponse>(`/organizations/${orgId}/billing/invoices`),
    ])
      .then(([planResp, catalogResp, invoiceResp]) => {
        setPlan(planResp.data);
        setPlanCatalog(Array.isArray(catalogResp.data.plans) ? catalogResp.data.plans : []);
        setInvoices(Array.isArray(invoiceResp.data.invoices) ? invoiceResp.data.invoices : []);
      })
      .catch((e) => setErr(apiErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [orgId]);

  useEffect(() => {
    reloadBilling();
  }, [reloadBilling]);

  async function openPortal() {
    if (!orgId) return;
    setPortalBusy(true);
    setErr(null);
    try {
      const { data } = await api.post<BillingPortalResponse>(`/organizations/${orgId}/billing/portal`, {
        return_url: window.location.href,
      });
      if (data.portal_url) window.location.assign(data.portal_url);
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setPortalBusy(false);
    }
  }

  async function startCheckout(tier: BillingPlanTier) {
    if (!orgId || !tier.price_id) return;
    setCheckoutPlanBusy(tier.plan);
    setErr(null);
    try {
      const { data } = await api.post<BillingCheckoutResponse>(`/organizations/${orgId}/billing/checkout`, {
        price_id: tier.price_id,
        success_url: window.location.href,
        cancel_url: window.location.href,
      });
      if (data.checkout_url) window.location.assign(data.checkout_url);
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setCheckoutPlanBusy(null);
    }
  }

  const currentTier = useMemo(
    () => (plan ? planCatalog.find((t) => t.plan === plan.plan) ?? null : null),
    [planCatalog, plan],
  );
  const seatPct = plan ? Math.min(100, Math.round((plan.seats_used / Math.max(plan.seats_max, 1)) * 100)) : 0;
  const connPct = plan ? Math.min(100, Math.round((plan.connectors_used / Math.max(plan.connectors_max, 1)) * 100)) : 0;
  const queriesUsed = plan ? Math.max(0, plan.queries_used_month ?? 0) : 0;
  const queryPct = plan
    ? Math.min(100, Math.round((queriesUsed / Math.max(plan.queries_per_month, 1)) * 100))
    : 0;
  const orderedCatalog = useMemo(() => {
    const order = ["free", "starter", "team", "business", "scale", "admin"];
    return [...planCatalog].sort(
      (a, b) => order.indexOf(a.plan) - order.indexOf(b.plan),
    );
  }, [planCatalog]);
  const billingHeroSubtitle = useMemo(() => {
    if (!plan) return "Live usage and entitlements";
    const name = formatBillingPlanLabel(plan.plan);
    if (plan.billing_grace_until) {
      try {
        const g = new Date(plan.billing_grace_until).toLocaleDateString();
        return `${name} plan · Grace until ${g}`;
      } catch {
        /* ignore */
      }
    }
    const st = (plan.subscription_status || "").toLowerCase();
    if (st === "trialing") return `${name} plan · Trial`;
    if (st === "past_due") return `${name} plan · Payment issue — update in Stripe`;
    if (st === "canceled" || st === "cancelled") return `${name} plan · Subscription ended`;
    if (st === "active") return `${name} plan · Renews via Stripe`;
    if (st) return `${name} plan · ${st.replace(/_/g, " ")}`;
    return `${name} plan · Usage and caps below`;
  }, [plan]);
  const upgradeTrackOrder = useMemo(() => ["free", "starter", "team", "business", "scale"], []);
  const upgradeTargetTier = useMemo(() => {
    if (!plan) return null;
    const idx = upgradeTrackOrder.indexOf(plan.plan);
    if (idx < 0 || idx >= upgradeTrackOrder.length - 1) return null;
    const nextKey = upgradeTrackOrder[idx + 1];
    return orderedCatalog.find((t) => t.plan === nextKey) ?? null;
  }, [plan, orderedCatalog, upgradeTrackOrder]);
  const upgradeHook = useMemo(() => {
    if (connPct >= 70) return `You are using about ${connPct}% of your connector allowance.`;
    if (connPct >= 55) return `You are using about ${connPct}% of your connector allowance.`;
    if (seatPct >= 70) return `You are using about ${seatPct}% of included seats.`;
    if (queryPct >= 75) return `You are approaching this month's query cap.`;
    if (queryPct >= 55) return `Query usage is about ${queryPct}% of the monthly allowance.`;
    return "Higher tiers include more seats, connectors, and monthly queries.";
  }, [connPct, seatPct, queryPct]);
  const latestInvoicePdf = useMemo(() => {
    for (const inv of invoices) {
      if (inv.invoice_pdf_url) return inv;
    }
    return null;
  }, [invoices]);
  const planFeatureBullets = useMemo(() => {
    const tier = currentTier;
    if (!tier) return [];
    const pk = tier.plan;
    const support =
      pk === "free" || pk === "starter"
        ? "Standard support"
        : pk === "team"
          ? "Email + chat support"
          : pk === "business"
            ? "Priority support · admin-friendly limits"
            : pk === "scale"
              ? "Priority support · expanded caps"
              : "Platform administration";
    return [
      `${tier.seats_max.toLocaleString()} users included`,
      `${tier.queries_per_month.toLocaleString()} queries / month`,
      `${tier.connectors_max.toLocaleString()} connectors included`,
      support,
      ...(pk === "business" || pk === "scale" ? ["Workspace-scoped connectors"] : []),
    ];
  }, [currentTier]);
  const fmtMoney = (currency: string, cents: number) => {
    try {
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: (currency || "USD").toUpperCase(),
      }).format((cents || 0) / 100);
    } catch {
      return `${((cents || 0) / 100).toFixed(2)} ${(currency || "USD").toUpperCase()}`;
    }
  };

  const UsageRow = ({
    label,
    left,
    pct,
    color,
  }: {
    label: string;
    left: string;
    pct: number;
    color: string;
  }) => (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.t2, marginBottom: 6 }}>
        <span>{label}</span>
        <span style={{ fontFamily: C.mono }}>{left}</span>
      </div>
      <div style={{ height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 999, opacity: 0.9 }} />
      </div>
    </div>
  );

  const priceHeadline = (() => {
    if (!plan || !currentTier) return "—";
    if (currentTier.price_display?.trim()) return currentTier.price_display;
    if (plan.plan === "free") return "$0 · included limits";
    if (plan.plan === "admin") return "Internal";
    return stripeEnabled ? "Billed in Stripe" : "Set price labels or Stripe prices";
  })();
  const subBadgeBad = plan?.subscription_status?.toLowerCase() === "past_due";
  const canUpgradeCheckout =
    Boolean(upgradeTargetTier && stripeEnabled && upgradeTargetTier.price_id && upgradeTargetTier.plan !== plan?.plan);

  return (
    <div style={{ padding: "22px 26px", overflowY: "auto", height: "100%", display: "flex", flexDirection: "column", gap: 14 }}>
      <div
        style={{
          background: C.bgCard,
          border: `1px solid ${C.bd}`,
          borderRadius: 16,
          padding: "18px 20px",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>Usage & Billing</div>
            <div style={{ fontSize: 12, color: C.t2 }}>{billingHeroSubtitle}</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Btn variant="ghost" onClick={() => reloadBilling()} disabled={loading} style={{ fontSize: 11 }}>
              {loading ? "Refreshing…" : "Refresh"}
            </Btn>
            <Btn
              variant="primary"
              onClick={() => void openPortal()}
              disabled={!stripeEnabled || portalBusy || !orgId}
              style={{ fontSize: 11 }}
            >
              {portalBusy ? "Opening…" : stripeEnabled ? "Billing portal" : "Stripe not configured"}
            </Btn>
          </div>
        </div>
      </div>

      {err && (
        <div style={{ padding: "10px 14px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8, fontSize: 12, color: C.red }}>
          {err}
        </div>
      )}

      <div style={{ maxWidth: 440 }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
          Organization
        </div>
        <select
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          style={{
            width: "100%",
            background: C.bgCard,
            border: `1px solid ${C.bd}`,
            borderRadius: 8,
            padding: "9px 10px",
            fontSize: 12,
            color: C.t1,
            fontFamily: C.sans,
            outline: "none",
          }}
        >
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </div>

      <div
        style={{
          fontSize: 11,
          color: C.t2,
          lineHeight: 1.55,
          padding: "11px 14px",
          borderRadius: 10,
          border: `1px solid ${C.bd}`,
          background: "rgba(255,255,255,0.02)",
        }}
      >
        <strong style={{ color: C.t1 }}>Billing portal.</strong>{" "}
        Payment methods, invoices, and subscription changes use Stripe&apos;s hosted{" "}
        <a href="https://docs.stripe.com/customer-management" target="_blank" rel="noreferrer" style={{ color: C.accent }}>
          Customer Portal
        </a>
        .{" "}
        <button
          type="button"
          onClick={() => void openPortal()}
          disabled={!stripeEnabled || portalBusy || !orgId}
          style={{
            background: "none",
            border: "none",
            padding: 0,
            margin: 0,
            color: C.accent,
            fontWeight: 600,
            fontFamily: C.sans,
            cursor: !stripeEnabled || portalBusy || !orgId ? "default" : "pointer",
          }}
        >
          {portalBusy ? "Opening portal…" : "Open Stripe portal"}
        </button>
        {" · "}
        <span style={{ color: C.t3 }}>docs/configuration/STRIPE.md</span>
      </div>

      {plan && (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1fr) minmax(260px, 320px)",
              gap: 14,
              alignItems: "start",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
              <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "18px 18px 16px" }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 10 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: C.t1, marginBottom: 4 }}>
                      {formatBillingPlanLabel(plan.plan)} plan
                    </div>
                    <div style={{ fontSize: 26, fontWeight: 800, color: C.t1, letterSpacing: "-0.02em" }}>{priceHeadline}</div>
                  </div>
                  <Badge
                    label={formatSubscriptionStatusLabel(plan.subscription_status)}
                    color={subBadgeBad ? C.red : C.accent}
                    bg={subBadgeBad ? "rgba(239,68,68,0.12)" : "rgba(37,99,235,0.12)"}
                    border={subBadgeBad ? "rgba(239,68,68,0.28)" : "rgba(37,99,235,0.25)"}
                  />
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "6px 14px",
                    fontSize: 11,
                    color: C.t2,
                    lineHeight: 1.45,
                    marginBottom: 14,
                  }}
                >
                  {planFeatureBullets.map((line, i) => (
                    <div key={`pf-${i}-${line}`} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                      <span style={{ color: C.accent, marginTop: 2 }}>●</span>
                      <span>{line}</span>
                    </div>
                  ))}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
                  <Btn variant="ghost" onClick={() => planCompareRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })} style={{ fontSize: 11 }}>
                    Change plan
                  </Btn>
                  <Btn
                    variant="ghost"
                    onClick={() => {
                      if (latestInvoicePdf?.invoice_pdf_url) {
                        window.open(latestInvoicePdf.invoice_pdf_url, "_blank", "noopener,noreferrer");
                      } else {
                        void openPortal();
                      }
                    }}
                    disabled={!stripeEnabled && !latestInvoicePdf}
                    style={{ fontSize: 11 }}
                  >
                    {latestInvoicePdf ? "Download invoice" : "Invoices in Stripe"}
                  </Btn>
                </div>
                <div style={{ borderTop: `1px solid ${C.bd}`, paddingTop: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.t1, marginBottom: 10 }}>Current period usage</div>
                  <UsageRow
                    label="Queries (this month)"
                    left={`${queriesUsed.toLocaleString()} / ${plan.queries_per_month.toLocaleString()}`}
                    pct={queryPct}
                    color="#34d399"
                  />
                  {!rateLimitRedis && (
                    <div style={{ fontSize: 10, color: C.t3, marginTop: -4, marginBottom: 8 }}>
                      Redis rate-limit store is off; usage may show as zero until queries run with Redis enabled.
                    </div>
                  )}
                  <UsageRow
                    label="Team members"
                    left={`${plan.seats_used.toLocaleString()} / ${plan.seats_max.toLocaleString()}`}
                    pct={seatPct}
                    color={C.accent}
                  />
                  <UsageRow
                    label="Active connectors"
                    left={`${plan.connectors_used.toLocaleString()} / ${plan.connectors_max.toLocaleString()}`}
                    pct={connPct}
                    color={C.gold}
                  />
                  <div style={{ marginTop: 8, fontSize: 11, color: C.t2 }}>
                    Burst caps: {plan.queries_per_day.toLocaleString()} / day
                    {plan.queries_per_hour == null ? "" : ` · ${plan.queries_per_hour.toLocaleString()} / hour`}
                  </div>
                </div>
              </div>

              <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "14px 16px 12px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: C.t1 }}>Invoice history</div>
                  <div style={{ fontSize: 11, color: C.t3 }}>
                    {invoices.length > 0 ? `${invoices.length} recent` : "None yet"}
                  </div>
                </div>
                {invoices.length === 0 ? (
                  <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.5 }}>
                    Invoices appear after Stripe billing. Open the portal to add a payment method or review past charges.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {invoices.slice(0, 6).map((inv) => (
                      <div
                        key={inv.invoice_id}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "minmax(0,1.2fr) auto auto auto",
                          gap: 10,
                          alignItems: "center",
                          padding: "8px 10px",
                          borderRadius: 10,
                          border: `1px solid ${C.bd}`,
                          background: "rgba(255,255,255,0.02)",
                        }}
                      >
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 12, color: C.t1, fontWeight: 600 }}>
                            {inv.number || inv.invoice_id}
                          </div>
                          <div style={{ fontSize: 10, color: C.t3 }}>
                            {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : "—"}
                          </div>
                        </div>
                        <Badge
                          label={inv.status || "unknown"}
                          color={inv.status === "paid" ? C.green : C.t2}
                          bg={inv.status === "paid" ? "rgba(16,185,129,0.12)" : "rgba(148,163,184,0.15)"}
                          border={inv.status === "paid" ? "rgba(16,185,129,0.25)" : "rgba(148,163,184,0.25)"}
                        />
                        <span style={{ fontSize: 12, color: C.t1, fontFamily: C.mono }}>
                          {fmtMoney(inv.currency, inv.total_cents)}
                        </span>
                        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                          {inv.hosted_invoice_url && (
                            <a
                              href={inv.hosted_invoice_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ fontSize: 11, color: C.accent, textDecoration: "none" }}
                            >
                              View
                            </a>
                          )}
                          {inv.invoice_pdf_url && (
                            <a
                              href={inv.invoice_pdf_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ fontSize: 11, color: C.accent, textDecoration: "none" }}
                            >
                              PDF
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div
                style={{
                  background: "linear-gradient(180deg, rgba(37,99,235,0.14) 0%, rgba(15,23,42,0.4) 100%)",
                  border: `1px solid rgba(37,99,235,0.35)`,
                  borderRadius: 14,
                  padding: "16px 16px 14px",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 800, color: C.t1, marginBottom: 8 }}>
                  {upgradeTargetTier ? `Upgrade to ${formatBillingPlanLabel(upgradeTargetTier.plan)}` : "You're on our top self-serve tier"}
                </div>
                <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.55, marginBottom: 12 }}>{upgradeHook}</div>
                {upgradeTargetTier?.price_display?.trim() && (
                  <div style={{ fontSize: 18, fontWeight: 800, color: C.t1, marginBottom: 12 }}>{upgradeTargetTier.price_display}</div>
                )}
                {upgradeTargetTier ? (
                  <Btn
                    variant="primary"
                    disabled={!canUpgradeCheckout || checkoutPlanBusy === upgradeTargetTier.plan}
                    onClick={() => void startCheckout(upgradeTargetTier)}
                    style={{ width: "100%", justifyContent: "center", fontSize: 12, padding: "10px 12px" }}
                  >
                    {checkoutPlanBusy === upgradeTargetTier.plan
                      ? "Redirecting…"
                      : canUpgradeCheckout
                        ? `Upgrade to ${formatBillingPlanLabel(upgradeTargetTier.plan)} →`
                        : stripeEnabled
                          ? "Configure Stripe price"
                          : "Stripe unavailable"}
                  </Btn>
                ) : (
                  <Btn variant="ghost" onClick={() => planCompareRef.current?.scrollIntoView({ behavior: "smooth" })} style={{ width: "100%", justifyContent: "center", fontSize: 11 }}>
                    View plans
                  </Btn>
                )}
              </div>

              <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "14px 16px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: C.t1, marginBottom: 4 }}>Payment method</div>
                    <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.45 }}>
                      Cards and bank debits are managed in Stripe Customer Portal.
                    </div>
                  </div>
                  <Btn
                    variant="ghost"
                    onClick={() => void openPortal()}
                    disabled={!stripeEnabled || portalBusy || !orgId}
                    style={{ fontSize: 11, flexShrink: 0 }}
                  >
                    Update
                  </Btn>
                </div>
              </div>

              <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "14px 16px" }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.t1, marginBottom: 6 }}>Need help?</div>
                <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.5, marginBottom: 10 }}>
                  Questions about your plan, invoices, or custom enterprise pricing?
                </div>
                {contactSalesEmail ? (
                  <a
                    href={`mailto:${contactSalesEmail}`}
                    style={{ fontSize: 12, color: C.accent, fontWeight: 600, textDecoration: "none" }}
                  >
                    Talk to sales →
                  </a>
                ) : (
                  <button
                    type="button"
                    onClick={() => void openPortal()}
                    disabled={!stripeEnabled}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: stripeEnabled ? "pointer" : "default",
                      fontSize: 12,
                      color: C.accent,
                      fontWeight: 600,
                      fontFamily: C.sans,
                    }}
                  >
                    Open billing portal →
                  </button>
                )}
              </div>

              <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "12px 14px" }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: C.t3, marginBottom: 6 }}>Plan controls</div>
                <Btn
                  variant="ghost"
                  onClick={() => void openPortal()}
                  disabled={!stripeEnabled || portalBusy || !orgId}
                  style={{ width: "100%", justifyContent: "center", marginBottom: 6, fontSize: 11 }}
                >
                  {portalBusy ? "Opening…" : "Manage subscription in Stripe"}
                </Btn>
                <Btn variant="ghost" onClick={() => reloadBilling()} disabled={loading} style={{ width: "100%", justifyContent: "center", fontSize: 11 }}>
                  {loading ? "Refreshing…" : "Refresh usage & limits"}
                </Btn>
                {!stripeEnabled && (
                  <div style={{ marginTop: 8, fontSize: 10, color: C.t3 }}>
                    Stripe is off in this environment; upgrade buttons need Checkout configured.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div ref={planCompareRef} style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "16px 16px 14px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: C.t1 }}>Plan comparison</div>
              <div style={{ fontSize: 11, color: C.t3 }}>Limits enforced by the API · checkout when Stripe is configured</div>
            </div>
            {orderedCatalog.length === 0 ? (
              <div style={{ fontSize: 12, color: C.t2 }}>No plan catalog available.</div>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 8 }}>
                {orderedCatalog.map((tier) => {
                  const active = tier.plan === plan.plan;
                  const canCheckout = stripeEnabled && Boolean(tier.price_id) && !active;
                  return (
                    <div
                      key={`plan-card-${tier.plan}`}
                      style={{
                        border: `1px solid ${active ? C.accent : C.bd}`,
                        background: active ? "rgba(37,99,235,0.08)" : "rgba(255,255,255,0.02)",
                        borderRadius: 10,
                        padding: "10px 10px 9px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                        <div style={{ fontSize: 12, fontWeight: 800, color: C.t1 }}>{formatBillingPlanLabel(tier.plan)}</div>
                        {active && (
                          <Badge
                            label="Current"
                            color={C.accent}
                            bg="rgba(37,99,235,0.12)"
                            border="rgba(37,99,235,0.25)"
                          />
                        )}
                      </div>
                      {tier.price_display?.trim() && (
                        <div style={{ fontSize: 12, fontWeight: 700, color: C.t1, marginBottom: 8 }}>{tier.price_display}</div>
                      )}
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11, color: C.t2, marginBottom: 10 }}>
                        <div>{tier.seats_max.toLocaleString()} seats</div>
                        <div>{tier.connectors_max.toLocaleString()} connectors</div>
                        <div>{tier.queries_per_day.toLocaleString()} queries/day</div>
                        <div>{tier.queries_per_month.toLocaleString()} queries/month</div>
                        <div>{tier.queries_per_hour == null ? "No hourly cap" : `${tier.queries_per_hour.toLocaleString()} queries/hour`}</div>
                      </div>
                      <Btn
                        variant={active ? "ghost" : "primary"}
                        disabled={active || !canCheckout || checkoutPlanBusy === tier.plan}
                        onClick={() => void startCheckout(tier)}
                        style={{ width: "100%", justifyContent: "center", fontSize: 11 }}
                      >
                        {active
                          ? "Current plan"
                          : checkoutPlanBusy === tier.plan
                            ? "Redirecting…"
                            : canCheckout
                              ? "Choose plan"
                              : !stripeEnabled
                                ? "Stripe unavailable"
                                : "Price not configured"}
                      </Btn>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

type AuditEvent = {
  id: string;
  created_at: string | null;
  actor_email: string;
  actor_role?: string | null;
  organization_id?: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  workspace_id: string | null;
  metadata: Record<string, unknown>;
};

type AuditCategory = "all" | "queries" | "admin" | "auth" | "sync" | "http" | "governance";

function parseAuditCategory(value: string | null): AuditCategory {
  if (
    value === "queries"
    || value === "admin"
    || value === "auth"
    || value === "sync"
    || value === "http"
    || value === "governance"
  ) {
    return value;
  }
  return "all";
}

/** Second click on the same category chip clears it (show all events again). */
function toggleAuditCategory(current: AuditCategory, chip: Exclude<AuditCategory, "all">): AuditCategory {
  return current === chip ? "all" : chip;
}

function formatAuditTimestampUtc(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
}

function parseAuditFailures(value: string | null): boolean {
  return value === "1" || value === "true";
}

function AuditPanel({
  orgs,
  selectedOrgId,
  workspaceScopeIds,
  workspaces = [],
}: {
  orgs: Org[];
  selectedOrgId: string;
  workspaceScopeIds?: string[];
  workspaces?: Workspace[];
}) {
  const C = useOrgShellTokens();
  const isWorkspaceScopedAudit = !!workspaceScopeIds && workspaceScopeIds.length > 0;
  const workspaceNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const w of workspaces) m.set(w.id, w.name);
    return m;
  }, [workspaces]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [action, setAction] = useState(() => searchParams.get("auditAction") ?? "");
  const [category, setCategory] = useState<AuditCategory>(() =>
    parseAuditCategory(searchParams.get("auditCategory")),
  );
  const [eventSearch, setEventSearch] = useState(() => searchParams.get("auditEvent") ?? "");
  const [userSearch, setUserSearch] = useState(() => searchParams.get("auditUser") ?? "");
  const [workspaceFilter, setWorkspaceFilter] = useState(() => searchParams.get("auditWorkspace") ?? "all");
  const [onlyFailures, setOnlyFailures] = useState(() => parseAuditFailures(searchParams.get("auditFailures")));
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const qAction = searchParams.get("auditAction") ?? "";
    const qCategory = parseAuditCategory(searchParams.get("auditCategory"));
    const qEvent = searchParams.get("auditEvent") ?? "";
    const qUser = searchParams.get("auditUser") ?? "";
    const qWorkspace = searchParams.get("auditWorkspace") ?? "all";
    const qFailures = parseAuditFailures(searchParams.get("auditFailures"));
    setAction((prev) => (prev === qAction ? prev : qAction));
    setCategory((prev) => (prev === qCategory ? prev : qCategory));
    setEventSearch((prev) => (prev === qEvent ? prev : qEvent));
    setUserSearch((prev) => (prev === qUser ? prev : qUser));
    setWorkspaceFilter((prev) => (prev === qWorkspace ? prev : qWorkspace));
    setOnlyFailures((prev) => (prev === qFailures ? prev : qFailures));
  }, [searchParams]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    const setOrDelete = (key: string, value: string | null) => {
      if (!value) next.delete(key);
      else next.set(key, value);
    };
    setOrDelete("auditAction", action.trim() || null);
    setOrDelete("auditCategory", category !== "all" ? category : null);
    setOrDelete("auditEvent", eventSearch.trim() || null);
    setOrDelete("auditUser", userSearch.trim() || null);
    setOrDelete("auditWorkspace", workspaceFilter !== "all" ? workspaceFilter : null);
    setOrDelete("auditFailures", onlyFailures ? "1" : null);
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [action, category, eventSearch, userSearch, workspaceFilter, onlyFailures, searchParams, setSearchParams]);

  const load = useCallback(async () => {
    if (!selectedOrgId) return;
    setErr(null);
    try {
      const { data } = await api.get<AuditEvent[]>(`/organizations/${selectedOrgId}/audit`, {
        params: {
          action: action || undefined,
          workspace_id: workspaceFilter !== "all" ? workspaceFilter : undefined,
          limit: 400,
        },
      });
      setRows(data);
    } catch (e) {
      setErr(apiErrorMessage(e));
    }
  }, [selectedOrgId, action, workspaceFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  function isFailureEvent(r: AuditEvent): boolean {
    const m = JSON.stringify(r.metadata || {}).toLowerCase();
    const a = r.action.toLowerCase();
    return (
      m.includes("error")
      || m.includes("failed")
      || m.includes("token_expired")
      || a.includes("failed")
      || a.includes("error")
    );
  }

  const workspaceOptions = useMemo(() => {
    const ids = new Set<string>();
    for (const id of workspaceScopeIds ?? []) ids.add(id);
    for (const r of rows) {
      if (r.workspace_id) ids.add(r.workspace_id);
    }
    return Array.from(ids).sort();
  }, [rows, workspaceScopeIds]);

  const filteredRows = rows.filter((r) => {
    const act = r.action.toLowerCase();
    const actor = (r.actor_email || "").toLowerCase();
    const text = `${r.action} ${r.target_type} ${JSON.stringify(r.metadata || {})}`.toLowerCase();
    if (category === "queries" && !act.includes("query")) return false;
    if (category === "admin" && !(act.includes("org") || act.includes("team") || act.includes("billing") || act.includes("admin"))) return false;
    if (category === "auth" && !(act.includes("auth") || act.includes("login") || act.includes("token"))) return false;
    if (category === "sync" && !(act.includes("sync") || act.includes("connector") || act.includes("document"))) return false;
    if (category === "http" && act !== "api_http_mutation") return false;
    if (
      category === "governance"
      && !/organization_|workspace_|member_|invite_|document_|connector_|chat_session|api_http_mutation/.test(act)
    ) {
      return false;
    }
    if (eventSearch && !text.includes(eventSearch.toLowerCase())) return false;
    if (userSearch && !actor.includes(userSearch.toLowerCase())) return false;
    if (workspaceFilter !== "all" && (r.workspace_id || "") !== workspaceFilter) return false;
    if (onlyFailures && !isFailureEvent(r)) return false;
    return true;
  });

  function actionClass(actionName: string) {
    const a = actionName.toLowerCase();
    if (a === "api_http_mutation") return "sk-action-tag achttp";
    if (a.includes("query")) return "sk-action-tag acq";
    if (a.includes("auth") || a.includes("login")) return "sk-action-tag acau";
    if (a.includes("sync") || a.includes("connector") || a.includes("document")) return "sk-action-tag acs";
    return "sk-action-tag aca";
  }

  function resultBadge(r: AuditEvent) {
    const fail = isFailureEvent(r);
    return fail ? <span className="badge bred">failure</span> : <span className="badge bgreen">recorded</span>;
  }

  function severityBadge(r: AuditEvent) {
    const a = r.action.toLowerCase();
    if (isFailureEvent(r)) return <span className="badge bred">error</span>;
    if (a.includes("delete") || a.includes("remove") || a.includes("revoke")) return <span className="badge byellow">warning</span>;
    return <span className="badge bblue">info</span>;
  }

  function exportCsv() {
    const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const header = [
      "timestamp_utc",
      "actor_email",
      "actor_role",
      "event_type",
      "organization_id",
      "target_type",
      "target_id",
      "workspace_id",
      "outcome",
      "metadata_json",
    ].join(",");
    const body = filteredRows
      .map((r) =>
        [
          escape(r.created_at || ""),
          escape(r.actor_email || "system"),
          escape(r.actor_role || ""),
          escape(r.action),
          escape(r.organization_id || ""),
          escape(r.target_type || ""),
          escape(r.target_id || ""),
          escape(r.workspace_id || ""),
          escape(isFailureEvent(r) ? "failure" : "recorded"),
          escape(JSON.stringify(r.metadata || {})),
        ].join(","),
      )
      .join("\n");
    const blob = new Blob([`${header}\n${body}`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-${selectedOrgId || "org"}-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const selectedOrgName = orgs.find((o) => o.id === selectedOrgId)?.name ?? null;

  return (
    <div className="sk-audit-page" style={{ padding: "22px 26px", overflowY: "auto", height: "100%" }}>
      <div className="sk-panel sk-audit-header">
        <div>
          <div className="sk-connectors-title">Audit log</div>
          <div className="sk-connectors-sub">
            Append-only style trail for this organization{selectedOrgName ? ` · ${selectedOrgName}` : ""}. Timestamps are
            stored in UTC. Rows include domain events and successful HTTP mutations when scope can be inferred from the
            request path.
          </div>
          {isWorkspaceScopedAudit && (
            <div
              style={{
                marginTop: 10,
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                borderRadius: 999,
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 700,
                color: C.gold,
                background: "rgba(245,158,11,0.12)",
                border: "1px solid rgba(245,158,11,0.3)",
              }}
            >
              Workspace-scoped access
            </div>
          )}
        </div>
        <button className="sk-btn secondary" type="button" onClick={exportCsv} disabled={filteredRows.length === 0}>
          Export CSV
        </button>
      </div>
      <div
        className="sk-audit-compliance-note"
        style={{
          marginBottom: 14,
          padding: "10px 14px",
          borderRadius: 10,
          border: `1px solid ${C.bd}`,
          background: C.bgE,
          fontSize: 11,
          lineHeight: 1.55,
        }}
      >
        <strong>Retention &amp; review:</strong> Use filters and CSV export for periodic access
        reviews. Correlation: HTTP mutation rows include <span className="sk-mono">request_id</span> when the edge
        middleware captured it.
      </div>
      {err && <p className="sk-error">{err}</p>}
      {!selectedOrgId && (
        <p className="sk-audit-empty-hint">Select an organization first to view the audit log.</p>
      )}
      <div className="sk-panel sk-spaced" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: "0.75rem", maxWidth: 980 }}>
        <div>
          <label className="sk-label">Action filter</label>
          <Input value={action} onChange={setAction} placeholder="organization_updated" />
        </div>
        <div>
          <label className="sk-label">User filter</label>
          <Input value={userSearch} onChange={setUserSearch} placeholder="user@company.com" />
        </div>
        <div>
          <label className="sk-label">Workspace</label>
          <select
            className="sk-input"
            value={workspaceFilter}
            onChange={(e) => setWorkspaceFilter(e.target.value)}
          >
            <option value="all">All workspaces</option>
            {workspaceOptions.map((id) => (
              <option key={id} value={id}>
                {workspaceNameById.get(id) ?? `${id.slice(0, 8)}…`}
              </option>
            ))}
          </select>
        </div>
        <div style={{ alignSelf: "end" }}>
          <button className="sk-btn secondary" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </div>

      <div className="sk-audit-filters">
        <button type="button" className={`sk-filter-chip ${category === "all" ? "on" : ""}`} onClick={() => setCategory("all")}>
          All events
        </button>
        <button
          type="button"
          className={`sk-filter-chip ${category === "queries" ? "on" : ""}`}
          onClick={() => setCategory((c) => toggleAuditCategory(c, "queries"))}
        >
          Queries
        </button>
        <button
          type="button"
          className={`sk-filter-chip ${category === "admin" ? "on" : ""}`}
          onClick={() => setCategory((c) => toggleAuditCategory(c, "admin"))}
        >
          Admin
        </button>
        <button
          type="button"
          className={`sk-filter-chip ${category === "auth" ? "on" : ""}`}
          onClick={() => setCategory((c) => toggleAuditCategory(c, "auth"))}
        >
          Auth
        </button>
        <button
          type="button"
          className={`sk-filter-chip ${category === "sync" ? "on" : ""}`}
          onClick={() => setCategory((c) => toggleAuditCategory(c, "sync"))}
        >
          Sync
        </button>
        <button
          type="button"
          className={`sk-filter-chip ${category === "governance" ? "on" : ""}`}
          onClick={() => setCategory((c) => toggleAuditCategory(c, "governance"))}
        >
          Governance
        </button>
        <button
          type="button"
          className={`sk-filter-chip ${category === "http" ? "on" : ""}`}
          onClick={() => setCategory((c) => toggleAuditCategory(c, "http"))}
        >
          HTTP API
        </button>
        <Input value={eventSearch} onChange={setEventSearch} placeholder="Search events..." style={{ maxWidth: 220 }} />
        <button
          type="button"
          className={`sk-filter-chip ${onlyFailures ? "on" : ""}`}
          onClick={() => setOnlyFailures((v) => !v)}
        >
          Failures only
        </button>
      </div>

      <div className="sk-panel sk-audit-table-wrap" style={{ overflow: "auto" }}>
        <table className="sk-audit-table">
          <thead>
            <tr>
              <th>Timestamp (UTC)</th>
              <th>Actor</th>
              <th>Role</th>
              <th>Event type</th>
              <th>Target</th>
              <th>Workspace</th>
              <th>Severity</th>
              <th>Outcome</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((r) => {
              const expanded = expandedId === r.id;
              const wsLabel = r.workspace_id
                ? (workspaceNameById.get(r.workspace_id) ?? `${r.workspace_id.slice(0, 8)}…`)
                : "—";
              return (
                <Fragment key={r.id}>
                  <tr>
                    <td className="sk-audit-ts">{formatAuditTimestampUtc(r.created_at)}</td>
                    <td>{r.actor_email || "—"}</td>
                    <td className="sk-mono sk-audit-role">{r.actor_role || "—"}</td>
                    <td>
                      <span className={actionClass(r.action)} title={r.action}>{r.action}</span>
                    </td>
                    <td className="sk-mono sk-audit-target">
                      {r.target_type || "—"}
                      {r.target_id ? ` · ${r.target_id.slice(0, 8)}…` : ""}
                    </td>
                    <td className="sk-audit-ws" title={r.workspace_id || undefined}>{wsLabel}</td>
                    <td>{severityBadge(r)}</td>
                    <td>{resultBadge(r)}</td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        type="button"
                        className="sk-btn secondary"
                        style={{ padding: "0.2rem 0.45rem", fontSize: "0.66rem" }}
                        onClick={() => setExpandedId((cur) => (cur === r.id ? null : r.id))}
                      >
                        {expanded ? "Hide" : "Details"}
                      </button>
                    </td>
                  </tr>
                  {expanded && (
                    <tr className="sk-audit-detail-row">
                      <td colSpan={9} style={{ padding: "10px 12px", background: C.bgE, borderBottom: `1px solid ${C.bd}` }}>
                        <div style={{ display: "grid", gap: 8 }}>
                          <div style={{ fontSize: 11, color: C.t2 }}>
                            <strong style={{ color: C.t1 }}>Organization ID:</strong>{" "}
                            <span className="sk-mono">{r.organization_id || selectedOrgId || "—"}</span>
                          </div>
                          <div style={{ fontSize: 11, color: C.t2 }}>
                            <strong style={{ color: C.t1 }}>Target ID:</strong>{" "}
                            <span className="sk-mono">{r.target_id || "—"}</span>
                          </div>
                          <div style={{ fontSize: 11, color: C.t2 }}>
                            <strong style={{ color: C.t1 }}>Workspace ID:</strong>{" "}
                            <span className="sk-mono">{r.workspace_id || "—"}</span>
                          </div>
                          <div style={{ fontSize: 11, color: C.t2 }}>
                            <strong style={{ color: C.t1 }}>Metadata</strong>
                          </div>
                          <pre
                            className="sk-mono sk-audit-metadata-pre"
                            style={{
                              margin: 0,
                              fontSize: 11,
                              lineHeight: 1.45,
                              whiteSpace: "pre-wrap",
                              background: C.bgCard,
                              border: `1px solid ${C.bd}`,
                              borderRadius: 8,
                              padding: "8px 10px",
                            }}
                          >
                            {JSON.stringify(r.metadata || {}, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {filteredRows.length === 0 && <p className="sk-audit-empty-hint">No audit events for this scope.</p>}
      </div>
    </div>
  );
}

function SettingsPanel({
  orgs,
  selectedOrgId,
  onSelectOrg,
  onSavedOrg,
  onSavedWorkspace,
  onOrgDeleted,
  isPlatformOwner,
  workspaces,
  canManageOrgSettings,
  canManageWorkspaceSettings,
}: {
  orgs: Org[];
  selectedOrgId: string;
  onSelectOrg: (orgId: string) => void;
  onSavedOrg: (updated: Org) => void;
  onSavedWorkspace: (updated: Workspace) => void;
  onOrgDeleted: () => Promise<void> | void;
  isPlatformOwner: boolean;
  workspaces: Workspace[];
  canManageOrgSettings: boolean;
  canManageWorkspaceSettings: boolean;
}) {
  const C = useOrgShellTokens();
  const selectedOrg = orgs.find((o) => o.id === selectedOrgId) ?? null;
  const isWorkspaceScopedSettings = canManageWorkspaceSettings && !canManageOrgSettings;
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string>("");
  const selectedWorkspace =
    workspaces.find((ws) => ws.id === selectedWorkspaceId) ?? (workspaces.length > 0 ? workspaces[0] : null);

  useEffect(() => {
    if (!workspaces.length) {
      setSelectedWorkspaceId("");
      return;
    }
    if (!selectedWorkspaceId || !workspaces.some((ws) => ws.id === selectedWorkspaceId)) {
      setSelectedWorkspaceId(workspaces[0].id);
    }
  }, [workspaces, selectedWorkspaceId]);

  return (
    <div style={{ padding: "22px 26px", overflowY: "auto", height: "100%" }}>
      <div style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 14,
        padding: "16px 18px",
        marginBottom: 12,
      }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>Settings</div>
        <div style={{ fontSize: 12, color: C.t2 }}>
          Organization profile and runtime/public configuration.
        </div>
        {isWorkspaceScopedSettings && (
          <div
            style={{
              marginTop: 10,
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              borderRadius: 999,
              padding: "4px 10px",
              fontSize: 11,
              fontWeight: 700,
              color: C.gold,
              background: "rgba(245,158,11,0.12)",
              border: "1px solid rgba(245,158,11,0.3)",
            }}
          >
            Workspace-scoped access
          </div>
        )}
      </div>
      <div style={{ maxWidth: 420, marginBottom: 12 }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
          Organization
        </div>
        <select
          value={selectedOrgId}
          onChange={(e) => onSelectOrg(e.target.value)}
          style={{
            width: "100%",
            background: C.bgCard,
            border: `1px solid ${C.bd}`,
            borderRadius: 8,
            padding: "9px 10px",
            fontSize: 12,
            color: C.t1,
            fontFamily: C.sans,
            outline: "none",
          }}
        >
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </div>
      {canManageOrgSettings && selectedOrg ? (
        <OrganizationSettingsPanel
          org={selectedOrg}
          onSaved={onSavedOrg}
          showDangerZone
          onOrgDeleted={onOrgDeleted}
          canManageCloudCredentials={canManageOrgSettings}
        />
      ) : canManageWorkspaceSettings ? (
        <>
          <div style={{ maxWidth: 420, marginBottom: 12 }}>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: C.t3,
                marginBottom: 6,
              }}
            >
              Workspace
            </div>
            <select
              value={selectedWorkspace?.id ?? ""}
              onChange={(e) => setSelectedWorkspaceId(e.target.value)}
              className="sk-input"
            >
              {workspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name}
                </option>
              ))}
            </select>
          </div>
          {selectedWorkspace ? (
            <WorkspaceSettingsPanel
              ws={selectedWorkspace}
              onSaved={onSavedWorkspace}
              workspaceCountInOrg={workspaces.length}
              showDangerZone={false}
            />
          ) : (
            <p className="sk-muted">No workspace settings available in this organization.</p>
          )}
        </>
      ) : (
        <p className="sk-muted">You do not have settings access in this organization.</p>
      )}
    </div>
  );
}

// ─── Upload modal (triggered from workspace row) ───────────────────────────────
function UploadModal({ ws, onClose }: { ws: Workspace; onClose: () => void }) {
  const C = useOrgShellTokens();
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setErr(null);
    setOk(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const { data } = await api.post<{ filename: string; chunk_count: number }>(
        `/documents/workspaces/${ws.id}/upload`, body,
      );
      setOk(`"${data.filename}" indexed — ${data.chunk_count} chunks.`);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
    }}
      onClick={onClose}
    >
      <div
        style={{
          background: C.bgCard, border: `1px solid ${C.bd2}`, borderRadius: 16,
          padding: 28, width: "100%", maxWidth: 440, position: "relative",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontFamily: C.serif, fontSize: 20, color: C.t1, marginBottom: 4 }}>
          Upload to <em style={{ fontStyle: "italic" }}>{ws.name}</em>
        </div>
        <div style={{ fontSize: 12, color: C.t2, marginBottom: 20 }}>
          Tier 1–2 formats (PDF, DOCX, PPTX, XLS/XLSX, CSV, RTF, TXT, MD, HTML) — max 50 MB.
        </div>

        <div
          style={{
            background: C.bgE, border: `2px dashed ${C.bd2}`, borderRadius: 10,
            padding: "24px 16px", textAlign: "center", cursor: "pointer", marginBottom: 16,
          }}
          onClick={() => fileRef.current?.click()}
        >
          <div style={{ fontSize: 28, marginBottom: 6 }}>📁</div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.t1, marginBottom: 2 }}>
            {uploading ? "Indexing…" : "Click to select a file"}
          </div>
          <div style={{ fontSize: 10, color: C.t3 }}>PDF, DOCX, PPTX, XLSX, CSV, RTF, TXT, MD, HTML · Max 50 MB</div>
          <input ref={fileRef} type="file" accept={DOCUMENT_UPLOAD_ACCEPT} style={{ display: "none" }} onChange={handleUpload} disabled={uploading} />
        </div>

        {err && <div style={{ fontSize: 11, color: C.red, marginBottom: 10 }}>✗ {err}</div>}
        {ok && <div style={{ fontSize: 11, color: C.green, marginBottom: 10 }}>✓ {ok}</div>}

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Btn variant="ghost" onClick={onClose}>Close</Btn>
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
type HomePageContentProps = {
  orgs: Org[];
  setOrgs: Dispatch<SetStateAction<Org[]>>;
  loading: boolean;
  err: string | null;
  setErr: Dispatch<SetStateAction<string | null>>;
  loadOrgs: () => Promise<void>;
  brightMode: boolean;
  setBrightMode: Dispatch<SetStateAction<boolean>>;
};

function HomePageContent({
  orgs,
  setOrgs,
  loading,
  err,
  setErr,
  loadOrgs,
  brightMode,
  setBrightMode,
}: HomePageContentProps) {
  const { user, logout } = useAuth();
  const isMemberOnlyUser =
    !user?.is_platform_owner
    && (user?.org_ids_as_owner ?? []).length === 0
    && (user?.org_ids_as_workspace_admin ?? []).length === 0;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialPanelFromUrl = panelFromQuery(searchParams.get("panel"));
  const {
    navigationScope,
    activeOrganizationId,
    activeWorkspaceId: ctxWorkspaceId,
    activeWorkspaceName: ctxWorkspaceName,
    setActiveWorkspaceContext,
    enterOrganization,
    exitToPlatform,
    needsOrganizationContext,
    isPlatformOwner,
  } = usePlatformNavigation();

  const selectedOrgId = activeOrganizationId ?? "";

  // Create org form
  const [showCreateOrg, setShowCreateOrg] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  /** Defaults favor self-hosted Ollama; platform owner can switch before create. */
  const [newOrgChatProv, setNewOrgChatProv] = useState<OrgChatProvider>("ollama");
  const [newOrgChatModel, setNewOrgChatModel] = useState("");
  const [newOrgOllamaBase, setNewOrgOllamaBase] = useState("");
  const [creating, setCreating] = useState(false);

  const {
    panel,
    setPanel,
    workspaces,
    setWorkspaces,
    allWorkspaces,
    setAllWorkspaces,
    workspaceCountByOrg,
    loadingWs,
    workspacesReloadNonce,
    setWorkspacesReloadNonce,
    jumpToWsId,
    setJumpToWsId,
    orgScreen,
    setOrgScreen,
    jumpToChatWsId,
    setJumpToChatWsId,
    chatWorkspaceId,
    setChatWorkspaceId,
    onEmbeddedChatWorkspaceChange,
    uploadWs,
    setUploadWs,
    scopedWorkspaces,
    workspaceInContext,
  } = useHomeWorkspaceState({
    orgs,
    selectedOrgId,
    userIsPlatformOwner: !!user?.is_platform_owner,
    memberChatOnly: isMemberOnlyUser,
    initialPanel: initialPanelFromUrl,
    api,
    ctxWorkspaceId,
    ctxWorkspaceName,
    setActiveWorkspaceContext,
  });

  // Sync URL → panel only when the query string changes (back/forward, deep link).
  // Do not depend on `panel`: after Launch Chat, `panel` becomes `chats` before
  // the next effect updates `?panel=`, and reading stale params would revert the panel.
  useEffect(() => {
    const qPanel = panelFromQuery(searchParams.get("panel"));
    if (!qPanel) return;
    setPanel((current) => (qPanel === current ? current : qPanel));
  }, [searchParams, setPanel]);

  // Always persist `panel` in the query string (including platform / dashboard / orgs).
  // Omitting it made `current === panel` false whenever the URL had no `panel` but state
  // was orgs|dashboard|platform, so this effect kept calling setSearchParams and broke nav.
  useEffect(() => {
    const current = panelFromQuery(searchParams.get("panel"));
    if (current === panel) return;
    const next = new URLSearchParams(searchParams);
    next.set("panel", panel);
    setSearchParams(next, { replace: true });
  }, [panel, searchParams, setSearchParams]);

  void useRef; // silence unused-import (used in UploadModal + DocumentsPanel)

  const { orgHasIndexedDocuments } = useOrgKnowledgeGate({
    api,
    selectedOrgId,
    scopedWorkspaces,
    isPlatformOwner,
    panel,
    setPanel,
  });

  async function createOrg(e: FormEvent) {
    e.preventDefault();
    if (!user?.is_platform_owner) return;
    setCreating(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = {
        name: newName.trim(),
        slug: newSlug.trim().toLowerCase(),
      };
      if (newOrgChatProv) body.preferred_chat_provider = newOrgChatProv;
      if (newOrgChatModel.trim()) body.preferred_chat_model = newOrgChatModel.trim();
      if (newOrgOllamaBase.trim()) body.ollama_base_url = newOrgOllamaBase.trim();
      const { data: newOrg } = await api.post<Org>("/organizations", body);
      setNewName("");
      setNewSlug("");
      setNewOrgChatProv("ollama");
      setNewOrgChatModel("");
      setNewOrgOllamaBase("");
      setShowCreateOrg(false);
      await loadOrgs();
      enterOrganization(newOrg.id);
      setPanel("dashboard");
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setCreating(false);
    }
  }

  const initials = user?.email?.slice(0, 2).toUpperCase() ?? "??";
  const hasOrgOwnerAccess =
    !!user?.is_platform_owner || (!!selectedOrgId && (user?.org_ids_as_owner ?? []).includes(selectedOrgId));
  const hasWorkspaceAdminAccess =
    !!user?.is_platform_owner || (!!selectedOrgId && (user?.org_ids_as_workspace_admin ?? []).includes(selectedOrgId));
  const workspaceScopeIds = hasOrgOwnerAccess ? undefined : scopedWorkspaces.map((ws) => ws.id);
  const canViewBilling = hasOrgOwnerAccess;
  const canViewAudit = hasOrgOwnerAccess || hasWorkspaceAdminAccess;
  const canViewSettings = hasOrgOwnerAccess || hasWorkspaceAdminAccess;

  // Member-only UX: auto-scope to first org and keep a chat-first landing.
  useEffect(() => {
    if (!isMemberOnlyUser) return;
    if (selectedOrgId || orgs.length === 0) return;
    enterOrganization(orgs[0].id);
  }, [isMemberOnlyUser, selectedOrgId, orgs, enterOrganization]);

  useEffect(() => {
    if (!isMemberOnlyUser) return;
    if (panel === "chats") return;
    setPanel("chats");
  }, [isMemberOnlyUser, panel, setPanel]);

  useEffect(() => {
    if (!isMemberOnlyUser) return;
    if (chatWorkspaceId || scopedWorkspaces.length === 0) return;
    setChatWorkspaceId(scopedWorkspaces[0].id);
  }, [isMemberOnlyUser, chatWorkspaceId, scopedWorkspaces, setChatWorkspaceId]);

  const C = brightMode ? ORG_SHELL_TOKENS_BRIGHT : ORG_SHELL_TOKENS_DARK;
  const { navGroups, onSelectNavItem } = useHomeNavState({
    userIsPlatformOwner: !!user?.is_platform_owner,
    memberChatOnly: isMemberOnlyUser,
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
  });
  const navGroupsWithState = useMemo(
    () =>
      navGroups.map((group) => ({
        ...group,
        items: group.items.map((item) => {
          const lock = getNavLockState(
            item.id,
            needsOrganizationContext,
            selectedOrgId,
            orgHasIndexedDocuments,
            isPlatformOwner,
          );
          return {
            ...item,
            disabled: lock.navDisabled,
            title: lock.title,
          };
        }),
      })),
    [navGroups, needsOrganizationContext, selectedOrgId, orgHasIndexedDocuments, isPlatformOwner],
  );
  const selectedOrgName = orgs.find((o) => o.id === selectedOrgId)?.name ?? null;
  const [memberAccountSettingsOpen, setMemberAccountSettingsOpen] = useState(false);

  return (
    <div
      className={brightMode ? "sk-org-shell sk-org-shell--bright" : "sk-org-shell"}
      style={{ display: "flex", height: "100vh", background: C.bg, fontFamily: C.sans, overflow: "hidden" }}
    >

      {!isMemberOnlyUser && (
        <HomeSidebar
          navGroups={navGroupsWithState}
          panel={panel}
          onSelectNavItem={onSelectNavItem}
          user={user}
          initials={initials}
          onLogout={() => void logout()}
        />
      )}

      {/* ── Main ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        <HomeTopBar
          panel={panel}
          chatWorkspaceId={chatWorkspaceId}
          setChatWorkspaceId={setChatWorkspaceId}
          scopedWorkspaces={scopedWorkspaces}
          ctxWorkspaceName={ctxWorkspaceName}
          brightMode={brightMode}
          setBrightMode={setBrightMode}
          initials={initials}
          isPlatformOwner={!!user?.is_platform_owner}
          navigationScope={navigationScope}
          selectedOrgId={selectedOrgId}
          selectedOrgName={selectedOrgName}
          ctxWorkspaceId={ctxWorkspaceId}
          exitToPlatform={exitToPlatform}
          setPanel={setPanel}
          memberChatOnly={isMemberOnlyUser}
          onLogout={() => void logout()}
          onOpenAccountSettings={() => setMemberAccountSettingsOpen(true)}
        />

        {/* Scrollable content — chat embed fills column (no outer scroll) */}
        <div style={{
          flex: 1, minHeight: 0, display: "flex", flexDirection: "column",
          overflowY: panel === "chats" && chatWorkspaceId ? "hidden" : "auto",
        }}>
          <HomePanelRouter
            panel={panel}
            user={user}
            orgs={orgs}
            allWorkspaces={allWorkspaces}
            workspaceCountByOrg={workspaceCountByOrg}
            loading={loading}
            enterOrganization={enterOrganization}
            setPanel={setPanel}
            selectedOrgId={selectedOrgId}
            navigate={navigate}
            showCreateOrg={showCreateOrg}
            setShowCreateOrg={setShowCreateOrg}
            err={err}
            createOrg={createOrg}
            newName={newName}
            setNewName={setNewName}
            newSlug={newSlug}
            setNewSlug={setNewSlug}
            newOrgChatProv={newOrgChatProv}
            setNewOrgChatProv={setNewOrgChatProv}
            newOrgChatModel={newOrgChatModel}
            setNewOrgChatModel={setNewOrgChatModel}
            newOrgOllamaBase={newOrgOllamaBase}
            setNewOrgOllamaBase={setNewOrgOllamaBase}
            isPlatformOwner={isPlatformOwner}
            navigationScope={navigationScope}
            exitToPlatform={exitToPlatform}
            orgScreen={orgScreen}
            setOrgScreen={setOrgScreen}
            workspaces={workspaces}
            loadingWs={loadingWs}
            setUploadWs={setUploadWs}
            api={api}
            AllWorkspacesPanel={AllWorkspacesPanel}
            OrgDetailView={OrgDetailView}
            creating={creating}
            setWorkspaces={setWorkspaces}
            setAllWorkspaces={setAllWorkspaces}
            setJumpToWsId={setJumpToWsId}
            setWorkspacesReloadNonce={setWorkspacesReloadNonce}
            loadOrgs={loadOrgs}
            setActiveWorkspaceContext={setActiveWorkspaceContext}
            scopedWorkspaces={scopedWorkspaces}
            ctxWorkspaceId={ctxWorkspaceId}
            jumpToWsId={jumpToWsId}
            chatWorkspaceId={chatWorkspaceId}
            setChatWorkspaceId={setChatWorkspaceId}
            brightMode={brightMode}
            onEmbeddedChatWorkspaceChange={onEmbeddedChatWorkspaceChange}
            ChatsPanel={ChatsPanel}
            jumpToChatWsId={jumpToChatWsId}
            ConnectorsPanel={ConnectorsPanel}
            workspaceInContext={workspaceInContext}
            BillingPanel={BillingPanel}
            AuditPanel={AuditPanel}
            workspaceScopeIds={workspaceScopeIds}
            canManageOrgSettings={hasOrgOwnerAccess}
            canManageWorkspaceSettings={hasWorkspaceAdminAccess}
            SettingsPanel={SettingsPanel}
            uploadWs={uploadWs}
            UploadModal={UploadModal}
            setOrgs={setOrgs}
            setErr={setErr}
            memberChatOnly={isMemberOnlyUser}
            memberAccountSettingsOpen={memberAccountSettingsOpen}
            setMemberAccountSettingsOpen={setMemberAccountSettingsOpen}
            onLaunchWorkspaceChat={(id) => {
              setChatWorkspaceId(id);
              setPanel("chats");
            }}
          />
        </div>
      </div>

      <style>{`
        @keyframes progress {
          0%   { margin-left: 0; width: 40%; }
          50%  { margin-left: 30%; width: 60%; }
          100% { margin-left: 100%; width: 10%; }
        }
        input[type="file"] { cursor: pointer; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: ${C.bg}; }
        ::-webkit-scrollbar-thumb { background: ${C.t3}; border-radius: 100px; }
        select option { background: ${C.bgE}; color: ${C.t1}; }
      `}</style>
    </div>
  );
}

export function HomePage() {
  const { orgs, setOrgs, loadingOrgs, orgsError, reloadOrgs } = useOrgsOutlet();
  const [formErr, setFormErr] = useState<string | null>(null);
  const err = formErr ?? orgsError;
  const [brightMode, setBrightMode] = useState(readOrgBrightModeFromStorage);
  useEffect(() => {
    persistOrgBrightMode(brightMode);
  }, [brightMode]);
  const C = brightMode ? ORG_SHELL_TOKENS_BRIGHT : ORG_SHELL_TOKENS_DARK;
  const orgShellUi = {
    brightMode,
    setBrightMode,
    toggleBrightMode: () => setBrightMode((v) => !v),
  };

  return (
    <OrgShellUiContext.Provider value={orgShellUi}>
      <OrgShellTokensContext.Provider value={C}>
        <HomePageContent
          orgs={orgs}
          setOrgs={setOrgs}
          loading={loadingOrgs}
          err={err}
          setErr={setFormErr}
          loadOrgs={reloadOrgs}
          brightMode={brightMode}
          setBrightMode={setBrightMode}
        />
      </OrgShellTokensContext.Provider>
    </OrgShellUiContext.Provider>
  );
}
