import {
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
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
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

// ─── Types ────────────────────────────────────────────────────────────────────
type Org = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description?: string | null;
  preferred_chat_provider?: string | null;
  preferred_chat_model?: string | null;
  openai_api_key_configured?: boolean;
  anthropic_api_key_configured?: boolean;
  openai_api_base_url?: string | null;
  anthropic_api_base_url?: string | null;
};

type OrgChatProvider = "" | "extractive" | "ollama" | "openai" | "anthropic";

function orgChatProviderFromApi(v: string | null | undefined): OrgChatProvider {
  if (v === "extractive" || v === "ollama" || v === "openai" || v === "anthropic") return v;
  return "";
}
type Workspace = { id: string; organization_id: string; name: string; description: string | null };
type Document = {
  id: string;
  filename: string;
  status: string;
  page_count: number | null;
  chunk_count?: number;
  created_at?: string;
};
type Panel =
  | "platform"
  | "dashboard"
  | "orgs"
  | "workspaces"
  | "chats"
  | "team"
  | "connectors"
  | "docs"
  | "analytics"
  | "billing";

/** Chats and Team stay disabled until at least one PDF is indexed (non–platform owners only). */
const KNOWLEDGE_GATED_PANELS: Panel[] = ["chats", "team"];

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
  children, variant = "primary", onClick, disabled, style,
}: {
  children: React.ReactNode;
  variant?: "primary" | "ghost" | "danger";
  onClick?: () => void;
  disabled?: boolean;
  style?: React.CSSProperties;
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
    <button type="button" style={{ ...base, ...styles[variant], ...style }} onClick={onClick} disabled={disabled}>
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

// ─── Nav item ─────────────────────────────────────────────────────────────────
function NavItem({
  icon, label, active, badge, badgeVariant = "accent", onClick, disabled, title: titleAttr,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  badge?: number;
  badgeVariant?: "accent" | "danger";
  onClick: () => void;
  disabled?: boolean;
  title?: string;
}) {
  const C = useOrgShellTokens();
  const badgeBg = badgeVariant === "danger" ? C.red : C.accent;
  return (
    <button
      type="button"
      title={titleAttr}
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      style={{
        display: "flex", alignItems: "center", gap: 8, padding: "6px 13px",
        fontSize: 12, fontWeight: 500, color: active ? C.t1 : C.t2,
        cursor: disabled ? "not-allowed" : "pointer", border: "none", background: active ? "rgba(37,99,235,0.12)" : "transparent",
        borderRight: active ? `2px solid ${C.accent}` : "2px solid transparent",
        width: "100%", textAlign: "left", fontFamily: C.sans, transition: "all .12s",
        opacity: disabled ? 0.45 : 1,
      }}
    >
      <span style={{ opacity: active ? 1 : 0.7, flexShrink: 0 }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      {badge != null && (
        <span style={{
          fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 100,
          background: badgeBg, color: "white",
        }}>
          {badge}
        </span>
      )}
    </button>
  );
}

// ─── Wide org dropdown (with search) ─────────────────────────────────────────
function WideOrgDropdown({
  orgs,
  selectedId,
  onSelect,
  allowEmpty,
  showBackToPlatform,
  onBackToPlatform,
}: {
  orgs: Org[];
  /** Pass "" to show “Select organization” until the user picks one (allowEmpty). */
  selectedId: string;
  onSelect: (id: string) => void;
  allowEmpty?: boolean;
  /** Platform owner: return to platform-wide scope (no active org). */
  showBackToPlatform?: boolean;
  onBackToPlatform?: () => void;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const selected = selectedId ? orgs.find((o) => o.id === selectedId) : allowEmpty ? undefined : orgs[0];

  const filtered = query.trim()
    ? orgs.filter((o) =>
        o.name.toLowerCase().includes(query.toLowerCase()) ||
        o.slug.toLowerCase().includes(query.toLowerCase()),
      )
    : orgs;

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => searchRef.current?.focus(), 50);
    else setQuery("");
  }, [open]);

  if (!orgs.length) return null;
  if (!selected && !allowEmpty) return null;

  return (
    <div ref={ref} style={{ position: "relative", width: "100%" }}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 12,
          padding: "13px 16px", background: C.bgCard,
          border: `1px solid ${open ? "rgba(37,99,235,0.5)" : C.bd2}`,
          borderRadius: open ? "12px 12px 0 0" : 12,
          cursor: "pointer", fontFamily: C.sans,
          boxShadow: open ? `0 0 0 3px rgba(37,99,235,0.1)` : "none",
          transition: "all .15s",
        }}
      >
        <div style={{
          width: 38, height: 38, borderRadius: 9, flexShrink: 0,
          background: selected
            ? "linear-gradient(135deg,rgba(37,99,235,0.35),rgba(139,92,246,0.35))"
            : "rgba(148,163,184,0.15)",
          border: `1px solid ${selected ? "rgba(37,99,235,0.35)" : C.bd}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 16, fontWeight: 700, color: selected ? "#93c5fd" : C.t3,
        }}>
          {selected ? selected.name.slice(0, 2).toUpperCase() : "?"}
        </div>
        <div style={{ flex: 1, textAlign: "left" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 2 }}>
            {selected ? selected.name : "Select organization…"}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {selected ? (
              <>
                <span style={{ fontSize: 10, color: C.t3, fontFamily: C.mono }}>/{selected.slug}</span>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 3,
                  padding: "1px 6px", borderRadius: 100, fontSize: 9, fontWeight: 700,
                  background: selected.status === "active" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
                  color: selected.status === "active" ? C.green : C.gold,
                  border: `1px solid ${selected.status === "active" ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)"}`,
                  fontFamily: C.sans,
                }}>
                  <span style={{ width: 4, height: 4, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />
                  {selected.status}
                </span>
              </>
            ) : (
              <span style={{ fontSize: 10, color: C.t3 }}>Choose an org to manage details</span>
            )}
          </div>
        </div>
        <svg viewBox="0 0 16 16" width="14" height="14" style={{
          fill: C.t3, flexShrink: 0,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform .15s",
        }}>
          <path d="M8 10.5L2.5 5h11L8 10.5z" />
        </svg>
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: "absolute", left: 0, right: 0, zIndex: 100,
          background: C.bgCard, border: `1px solid rgba(37,99,235,0.3)`,
          borderTop: "none", borderRadius: "0 0 12px 12px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        }}>
          {/* Search input */}
          <div style={{ padding: "10px 12px", borderBottom: `1px solid ${C.bd}` }}>
            <div style={{ position: "relative" }}>
              <svg viewBox="0 0 16 16" width="13" height="13" style={{
                position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)",
                fill: "none", stroke: C.t3, strokeWidth: 1.5, strokeLinecap: "round",
              }}>
                <circle cx="6.5" cy="6.5" r="4" />
                <path d="M10 10l3 3" />
              </svg>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search organizations…"
                style={{
                  width: "100%", padding: "7px 10px 7px 30px",
                  background: C.bgE, border: `1px solid ${C.bd}`, borderRadius: 7,
                  fontSize: 12, color: C.t1, fontFamily: C.sans, outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
          {showBackToPlatform && onBackToPlatform && (
            <div style={{ padding: "8px 12px", borderBottom: `1px solid ${C.bd}` }}>
              <button
                type="button"
                onClick={() => {
                  onBackToPlatform();
                  setOpen(false);
                  setQuery("");
                }}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 12px", borderRadius: 8, border: `1px solid rgba(37,99,235,0.25)`,
                  background: "rgba(37,99,235,0.08)", cursor: "pointer", fontFamily: C.sans,
                  textAlign: "left", transition: "background .12s",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(37,99,235,0.14)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(37,99,235,0.08)";
                }}
              >
                <span style={{ fontSize: 16, lineHeight: 1 }} aria-hidden>🌐</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>Platform-wide view</div>
                  <div style={{ fontSize: 10, color: C.t3, marginTop: 2 }}>Leave org context · overview all organizations</div>
                </div>
              </button>
            </div>
          )}
          {/* Results */}
          <div style={{ maxHeight: 240, overflowY: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: C.t3 }}>
                No organizations match "{query}"
              </div>
            ) : (
              filtered.map((org, i) => (
                <button
                  key={org.id}
                  type="button"
                  onClick={() => { onSelect(org.id); setOpen(false); setQuery(""); }}
                  style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 10,
                    padding: "11px 16px",
                    background: org.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent",
                    borderBottom: i < filtered.length - 1 ? `1px solid ${C.bd}` : "none",
                    border: "none", cursor: "pointer", fontFamily: C.sans, transition: "background .1s",
                  }}
                  onMouseEnter={(e) => { if (org.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = C.rowHover; }}
                  onMouseLeave={(e) => { if (org.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = org.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent"; }}
                >
                  <div style={{
                    width: 30, height: 30, borderRadius: 7, flexShrink: 0,
                    background: "rgba(37,99,235,0.18)", border: "1px solid rgba(37,99,235,0.25)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 700, color: "#93c5fd",
                  }}>
                    {org.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div style={{ flex: 1, textAlign: "left" }}>
                    <div style={{ fontSize: 12, fontWeight: org.id === selectedId ? 600 : 500, color: C.t1 }}>
                      {org.name}
                    </div>
                    <div style={{ fontSize: 10, color: C.t3, fontFamily: C.mono }}>/{org.slug}</div>
                  </div>
                  {org.id === selectedId && (
                    <svg viewBox="0 0 16 16" width="12" height="12" style={{ fill: "none", flexShrink: 0 }}>
                      <path d="M3 8l3.5 3.5 6.5-7" stroke={C.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Wide workspace dropdown (with search) ────────────────────────────────────
function WideWorkspaceDropdown({
  workspaces, orgs, selectedId, onSelect,
}: {
  workspaces: Workspace[];
  orgs: Org[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const selected = workspaces.find((w) => w.id === selectedId) ?? workspaces[0];

  const filtered = query.trim()
    ? workspaces.filter((w) => {
        const org = orgs.find((o) => o.id === w.organization_id);
        const q = query.toLowerCase();
        return (
          w.name.toLowerCase().includes(q) ||
          (w.description ?? "").toLowerCase().includes(q) ||
          (org?.name ?? "").toLowerCase().includes(q)
        );
      })
    : workspaces;

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => searchRef.current?.focus(), 50);
    else setQuery("");
  }, [open]);

  if (!selected) return null;

  const selOrg = orgs.find((o) => o.id === selected.organization_id);

  return (
    <div ref={ref} style={{ position: "relative", width: "100%" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 12,
          padding: "13px 16px", background: C.bgCard,
          border: `1px solid ${open ? "rgba(37,99,235,0.5)" : C.bd2}`,
          borderRadius: open ? "12px 12px 0 0" : 12,
          cursor: "pointer", fontFamily: C.sans,
          boxShadow: open ? `0 0 0 3px rgba(37,99,235,0.1)` : "none",
          transition: "all .15s",
        }}
      >
        <div style={{
          width: 38, height: 38, borderRadius: 9, flexShrink: 0,
          background: "linear-gradient(135deg,rgba(37,99,235,0.35),rgba(139,92,246,0.35))",
          border: "1px solid rgba(37,99,235,0.35)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, fontWeight: 700, color: "#93c5fd",
        }}>
          {selected.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
        </div>
        <div style={{ flex: 1, textAlign: "left" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 2 }}>
            {selected.name}
          </div>
          <div style={{ fontSize: 10, color: C.t3, fontFamily: C.mono }}>
            {selOrg?.name ?? "Organization"} · {selected.id.slice(0, 8)}…
          </div>
        </div>
        <svg viewBox="0 0 16 16" width="14" height="14" style={{
          fill: C.t3, flexShrink: 0,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform .15s",
        }}>
          <path d="M8 10.5L2.5 5h11L8 10.5z" />
        </svg>
      </button>

      {open && (
        <div style={{
          position: "absolute", left: 0, right: 0, zIndex: 100,
          background: C.bgCard, border: `1px solid rgba(37,99,235,0.3)`,
          borderTop: "none", borderRadius: "0 0 12px 12px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        }}>
          <div style={{ padding: "10px 12px", borderBottom: `1px solid ${C.bd}` }}>
            <div style={{ position: "relative" }}>
              <svg viewBox="0 0 16 16" width="13" height="13" style={{
                position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)",
                fill: "none", stroke: C.t3, strokeWidth: 1.5, strokeLinecap: "round",
              }}>
                <circle cx="6.5" cy="6.5" r="4" />
                <path d="M10 10l3 3" />
              </svg>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search workspaces…"
                style={{
                  width: "100%", padding: "7px 10px 7px 30px",
                  background: C.bgE, border: `1px solid ${C.bd}`, borderRadius: 7,
                  fontSize: 12, color: C.t1, fontFamily: C.sans, outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
          <div style={{ maxHeight: 260, overflowY: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: C.t3 }}>
                No workspaces match "{query}"
              </div>
            ) : (
              filtered.map((ws, i) => {
                const org = orgs.find((o) => o.id === ws.organization_id);
                return (
                  <button
                    key={ws.id}
                    type="button"
                    onClick={() => { onSelect(ws.id); setOpen(false); setQuery(""); }}
                    style={{
                      width: "100%", display: "flex", alignItems: "center", gap: 10,
                      padding: "11px 16px",
                      background: ws.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent",
                      borderBottom: i < filtered.length - 1 ? `1px solid ${C.bd}` : "none",
                      border: "none", cursor: "pointer", fontFamily: C.sans, transition: "background .1s",
                    }}
                    onMouseEnter={(e) => { if (ws.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = C.rowHover; }}
                    onMouseLeave={(e) => { if (ws.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = ws.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent"; }}
                  >
                    <div style={{
                      width: 30, height: 30, borderRadius: 7, flexShrink: 0,
                      background: "rgba(37,99,235,0.18)", border: "1px solid rgba(37,99,235,0.25)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 10, fontWeight: 700, color: "#93c5fd",
                    }}>
                      {ws.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, textAlign: "left", minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: ws.id === selectedId ? 600 : 500, color: C.t1 }}>
                        {ws.name}
                      </div>
                      <div style={{ fontSize: 10, color: C.t3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {org?.name ?? "—"}
                      </div>
                    </div>
                    {ws.id === selectedId && (
                      <svg viewBox="0 0 16 16" width="12" height="12" style={{ fill: "none", flexShrink: 0 }}>
                        <path d="M3 8l3.5 3.5 6.5-7" stroke={C.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Org detail — stats tile ───────────────────────────────────────────────────
function StatTile({
  icon, label, value, sub, color,
}: {
  icon: string; label: string; value: string | number; sub?: string; color?: string;
}) {
  const C = useOrgShellTokens();
  return (
    <div style={{
      background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 12,
      padding: "16px 18px", display: "flex", flexDirection: "column", gap: 6,
    }}>
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
    </div>
  );
}

type OrgScreen = "overview" | "settings";

function OrgSettingsCollapsible({
  title,
  subtitle,
  defaultOpen = true,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 14,
        overflow: "hidden",
        marginBottom: 10,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "14px 18px",
          background: open ? "rgba(37,99,235,0.06)" : "transparent",
          border: "none",
          cursor: "pointer",
          fontFamily: C.sans,
          textAlign: "left",
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.t1 }}>{title}</div>
          {subtitle ? <div style={{ fontSize: 11, color: C.t3, marginTop: 2 }}>{subtitle}</div> : null}
        </div>
        <span style={{ fontSize: 11, color: C.t2, flexShrink: 0 }}>{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div style={{ padding: "8px 18px 18px", borderTop: `1px solid ${C.bd}` }}>{children}</div>
      ) : null}
    </div>
  );
}

function OrganizationSettingsPanel({
  org,
  onSaved,
  showDangerZone,
  onOrgDeleted,
  isPlatformOwner,
}: {
  org: Org;
  onSaved: (org: Org) => void;
  showDangerZone?: boolean;
  onOrgDeleted?: () => void | Promise<void>;
  isPlatformOwner?: boolean;
}) {
  const C = useOrgShellTokens();
  const [name, setName] = useState(org.name);
  const [status, setStatus] = useState(org.status);
  const [description, setDescription] = useState(org.description ?? "");
  const [chatProv, setChatProv] = useState<OrgChatProvider>(orgChatProviderFromApi(org.preferred_chat_provider));
  const [chatModel, setChatModel] = useState(org.preferred_chat_model ?? "");
  const [openaiKeyDraft, setOpenaiKeyDraft] = useState("");
  const [anthropicKeyDraft, setAnthropicKeyDraft] = useState("");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState(org.openai_api_base_url ?? "");
  const [anthropicBaseUrl, setAnthropicBaseUrl] = useState(org.anthropic_api_base_url ?? "");
  const [clearOpenaiKey, setClearOpenaiKey] = useState(false);
  const [clearAnthropicKey, setClearAnthropicKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [delSlug, setDelSlug] = useState("");
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState<string | null>(null);

  useEffect(() => {
    setName(org.name);
    setStatus(org.status);
    setDescription(org.description ?? "");
    setChatProv(orgChatProviderFromApi(org.preferred_chat_provider));
    setChatModel(org.preferred_chat_model ?? "");
    setOpenaiBaseUrl(org.openai_api_base_url ?? "");
    setAnthropicBaseUrl(org.anthropic_api_base_url ?? "");
    setOpenaiKeyDraft("");
    setAnthropicKeyDraft("");
    setClearOpenaiKey(false);
    setClearAnthropicKey(false);
    setErr(null);
    setOk(null);
    setDelSlug("");
    setDelErr(null);
  }, [
    org.id,
    org.name,
    org.status,
    org.description,
    org.preferred_chat_provider,
    org.preferred_chat_model,
    org.openai_api_base_url,
    org.anthropic_api_base_url,
    org.openai_api_key_configured,
    org.anthropic_api_key_configured,
  ]);

  const selectStyle: CSSProperties = {
    width: "100%",
    background: C.bgE,
    border: `1px solid ${C.bd}`,
    borderRadius: 8,
    padding: "7px 10px",
    fontSize: 12,
    color: C.t1,
    fontFamily: C.sans,
    outline: "none",
    boxSizing: "border-box",
  };

  function resetForm() {
    setName(org.name);
    setStatus(org.status);
    setDescription(org.description ?? "");
    setChatProv(orgChatProviderFromApi(org.preferred_chat_provider));
    setChatModel(org.preferred_chat_model ?? "");
    setOpenaiBaseUrl(org.openai_api_base_url ?? "");
    setAnthropicBaseUrl(org.anthropic_api_base_url ?? "");
    setOpenaiKeyDraft("");
    setAnthropicKeyDraft("");
    setClearOpenaiKey(false);
    setClearAnthropicKey(false);
    setErr(null);
    setOk(null);
  }

  async function save() {
    setSaving(true);
    setErr(null);
    setOk(null);
    try {
      const patch: Record<string, unknown> = {
        name: name.trim(),
        status: status.trim().toLowerCase(),
        description: description.trim() || null,
        preferred_chat_provider: chatProv === "" ? null : chatProv,
        preferred_chat_model: chatModel.trim() || null,
      };
      if (isPlatformOwner) {
        if (clearOpenaiKey) patch.openai_api_key = null;
        else if (openaiKeyDraft.trim()) patch.openai_api_key = openaiKeyDraft.trim();
        if (clearAnthropicKey) patch.anthropic_api_key = null;
        else if (anthropicKeyDraft.trim()) patch.anthropic_api_key = anthropicKeyDraft.trim();
        patch.openai_api_base_url = openaiBaseUrl.trim() || null;
        patch.anthropic_api_base_url = anthropicBaseUrl.trim() || null;
      }

      const { data } = await api.patch<Org>(`/organizations/${org.id}`, patch);
      onSaved({ ...org, ...data });
      setOpenaiKeyDraft("");
      setAnthropicKeyDraft("");
      setClearOpenaiKey(false);
      setClearAnthropicKey(false);
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
        <div style={{ fontFamily: C.serif, fontSize: 20, color: C.t1, marginBottom: 4 }}>Organization settings</div>
        <div style={{ fontSize: 12, color: C.t2 }}>
          Profile, description, and optional chat model overrides for this organization.
        </div>
      </div>

      <OrgSettingsCollapsible title="Profile" subtitle="Name, status, and URL slug" defaultOpen>
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Name
            </div>
            <Input value={name} onChange={setName} placeholder="Organization name" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Status
            </div>
            <select value={status} onChange={(e) => setStatus(e.target.value)} style={selectStyle}>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Slug
            </div>
            <div style={{ fontSize: 12, color: C.t2, fontFamily: C.mono }}>/{org.slug}</div>
            <div style={{ fontSize: 10, color: C.t3, marginTop: 4 }}>Slug is read-only. Contact support to change it.</div>
          </div>
        </div>
      </OrgSettingsCollapsible>

      <OrgSettingsCollapsible
        title="About this organization"
        subtitle="Mission, context, and who this org serves"
        defaultOpen={false}
      >
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
            Description
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the organization's purpose, teams, and how you use the knowledge base."
            rows={5}
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
      </OrgSettingsCollapsible>

      <OrgSettingsCollapsible
        title="Chat & LLM"
        subtitle="Override platform defaults for grounded answers in this org"
        defaultOpen={false}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Answer provider
            </div>
            <select
              value={chatProv}
              onChange={(e) => setChatProv(e.target.value as OrgChatProvider)}
              style={selectStyle}
            >
              <option value="">Use platform default</option>
              <option value="extractive">Extractive (quotes only, no LLM)</option>
              <option value="ollama">Ollama (local LLM)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Chat model override
            </div>
            <Input
              value={chatModel}
              onChange={setChatModel}
              placeholder={
                chatProv === "openai"
                  ? "e.g. gpt-4o-mini"
                  : chatProv === "anthropic"
                    ? "e.g. claude-3-5-haiku-20241022"
                    : "e.g. llama3.2, qwen3:32b"
              }
              disabled={chatProv === "extractive"}
            />
            <div style={{ fontSize: 10, color: C.t3, marginTop: 6, lineHeight: 1.45 }}>
              When the effective provider is Ollama, OpenAI, or Anthropic, this overrides the platform default model for that
              provider if set. Leave empty to use the server default (
              <span style={{ fontFamily: C.mono }}>ANSWER_GENERATION_MODEL</span>,{" "}
              <span style={{ fontFamily: C.mono }}>OPENAI_DEFAULT_CHAT_MODEL</span>, or{" "}
              <span style={{ fontFamily: C.mono }}>ANTHROPIC_DEFAULT_CHAT_MODEL</span>).
            </div>
          </div>
          {!isPlatformOwner ? (
            <div
              style={{
                fontSize: 11,
                color: C.t2,
                lineHeight: 1.55,
                padding: "12px 14px",
                borderRadius: 10,
                background: "rgba(139,92,246,0.06)",
                border: "1px solid rgba(139,92,246,0.2)",
              }}
            >
              <strong style={{ color: C.t1 }}>Cloud LLM keys</strong> for OpenAI and Anthropic are configured by the platform
              owner (encrypted at rest). You can still select those providers here if keys or platform fallbacks are available.
            </div>
          ) : null}
        </div>
      </OrgSettingsCollapsible>

      {isPlatformOwner ? (
        <OrgSettingsCollapsible
          title="Cloud LLM credentials"
          subtitle="Platform owner only — per-organization API keys and optional API bases"
          defaultOpen={false}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>
            <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.55 }}>
              Store keys only when <span style={{ fontFamily: C.mono }}>ORG_LLM_FERNET_KEY</span> is set on the API. Keys are
              write-only; leave the password fields blank to keep the current stored key. Use "Remove stored key" to clear.
            </div>

            <div style={{ borderTop: `1px solid ${C.bd}`, paddingTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 8 }}>
                OpenAI
              </div>
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Key status:{" "}
                <strong style={{ color: C.t1 }}>
                  {clearOpenaiKey ? "will clear on save" : org.openai_api_key_configured ? "stored" : "none"}
                </strong>
              </div>
              <Input
                type="password"
                value={openaiKeyDraft}
                onChange={(v) => {
                  setOpenaiKeyDraft(v);
                  if (v.trim()) setClearOpenaiKey(false);
                }}
                placeholder="New API key (optional)"
              />
              <div style={{ marginTop: 8 }}>
                <Btn
                  variant="ghost"
                  disabled={saving || !org.openai_api_key_configured}
                  onClick={() => {
                    setClearOpenaiKey(true);
                    setOpenaiKeyDraft("");
                  }}
                >
                  Remove stored OpenAI key
                </Btn>
              </div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, margin: "12px 0 6px" }}>
                OpenAI API base URL
              </div>
              <Input
                value={openaiBaseUrl}
                onChange={setOpenaiBaseUrl}
                placeholder="https://api.openai.com/v1 (optional override)"
              />
            </div>

            <div style={{ borderTop: `1px solid ${C.bd}`, paddingTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 8 }}>
                Anthropic
              </div>
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Key status:{" "}
                <strong style={{ color: C.t1 }}>
                  {clearAnthropicKey ? "will clear on save" : org.anthropic_api_key_configured ? "stored" : "none"}
                </strong>
              </div>
              <Input
                type="password"
                value={anthropicKeyDraft}
                onChange={(v) => {
                  setAnthropicKeyDraft(v);
                  if (v.trim()) setClearAnthropicKey(false);
                }}
                placeholder="New API key (optional)"
              />
              <div style={{ marginTop: 8 }}>
                <Btn
                  variant="ghost"
                  disabled={saving || !org.anthropic_api_key_configured}
                  onClick={() => {
                    setClearAnthropicKey(true);
                    setAnthropicKeyDraft("");
                  }}
                >
                  Remove stored Anthropic key
                </Btn>
              </div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, margin: "12px 0 6px" }}>
                Anthropic API base URL
              </div>
              <Input
                value={anthropicBaseUrl}
                onChange={setAnthropicBaseUrl}
                placeholder="https://api.anthropic.com (optional override)"
              />
            </div>
          </div>
        </OrgSettingsCollapsible>
      ) : null}

      <div style={{ marginTop: 4 }}>
        {err ? <div style={{ fontSize: 11, color: C.red, marginBottom: 8 }}>✗ {err}</div> : null}
        {ok ? <div style={{ fontSize: 11, color: C.green, marginBottom: 8 }}>✓ {ok}</div> : null}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Btn variant="ghost" disabled={saving} onClick={resetForm}>
            Reset
          </Btn>
          <Btn variant="primary" disabled={saving || !name.trim()} onClick={save}>
            {saving ? "Saving…" : "Save changes"}
          </Btn>
        </div>
      </div>

      {showDangerZone && onOrgDeleted && (
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
          <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.55, marginBottom: 12 }}>
            Delete this organization and all workspaces, indexed documents, chat history, and connectors. This cannot be undone.
          </div>
          <div style={{ fontSize: 10, fontWeight: 600, color: C.t3, marginBottom: 6 }}>
            Type slug <span style={{ fontFamily: C.mono, color: C.t1 }}>{org.slug}</span> to confirm
          </div>
          <Input value={delSlug} onChange={setDelSlug} placeholder={org.slug} style={{ maxWidth: 320, marginBottom: 10 }} />
          {delErr && <div style={{ fontSize: 11, color: C.red, marginBottom: 8 }}>{delErr}</div>}
          <Btn
            variant="ghost"
            disabled={delBusy}
            style={{ borderColor: "rgba(239,68,68,0.45)", color: C.red }}
            onClick={async () => {
              setDelErr(null);
              if (delSlug.trim().toLowerCase() !== org.slug.toLowerCase()) {
                setDelErr("Slug must match exactly.");
                return;
              }
              setDelBusy(true);
              try {
                await api.delete(`/organizations/${org.id}`, { params: { confirm_slug: delSlug.trim() } });
                setDelSlug("");
                await onOrgDeleted();
              } catch (e) {
                setDelErr(apiErrorMessage(e));
              } finally {
                setDelBusy(false);
              }
            }}
          >
            {delBusy ? "Deleting…" : "Delete organization"}
          </Btn>
        </div>
      )}
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
  onOpenSettings,
}: {
  org: Org;
  workspaces: Workspace[];
  loadingWs: boolean;
  onUploadClick: (ws: Workspace) => void;
  onWorkspaceCreated: (wsId?: string) => void;
  onGoToWorkspace: (wsId?: string) => void;
  onOpenSettings: () => void;
}) {
  const C = useOrgShellTokens();

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
          <StatTile icon="⬡" label="Workspaces" value={loadingWs ? "…" : workspaces.length} sub="Active environments" color={C.accent} />
          <StatTile icon="👥" label="Members" value="—" sub="Seats provisioned" />
          <StatTile icon="📄" label="Documents" value="—" sub="Indexed & retrievable" color={C.purple} />
          <StatTile icon="🔌" label="Connectors" value={CONNECTORS.length} sub="Available integrations" color={C.green} />
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
          Manually upload PDFs; files are chunked and indexed for retrieval.
        </div>
        <span style={{ fontSize: 11, color: C.accent, fontWeight: 600 }}>
          {uploading ? "Indexing…" : "Upload File ↑"}
        </span>
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="application/pdf"
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
}: {
  orgs: Org[];
  allWorkspaces: Workspace[];
  loadingWs: boolean;
  initialWsId?: string;
  onLaunchChat: (workspaceId: string) => void;
  onWorkspaceUpdated: (ws: Workspace) => void;
  onSelectedWorkspaceChange?: (id: string | null, name: string | null) => void;
  onNavigateToTeam?: () => void;
  onNavigateToConnectors?: () => void;
  isPlatformOwner?: boolean;
  onWorkspaceDeleted?: () => void | Promise<void>;
}) {
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
        <button
          type="button"
          onClick={backToOverview}
          style={{
            display: "inline-flex", alignItems: "center", gap: 6, marginBottom: 16,
            background: "none", border: "none", cursor: "pointer",
            fontSize: 12, color: C.accent, fontFamily: C.sans,
          }}
        >
          ← Back to workspace
        </button>
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
            <WideWorkspaceDropdown
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
}: {
  allWorkspaces: Workspace[];
  initialWsId?: string;
  onOpenChat: (workspaceId: string) => void;
}) {
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
  ws, index, onUploadClick, onGoToWorkspace,
}: {
  ws: Workspace;
  index: number;
  onUploadClick: (ws: Workspace) => void;
  onGoToWorkspace: (wsId: string) => void;
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
          onClick={() => navigate(`/dashboard/${ws.id}`)}
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

// ─── Documents panel ──────────────────────────────────────────────────────────
function DocumentsPanel({ orgs, scopeOrganizationId }: { orgs: Org[]; scopeOrganizationId?: string | null }) {
  const C = useOrgShellTokens();
  const [allWorkspaces, setAllWorkspaces] = useState<(Workspace & { orgName: string })[]>([]);
  const [selectedWsId, setSelectedWsId] = useState<string>("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [uploadOk, setUploadOk] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Collect workspaces (all orgs, or single org when platform owner has scoped context)
  useEffect(() => {
    if (!orgs.length) return;
    const orgList = scopeOrganizationId
      ? orgs.filter((o) => o.id === scopeOrganizationId)
      : orgs;
    if (!orgList.length) {
      setAllWorkspaces([]);
      setSelectedWsId("");
      return;
    }
    let cancelled = false;
    void (async () => {
      const collected: (Workspace & { orgName: string })[] = [];
      for (const o of orgList) {
        try {
          const { data } = await api.get<Workspace[]>(`/workspaces/org/${o.id}`);
          data.forEach((ws) => collected.push({ ...ws, orgName: o.name }));
        } catch {
          /* ignore */
        }
      }
      if (cancelled) return;
      setAllWorkspaces(collected);
      setSelectedWsId((prev) => {
        if (collected.some((w) => w.id === prev)) return prev;
        return collected[0]?.id ?? "";
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [orgs, scopeOrganizationId]);

  // Fetch documents when workspace selected
  useEffect(() => {
    if (!selectedWsId) return;
    setLoadingDocs(true);
    setDocuments([]);
    api.get<Document[]>(`/documents/workspaces/${selectedWsId}`)
      .then(({ data }) => setDocuments(data))
      .catch(() => setDocuments([]))
      .finally(() => setLoadingDocs(false));
  }, [selectedWsId]);

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedWsId) return;
    setUploading(true);
    setUploadErr(null);
    setUploadOk(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const { data } = await api.post<{ filename: string; chunk_count: number }>(
        `/documents/workspaces/${selectedWsId}/upload`, body,
      );
      setUploadOk(`"${data.filename}" indexed — ${data.chunk_count} chunks created.`);
      // Refresh doc list
      const { data: docs } = await api.get<Document[]>(`/documents/workspaces/${selectedWsId}`);
      setDocuments(docs);
    } catch (ex) {
      setUploadErr(apiErrorMessage(ex));
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  if (scopeOrganizationId && !orgs.some((o) => o.id === scopeOrganizationId)) {
    return (
      <div style={{ padding: "18px 22px" }}>
        <div style={{ fontSize: 13, color: C.t2 }}>Select an organization from the context bar to manage documents for that org.</div>
      </div>
    );
  }

  return (
    <div style={{ padding: "18px 22px" }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>
          Document Library
        </div>
        <div style={{ fontSize: 12, color: C.t2 }}>
          Upload PDFs to any workspace to index them for grounded AI retrieval.
        </div>
      </div>

      {/* Workspace selector */}
      <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, color: C.t3, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Workspace
        </span>
        <select
          value={selectedWsId}
          onChange={(e) => setSelectedWsId(e.target.value)}
          style={{
            background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 7,
            padding: "6px 10px", fontSize: 12, color: C.t1, fontFamily: C.sans, outline: "none",
          }}
        >
          {allWorkspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>{ws.orgName} / {ws.name}</option>
          ))}
        </select>
      </div>

      {/* Upload zone */}
      <div style={{
        background: C.bgCard, border: `2px dashed ${C.bd2}`, borderRadius: 12,
        padding: "28px 24px", textAlign: "center", marginBottom: 20,
        cursor: "pointer", transition: "border-color .2s",
      }}
        onClick={() => fileRef.current?.click()}
      >
        <div style={{ fontSize: 30, marginBottom: 8 }}>📄</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 4 }}>
          {uploading ? "Uploading & indexing…" : "Click to upload a PDF"}
        </div>
        <div style={{ fontSize: 11, color: C.t3 }}>
          PDFs are parsed, chunked, embedded and indexed automatically
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          style={{ display: "none" }}
          onChange={handleUpload}
          disabled={uploading || !selectedWsId}
        />
        {uploading && (
          <div style={{ marginTop: 12 }}>
            <div style={{
              height: 3, background: C.bgE, borderRadius: 100, overflow: "hidden", maxWidth: 280, margin: "0 auto",
            }}>
              <div style={{
                height: "100%", background: C.accent, borderRadius: 100,
                width: "60%", animation: "progress 1.5s ease-in-out infinite",
              }} />
            </div>
          </div>
        )}
      </div>

      {uploadErr && (
        <div style={{
          padding: "10px 14px", background: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8,
          fontSize: 12, color: "#f87171", marginBottom: 14,
        }}>
          ✗ {uploadErr}
        </div>
      )}
      {uploadOk && (
        <div style={{
          padding: "10px 14px", background: "rgba(16,185,129,0.08)",
          border: "1px solid rgba(16,185,129,0.25)", borderRadius: 8,
          fontSize: 12, color: "#34d399", marginBottom: 14,
        }}>
          ✓ {uploadOk}
        </div>
      )}

      {/* Document table */}
      <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 12, overflow: "hidden" }}>
        <div style={{
          padding: "11px 15px", borderBottom: `1px solid ${C.bd}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>
            Indexed documents {documents.length > 0 && `· ${documents.length}`}
          </span>
          {loadingDocs && <span style={{ fontSize: 10, color: C.t3 }}>Loading…</span>}
        </div>
        {documents.length === 0 && !loadingDocs ? (
          <div style={{ padding: "24px 16px", textAlign: "center", fontSize: 12, color: C.t3 }}>
            No documents indexed yet. Upload a PDF above to get started.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Document", "Status", "Pages", "Chunks", "Indexed", ""].map((h) => (
                  <th key={h} style={{
                    textAlign: "left", fontSize: 9, fontWeight: 700,
                    letterSpacing: "0.1em", textTransform: "uppercase",
                    color: C.t3, padding: "7px 12px",
                    background: "rgba(255,255,255,0.02)", borderBottom: `1px solid ${C.bd}`,
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id} style={{ borderBottom: `1px solid rgba(255,255,255,0.04)` }}>
                  <td style={{ padding: "9px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{
                        width: 26, height: 26, borderRadius: 5, background: "rgba(37,99,235,0.12)",
                        border: `1px solid rgba(37,99,235,0.2)`, display: "flex",
                        alignItems: "center", justifyContent: "center", fontSize: 12, flexShrink: 0,
                      }}>
                        📄
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 500, color: C.t1 }}>{doc.filename}</span>
                    </div>
                  </td>
                  <td style={{ padding: "9px 12px" }}>
                    {doc.status === "indexed"
                      ? <Badge label="● Indexed" color={C.green} bg="rgba(16,185,129,0.12)" border="rgba(16,185,129,0.25)" />
                      : doc.status === "pending"
                        ? <Badge label="⟳ Processing" color={C.gold} bg="rgba(245,158,11,0.12)" border="rgba(245,158,11,0.25)" />
                        : <Badge label={doc.status} color={C.t2} bg="rgba(148,163,184,0.08)" border={C.bd} />}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: C.t2, fontFamily: C.mono }}>
                    {doc.page_count ?? "—"}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: C.t2, fontFamily: C.mono }}>
                    {doc.chunk_count ?? "—"}
                  </td>
                  <td style={{ padding: "9px 12px", fontSize: 11, color: C.t3, fontFamily: C.mono }}>
                    {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td style={{ padding: "9px 12px", textAlign: "right" }}>
                    <button
                      type="button"
                      disabled={removingId === doc.id}
                      onClick={async () => {
                        if (!window.confirm(`Remove “${doc.filename}” from the index?`)) return;
                        setRemovingId(doc.id);
                        try {
                          await api.delete(`/documents/${doc.id}`);
                          const { data: docs } = await api.get<Document[]>(`/documents/workspaces/${selectedWsId}`);
                          setDocuments(docs);
                        } catch (ex) {
                          setUploadErr(apiErrorMessage(ex));
                        } finally {
                          setRemovingId(null);
                        }
                      }}
                      style={{
                        fontSize: 10,
                        fontWeight: 600,
                        color: C.red,
                        background: "none",
                        border: "none",
                        cursor: removingId === doc.id ? "wait" : "pointer",
                        fontFamily: C.sans,
                      }}
                    >
                      {removingId === doc.id ? "…" : "Remove"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ─── Billing panel (same details as /admin/billing) ────────────────────────────
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
  connectors_used: number;
  seats_used: number;
  billing_grace_until: string | null;
};

function BillingPanel() {
  const C = useOrgShellTokens();
  const [orgs, setOrgs] = useState<BillingOrg[]>([]);
  const [orgId, setOrgId] = useState("");
  const [plan, setPlan] = useState<BillingPlan | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<BillingOrg[]>("/organizations/me")
      .then((r) => {
        setOrgs(r.data);
        if (!orgId && r.data[0]) setOrgId(r.data[0].id);
      })
      .catch((e) => setErr(apiErrorMessage(e)));
  }, [orgId]);

  useEffect(() => {
    if (!orgId) return;
    setErr(null);
    void api
      .get<BillingPlan>(`/organizations/${orgId}/billing/plan`)
      .then((r) => setPlan(r.data))
      .catch((e) => setErr(apiErrorMessage(e)));
  }, [orgId]);

  const seatPct = plan ? Math.min(100, Math.round((plan.seats_used / Math.max(plan.seats_max, 1)) * 100)) : 0;
  const connPct = plan ? Math.min(100, Math.round((plan.connectors_used / Math.max(plan.connectors_max, 1)) * 100)) : 0;
  const queryPct = plan ? Math.min(100, Math.round((Math.max(plan.queries_per_day, 1) / Math.max(plan.queries_per_month, 1)) * 100)) : 0;

  const invoiceRows = [
    { date: "Nov 1, 2025", amount: "$299.00", status: "Paid" },
    { date: "Oct 1, 2025", amount: "$299.00", status: "Paid" },
    { date: "Sep 1, 2025", amount: "$149.00", status: "Paid" },
  ];

  return (
    <div style={{ padding: "22px 26px", overflowY: "auto", height: "100%" }}>
      <div style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 16,
        padding: "18px 20px",
        marginBottom: 14,
      }}>
        <div style={{ fontFamily: C.serif, fontSize: 22, color: C.t1, marginBottom: 4 }}>Usage & Billing</div>
        <div style={{ fontSize: 12, color: C.t2 }}>
          {plan ? `${plan.plan[0].toUpperCase()}${plan.plan.slice(1)} plan` : "Plan"} ·{" "}
          {plan?.billing_grace_until ? `Grace until ${new Date(plan.billing_grace_until).toLocaleDateString()}` : "Renews soon"}
        </div>
      </div>

      {err && (
        <div style={{ padding: "10px 14px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8, fontSize: 12, color: C.red, marginBottom: 14 }}>
          {err}
        </div>
      )}

      <div style={{ maxWidth: 420, marginBottom: 12 }}>
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

      {plan && (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", gap: 12, alignItems: "start" }}>
          <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "16px 16px 14px" }}>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: C.t1, marginBottom: 4 }}>
                  {plan.plan[0].toUpperCase() + plan.plan.slice(1)} Plan
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color: C.t1, fontFamily: C.mono }}>
                  ${Math.max(99, Math.round(plan.queries_per_month / 20))}
                  <span style={{ fontSize: 12, color: C.t3, fontWeight: 600, marginLeft: 6, fontFamily: C.sans }}>/month</span>
                </div>
              </div>
              <Badge label={plan.subscription_status || "Active"} color={C.accent} bg="rgba(37,99,235,0.12)" border="rgba(37,99,235,0.25)" />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12, fontSize: 12, color: C.t2 }}>
              <div>{plan.seats_max} users included</div>
              <div>{plan.connectors_max} connectors included</div>
              <div>{plan.queries_per_month.toLocaleString()} queries/month</div>
              <div>Admin analytics</div>
              <div>Email + chat support</div>
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Btn variant="ghost" style={{ fontSize: 11 }}>Change plan</Btn>
              <Btn variant="ghost" style={{ fontSize: 11 }}>Download invoice</Btn>
            </div>

            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.t1, marginBottom: 10 }}>Current period usage</div>

              {[
                { label: "Queries", left: `${plan.queries_per_day.toLocaleString()} / ${plan.queries_per_month.toLocaleString()}`, pct: queryPct, color: C.green },
                { label: "Team members", left: `${plan.seats_used} / ${plan.seats_max}`, pct: seatPct, color: C.green },
                { label: "Active connectors", left: `${plan.connectors_used} / ${plan.connectors_max}`, pct: connPct, color: C.gold },
              ].map((row) => (
                <div key={row.label} style={{ marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: C.t2, marginBottom: 6 }}>
                    <span>{row.label}</span>
                    <span style={{ fontFamily: C.mono }}>{row.left}</span>
                  </div>
                  <div style={{ height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 999, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${row.pct}%`, background: row.color, borderRadius: 999, opacity: 0.85 }} />
                  </div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.t1, marginBottom: 10 }}>Invoice history</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {invoiceRows.map((inv) => (
                  <div key={inv.date} style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 10, alignItems: "center", padding: "8px 10px", borderRadius: 10, border: `1px solid ${C.bd}`, background: "rgba(255,255,255,0.02)" }}>
                    <span style={{ fontSize: 12, color: C.t2 }}>{inv.date}</span>
                    <Badge label={inv.status} color={C.green} bg="rgba(16,185,129,0.12)" border="rgba(16,185,129,0.25)" />
                    <span style={{ fontSize: 12, color: C.t1, fontFamily: C.mono }}>{inv.amount}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "16px 16px 14px" }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: C.t1, marginBottom: 6 }}>Upgrade to Scale</div>
              <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.55, marginBottom: 12 }}>
                You are using {connPct}% of connectors. Scale includes more connectors, SSO, audit logs, and priority support.
              </div>
              <div style={{ fontSize: 20, fontWeight: 800, color: C.t1, fontFamily: C.mono, marginBottom: 12 }}>
                ${Math.max(199, Math.round(Math.max(99, plan.queries_per_month / 20) * 1.8))}
                <span style={{ fontSize: 12, color: C.t3, fontWeight: 600, marginLeft: 6, fontFamily: C.sans }}>/month</span>
              </div>
              <Btn variant="primary" style={{ width: "100%", justifyContent: "center" }}>
                Upgrade to Scale →
              </Btn>
            </div>

            <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "16px 16px 14px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.t1, marginBottom: 10 }}>Payment method</div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "10px 10px", borderRadius: 12, border: `1px solid ${C.bd}`, background: "rgba(255,255,255,0.02)" }}>
                <div style={{ fontSize: 10, fontWeight: 800, color: C.t1, border: `1px solid ${C.bd}`, background: C.bgE, borderRadius: 10, padding: "6px 8px" }}>
                  VISA
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.t1 }}>Visa ending in 4242</div>
                  <div style={{ fontSize: 11, color: C.t2 }}>Expires 08/2027</div>
                </div>
                <Btn variant="ghost" style={{ marginLeft: "auto", fontSize: 11, padding: "6px 10px" }}>
                  Update
                </Btn>
              </div>
            </div>

            <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "16px 16px 14px" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.t1, marginBottom: 6 }}>Need help?</div>
              <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.55, marginBottom: 10 }}>
                Questions about your plan or custom enterprise pricing?
              </div>
              <Btn variant="ghost" style={{ width: "100%", justifyContent: "center", fontSize: 11 }}>
                Talk to sales →
              </Btn>
            </div>
          </div>
        </div>
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
          PDFs are parsed, chunked, and embedded for RAG retrieval.
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
            {uploading ? "Indexing…" : "Click to select a PDF"}
          </div>
          <div style={{ fontSize: 10, color: C.t3 }}>Supported: PDF · Max 50 MB</div>
          <input ref={fileRef} type="file" accept="application/pdf" style={{ display: "none" }} onChange={handleUpload} disabled={uploading} />
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
  const navigate = useNavigate();
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

  const [panel, setPanel] = useState<Panel>(() => (user?.is_platform_owner ? "platform" : "dashboard"));

  // Create org form
  const [showCreateOrg, setShowCreateOrg] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [creating, setCreating] = useState(false);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [allWorkspaces, setAllWorkspaces] = useState<Workspace[]>([]);
  const [workspaceCountByOrg, setWorkspaceCountByOrg] = useState<Record<string, number>>({});
  const [loadingWs, setLoadingWs] = useState(false);
  /** Bumps workspace list refetch after destructive deletes (org/workspace). */
  const [workspacesReloadNonce, setWorkspacesReloadNonce] = useState(0);
  // Workspace to auto-select when switching to workspaces panel
  const [jumpToWsId, setJumpToWsId] = useState<string | undefined>(undefined);
  /** Organizations panel: overview vs settings (mirrors workspace panel). */
  const [orgScreen, setOrgScreen] = useState<OrgScreen>("overview");
  // Workspace to highlight in Chats list (when not in embedded chat)
  const [jumpToChatWsId, setJumpToChatWsId] = useState<string | undefined>(undefined);

  useEffect(() => {
    setOrgScreen("overview");
  }, [selectedOrgId]);
  /** Open chat UI inside main area while keeping platform sidebar */
  const [chatWorkspaceId, setChatWorkspaceId] = useState<string | null>(null);
  /** Stable for Dashboard embedded mode — avoids refetch/loading flash on every HomePage re-render. */
  const onEmbeddedChatWorkspaceChange = useCallback((id: string) => {
    setChatWorkspaceId(id);
  }, []);

  // Upload modal
  const [uploadWs, setUploadWs] = useState<Workspace | null>(null);
  void useRef; // silence unused-import (used in UploadModal + DocumentsPanel)

  useEffect(() => {
    if (panel !== "chats") {
      setJumpToChatWsId(undefined);
      setChatWorkspaceId(null);
    }
  }, [panel]);

  useEffect(() => {
    if (!chatWorkspaceId) return;
    const w =
      allWorkspaces.find((x) => x.id === chatWorkspaceId) ??
      workspaces.find((x) => x.id === chatWorkspaceId);
    setActiveWorkspaceContext(chatWorkspaceId, w?.name ?? null);
  }, [chatWorkspaceId, allWorkspaces, workspaces, setActiveWorkspaceContext]);

  /** Clear workspace scope only when leaving org-scoped "modes" — keep context for Team, Analytics, Connectors, Docs, etc. */
  useEffect(() => {
    if (panel === "platform" || panel === "orgs" || panel === "billing") {
      setActiveWorkspaceContext(null, null);
    }
  }, [panel, setActiveWorkspaceContext]);

  /** Drop workspace context if it no longer belongs to the active organization. */
  useEffect(() => {
    if (!ctxWorkspaceId || !selectedOrgId) return;
    if (loadingWs) return;
    const ws =
      allWorkspaces.find((w) => w.id === ctxWorkspaceId) ??
      workspaces.find((w) => w.id === ctxWorkspaceId);
    if (!ws || ws.organization_id !== selectedOrgId) {
      setActiveWorkspaceContext(null, null);
    }
  }, [selectedOrgId, ctxWorkspaceId, allWorkspaces, workspaces, loadingWs, setActiveWorkspaceContext]);

  // Fetch workspace counts (all orgs) for platform dashboard + chat list
  useEffect(() => {
    if (!orgs.length) {
      setAllWorkspaces([]);
      setWorkspaceCountByOrg({});
      return;
    }
    let cancelled = false;
    void Promise.allSettled(
      orgs.map((o) =>
        api.get<Workspace[]>(`/workspaces/org/${o.id}`).then((r) => ({ id: o.id, list: r.data })),
      ),
    ).then((results) => {
      if (cancelled) return;
      const fulfilled = results.filter(
        (r): r is PromiseFulfilledResult<{ id: string; list: Workspace[] }> => r.status === "fulfilled",
      );
      const merged: Workspace[] = [];
      for (const { value } of fulfilled) {
        merged.push(...value.list);
      }
      // Keep prior counts for orgs whose request failed so one bad / slow org does not zero others (e.g. Sterling).
      setWorkspaceCountByOrg((prev) => {
        const next: Record<string, number> = {};
        for (const o of orgs) {
          next[o.id] = prev[o.id] ?? 0;
        }
        for (const { value } of fulfilled) {
          next[value.id] = value.list.length;
        }
        return next;
      });
      setAllWorkspaces(merged);
    });
    return () => {
      cancelled = true;
    };
  }, [orgs, workspacesReloadNonce]);

  // Load workspaces for active organization (org-scoped modules)
  useEffect(() => {
    if (!selectedOrgId) {
      setWorkspaces([]);
      setLoadingWs(false);
      return;
    }
    let stale = false;
    setLoadingWs(true);
    setWorkspaces([]);
    api
      .get<Workspace[]>(`/workspaces/org/${selectedOrgId}`)
      .then(({ data }) => {
        if (stale) return;
        setWorkspaces(data);
      })
      .catch(() => {
        if (stale) return;
        setWorkspaces([]);
      })
      .finally(() => {
        if (stale) return;
        setLoadingWs(false);
      });
    return () => {
      stale = true;
    };
  }, [selectedOrgId]);

  // Align platform workspace counts with the authoritative per-org list once it finishes loading.
  useEffect(() => {
    if (!selectedOrgId || loadingWs) return;
    setWorkspaceCountByOrg((prev) => ({ ...prev, [selectedOrgId]: workspaces.length }));
  }, [selectedOrgId, workspaces, loadingWs]);

  /**
   * Prefer the dedicated `/workspaces/org/:id` list: it is authoritative for the open org.
   * Filtering dedicated rows by `organization_id` hid everything when a stale response from another org
   * overwrote state (last write wins) — those rows no longer matched `selectedOrgId`.
   */
  const scopedWorkspaces = useMemo(() => {
    if (!selectedOrgId) return [] as Workspace[];
    const fromBatch = allWorkspaces.filter((w) => w.organization_id === selectedOrgId);
    if (workspaces.length > 0) return workspaces;
    return fromBatch;
  }, [allWorkspaces, selectedOrgId, workspaces]);

  /** Resolved workspace for nav panels (Team / Analytics / Connectors) when a workspace is selected in context. */
  const workspaceInContext = useMemo((): Workspace | null => {
    if (!ctxWorkspaceId) return null;
    const w =
      allWorkspaces.find((x) => x.id === ctxWorkspaceId) ?? workspaces.find((x) => x.id === ctxWorkspaceId);
    if (w) return w;
    if (selectedOrgId && ctxWorkspaceName) {
      return {
        id: ctxWorkspaceId,
        organization_id: selectedOrgId,
        name: ctxWorkspaceName,
        description: null,
      };
    }
    return null;
  }, [ctxWorkspaceId, ctxWorkspaceName, allWorkspaces, workspaces, selectedOrgId]);

  /** True when any workspace in the active org has at least one indexed document; null while loading. */
  const [orgHasIndexedDocuments, setOrgHasIndexedDocuments] = useState<boolean | null>(null);

  useEffect(() => {
    if (!selectedOrgId || scopedWorkspaces.length === 0) {
      setOrgHasIndexedDocuments(null);
      return;
    }
    let cancelled = false;
    void Promise.allSettled(
      scopedWorkspaces.map((ws) =>
        api.get<Document[]>(`/documents/workspaces/${ws.id}`).then((r) => r.data.length),
      ),
    ).then((results) => {
      if (cancelled) return;
      const ok = results.filter(
        (r): r is PromiseFulfilledResult<number> => r.status === "fulfilled",
      );
      if (ok.length === 0) {
        setOrgHasIndexedDocuments(null);
        return;
      }
      setOrgHasIndexedDocuments(ok.some((r) => r.value > 0));
    });
    return () => {
      cancelled = true;
    };
  }, [selectedOrgId, scopedWorkspaces]);

  useEffect(() => {
    if (isPlatformOwner) return;
    if (orgHasIndexedDocuments !== false) return;
    if (panel !== "chats" && panel !== "team") return;
    if (!selectedOrgId) return;
    setPanel("docs");
  }, [orgHasIndexedDocuments, panel, selectedOrgId, isPlatformOwner]);

  async function createOrg(e: FormEvent) {
    e.preventDefault();
    if (!user?.is_platform_owner) return;
    setCreating(true);
    setErr(null);
    try {
      const { data: newOrg } = await api.post<Org>("/organizations", {
        name: newName.trim(),
        slug: newSlug.trim().toLowerCase(),
      });
      setNewName("");
      setNewSlug("");
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

  const C = brightMode ? ORG_SHELL_TOKENS_BRIGHT : ORG_SHELL_TOKENS_DARK;

  /** Panels that require an active org when the user is in platform-wide scope (not "dashboard" — it has its own empty state + link to Organizations). */
  const ORG_SCOPED_PANELS: Panel[] = [
    "workspaces",
    "chats",
    "team",
    "analytics",
    "docs",
    "connectors",
    "billing",
  ];

  const navGroups = user?.is_platform_owner
    ? [
        {
          label: "Platform",
          items: [{ id: "platform" as Panel, icon: "\u{1F310}", label: "Overview" }],
        },
        {
          label: "Core app",
          items: [
            { id: "dashboard" as Panel, icon: dashNavIcon, label: "Dashboard" },
            { id: "orgs" as Panel, icon: "\u{1F3E2}", label: "Organizations" },
            { id: "workspaces" as Panel, icon: "\u{2B21}", label: "Workspaces" },
            { id: "chats" as Panel, icon: "\u{1F4AC}", label: "Chats" },
          ],
        },
        {
          label: "Knowledge",
          items: [
            { id: "team" as Panel, icon: "\u{1F465}", label: "Team", badge: 12 },
            { id: "analytics" as Panel, icon: "\u{1F4CA}", label: "Analytics" },
            { id: "docs" as Panel, icon: "\u{1F4C4}", label: "Documents" },
            {
              id: "connectors" as Panel,
              icon: "\u{1F50C}",
              label: "Connectors",
              badge: 1,
              badgeVariant: "danger" as const,
            },
          ],
        },
        {
          label: "Enterprise",
          items: [
            { id: "billing" as Panel, icon: "\u{1F4B3}", label: "Billing" },
            { id: null, icon: "\u{1F6E1}", label: "Audit Log", href: "/admin/audit" },
            { id: null, icon: "\u{2699}\u{FE0F}", label: "Settings", href: "/admin/settings" },
          ],
        },
      ]
    : [
        {
          label: "Core app",
          items: [
            { id: "dashboard" as Panel, icon: dashNavIcon, label: "Dashboard" },
            { id: "orgs" as Panel, icon: "\u{1F3E2}", label: "Organizations" },
            { id: "workspaces" as Panel, icon: "\u{2B21}", label: "Workspaces" },
            { id: "chats" as Panel, icon: "\u{1F4AC}", label: "Chats" },
          ],
        },
        {
          label: "Knowledge",
          items: [
            { id: "team" as Panel, icon: "\u{1F465}", label: "Team", badge: 12 },
            { id: "analytics" as Panel, icon: "\u{1F4CA}", label: "Analytics" },
            { id: "docs" as Panel, icon: "\u{1F4C4}", label: "Documents" },
            {
              id: "connectors" as Panel,
              icon: "\u{1F50C}",
              label: "Connectors",
              badge: 1,
              badgeVariant: "danger" as const,
            },
          ],
        },
        {
          label: "Enterprise",
          items: [
            { id: "billing" as Panel, icon: "\u{1F4B3}", label: "Billing" },
            { id: null, icon: "\u{1F6E1}", label: "Audit Log", href: "/admin/audit" },
            { id: null, icon: "\u{2699}\u{FE0F}", label: "Settings", href: "/admin/settings" },
          ],
        },
      ];

  return (
    <div
      className={brightMode ? "sk-org-shell sk-org-shell--bright" : "sk-org-shell"}
      style={{ display: "flex", height: "100vh", background: C.bg, fontFamily: C.sans, overflow: "hidden" }}
    >

      {/* ── Sidebar ── */}
      <aside style={{
        width: 210, flexShrink: 0, background: C.bg,
        borderRight: `1px solid ${C.hairline}`,
        display: "flex", flexDirection: "column", overflowY: "auto",
      }}>
        {/* Logo */}
        <div style={{
          padding: "14px 14px 14px", borderBottom: `1px solid ${C.hairline}`,
          display: "flex", alignItems: "center", gap: 8,
          fontSize: 13, fontWeight: 600, color: C.t1,
        }}>
          <div style={{
            width: 24, height: 24, background: C.accent, borderRadius: 5,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 0 12px ${C.accentG}`,
          }}>
            <svg viewBox="0 0 18 18" style={{ width: 13, height: 13, fill: "white" }}>
              <path d="M9 1L2 5v8l7 4 7-4V5L9 1zm0 2.2l4.8 2.8L9 8.8 4.2 6 9 3.2zm-5.8 3.8l5 2.9v5.2L3.2 12V7zm6.8 8.1V9.9l5-2.9V12l-5 2.9z" />
            </svg>
          </div>
          Sovereign Knowledge
        </div>

        {/* Nav groups */}
        {navGroups.map((group) => (
          <div key={group.label}>
            <div style={{
              fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase",
              color: C.t3, padding: "10px 14px 4px",
            }}>
              {group.label}
            </div>
            {group.items.map((item) => {
              const pid = "id" in item && item.id ? item.id : null;
              const orgLocked =
                Boolean(pid && ORG_SCOPED_PANELS.includes(pid) && needsOrganizationContext);
              const knowledgeLocked =
                Boolean(
                  pid &&
                    KNOWLEDGE_GATED_PANELS.includes(pid) &&
                    selectedOrgId &&
                    orgHasIndexedDocuments !== true &&
                    !isPlatformOwner,
                );
              const navDisabled = orgLocked || knowledgeLocked;
              return (
              <NavItem
                key={item.label}
                icon={item.icon}
                label={item.label}
                active={Boolean(pid && pid === panel)}
                badge={"badge" in item ? item.badge : undefined}
                badgeVariant={"badgeVariant" in item ? item.badgeVariant : "accent"}
                disabled={navDisabled}
                title={
                  orgLocked
                    ? "Select an organization from Platform overview or Organizations first"
                    : knowledgeLocked
                      ? "Index at least one PDF under Documents (any workspace) before Chats and Team"
                      : undefined
                }
                onClick={() => {
                  if ("href" in item && item.href) {
                    navigate(item.href);
                  } else if ("id" in item && item.id) {
                    if (ORG_SCOPED_PANELS.includes(item.id) && needsOrganizationContext) return;
                    if (
                      KNOWLEDGE_GATED_PANELS.includes(item.id) &&
                      selectedOrgId &&
                      orgHasIndexedDocuments !== true &&
                      !isPlatformOwner
                    ) {
                      return;
                    }
                    if (item.id === "chats") {
                      setJumpToChatWsId(undefined);
                      /** Open the in-context workspace thread directly (latest session on load); otherwise show workspace picker. */
                      setChatWorkspaceId(ctxWorkspaceId ?? null);
                    }
                    setPanel(item.id);
                  }
                }}
              />
            );})}
          </div>
        ))}

        {/* User footer */}
        <div style={{ marginTop: "auto", padding: "12px 14px", borderTop: `1px solid ${C.hairline}` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <div style={{
              width: 27, height: 27, borderRadius: "50%",
              background: "linear-gradient(135deg,#2563EB,#7C3AED)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 10, fontWeight: 700, color: "white", flexShrink: 0,
            }}>
              {initials}
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: C.t1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 130 }}>
                {user?.email}
              </div>
              {user?.is_platform_owner && (
                <div style={{ fontSize: 9, color: C.green, fontFamily: C.mono }}>platform owner</div>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={() => void logout()}
            style={{
              width: "100%", padding: "5px 10px", border: `1px solid ${C.bd}`,
              borderRadius: 6, background: "transparent", color: C.t2,
              fontSize: 11, fontFamily: C.sans, cursor: "pointer",
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

        {/* Top bar */}
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
                {panel === "platform" ? "Platform overview"
                  : panel === "dashboard" ? "Dashboard"
                  : panel === "team"
                    ? (ctxWorkspaceName ? `Team · ${ctxWorkspaceName}` : "Team")
                  : panel === "orgs" ? "Organizations"
                  : panel === "workspaces" ? "Workspaces"
                  : panel === "chats"
                    ? (chatWorkspaceId ? "Chats · Conversation" : "Chats")
                  : panel === "analytics"
                    ? (ctxWorkspaceName ? `Analytics · ${ctxWorkspaceName}` : "Analytics")
                  : panel === "connectors"
                    ? (ctxWorkspaceName ? `Connectors · ${ctxWorkspaceName}` : "Connectors")
                  : panel === "billing" ? "Billing"
                  : "Documents"}
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

        {user?.is_platform_owner && (
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
                  {orgs.find((o) => o.id === selectedOrgId)?.name ?? "Organization"}
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

        {/* Scrollable content — chat embed fills column (no outer scroll) */}
        <div style={{
          flex: 1, minHeight: 0, display: "flex", flexDirection: "column",
          overflowY: panel === "chats" && chatWorkspaceId ? "hidden" : "auto",
        }}>

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
              onInviteTeam={() => navigate("/admin/team")}
              onOpenOrganizations={() => setPanel("orgs")}
            />
          )}

          {/* ── ORGANIZATIONS panel ── */}
          {panel === "orgs" && (
            <div style={{ padding: "22px 26px" }}>

              {/* ── Page header ── */}
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

              {/* ── Error ── */}
              {err && (
                <div style={{ padding: "10px 14px", background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: 8, fontSize: 12, color: C.red, marginBottom: 16 }}>
                  {err}
                </div>
              )}

              {/* ── Create org form ── */}
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
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: C.t3, marginBottom: 5, letterSpacing: "0.06em", textTransform: "uppercase" }}>Organization name *</div>
                      <Input value={newName} onChange={setNewName} placeholder="Acme Corp" required />
                    </div>
                    <div>
                      <div style={{ fontSize: 10, fontWeight: 600, color: C.t3, marginBottom: 5, letterSpacing: "0.06em", textTransform: "uppercase" }}>URL slug *</div>
                      <Input
                        value={newSlug}
                        onChange={(v) => setNewSlug(v.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
                        placeholder="acme-corp"
                        required
                      />
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Btn variant="primary" disabled={creating} onClick={() => {}}>
                      {creating ? "Creating…" : "Create organization"}
                    </Btn>
                    <Btn variant="ghost" onClick={() => { setShowCreateOrg(false); setErr(null); }}>Cancel</Btn>
                  </div>
                </form>
              )}

              {/* ── Loading skeleton ── */}
              {loading && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {[64, 64, 64].map((h, i) => (
                    <div key={i} style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, height: h, opacity: 0.4 }} />
                  ))}
                </div>
              )}

              {/* ── Empty state ── */}
              {!loading && orgs.length === 0 && (
                <div style={{
                  background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14,
                  padding: "52px 24px", textAlign: "center",
                }}>
                  <div style={{ fontSize: 38, marginBottom: 12 }}>🏢</div>
                  <div style={{ fontFamily: C.serif, fontSize: 20, color: C.t1, marginBottom: 6 }}>No organizations yet</div>
                  <div style={{ fontSize: 12, color: C.t2, marginBottom: 20 }}>
                    {user?.is_platform_owner
                      ? "Create your first organization to get started."
                      : "Ask your platform owner to add you to an organization."}
                  </div>
                  {user?.is_platform_owner && (
                    <Btn variant="primary" onClick={() => setShowCreateOrg(true)}>+ Create Organization</Btn>
                  )}
                </div>
              )}

              {/* ── Org selector + detail ── */}
              {!loading && orgs.length > 0 && (() => {
                const org = orgs.find((o) => o.id === selectedOrgId);
                return (
                  <>
                    {/* Wide dropdown */}
                    <div style={{ marginBottom: 24 }}>
                      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.t3, marginBottom: 10 }}>
                        Select Organization
                      </div>
                      <WideOrgDropdown
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

                    {/* Divider */}
                    <div style={{ height: 1, background: C.bd, marginBottom: 24 }} />

                    {/* Detail sections */}
                    {!org && isPlatformOwner && navigationScope === "platform" && (
                      <div style={{ fontSize: 13, color: C.t2, marginBottom: 16 }}>
                        Choose an organization above to see details, workspaces, and actions for that org.
                      </div>
                    )}
                    {org && (
                      <>
                        {orgScreen !== "overview" && (
                          <button
                            type="button"
                            onClick={() => setOrgScreen("overview")}
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 6,
                              marginBottom: 16,
                              background: "none",
                              border: "none",
                              cursor: "pointer",
                              fontSize: 12,
                              color: C.accent,
                              fontFamily: C.sans,
                            }}
                          >
                            ← Back to organization
                          </button>
                        )}
                        {orgScreen === "overview" && (
                          <OrgDetailView
                            org={org}
                            workspaces={workspaces}
                            loadingWs={loadingWs}
                            onOpenSettings={() => setOrgScreen("settings")}
                            onUploadClick={setUploadWs}
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
                          />
                        )}
                        {orgScreen === "settings" && (
                          <OrganizationSettingsPanel
                            org={org}
                            isPlatformOwner={!!user?.is_platform_owner}
                            showDangerZone={!!user?.is_platform_owner}
                            onSaved={(updated) => {
                              setOrgs((prev) => prev.map((o) => (o.id === updated.id ? updated : o)));
                            }}
                            onOrgDeleted={async () => {
                              setErr(null);
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
          )}

          {/* ── WORKSPACES panel ── */}
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

          {/* ── CHATS panel — list or embedded chat (platform sidebar always visible) ── */}
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

          {/* ── CONNECTORS panel ── */}
          {panel === "connectors" && (
            <ConnectorsPanel orgs={orgs} workspaceScope={workspaceInContext} />
          )}

          {/* ── TEAM MANAGEMENT panel ── */}
          {panel === "team" && (
            <TeamManagementPanel
              initialOrgId={(workspaceInContext?.organization_id || selectedOrgId) || undefined}
              scopedWorkspaceId={workspaceInContext?.id ?? null}
              scopedWorkspaceName={workspaceInContext?.name ?? null}
            />
          )}

          {/* ── KNOWLEDGE ANALYTICS panel ── */}
          {panel === "analytics" && (
            <KnowledgeAnalyticsPanel
              workspaceName={workspaceInContext?.name ?? null}
              organizationName={
                selectedOrgId ? orgs.find((o) => o.id === selectedOrgId)?.name ?? null : null
              }
            />
          )}

          {/* ── DOCUMENTS panel ── */}
          {panel === "docs" && (
            <DocumentsPanel orgs={orgs} scopeOrganizationId={selectedOrgId || null} />
          )}

          {/* ── BILLING panel ── */}
          {panel === "billing" && <BillingPanel />}
        </div>
      </div>

      {/* ── Upload modal ── */}
      {uploadWs && <UploadModal ws={uploadWs} onClose={() => setUploadWs(null)} />}

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
