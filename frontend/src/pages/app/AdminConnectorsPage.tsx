import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { connectorCatalogMatch } from "../../lib/connectorIds";
import { obtainConnectorConnectionId } from "../../lib/nangoConnect";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAdminOrgScope } from "../../hooks/useAdminOrgScope";
type Ws = { id: string; name: string };

type CatalogItem = {
  id: string;
  name: string;
  description: string;
  icon: string;
  statLabel: string;
  secondaryLabel: string;
  secondaryValue: string;
  accentBg?: string;
  accentBorder?: string;
  manualOnly?: boolean;
  backendReady: boolean;
};

const CATALOG: CatalogItem[] = [
  {
    id: "confluence",
    name: "Confluence",
    icon: "📘",
    description: "Wiki pages, docs, meeting notes across all spaces",
    statLabel: "Documents",
    secondaryLabel: "Spaces",
    secondaryValue: "12",
    accentBg: "rgba(0,101,209,0.1)",
    accentBorder: "rgba(0,101,209,0.3)",
    backendReady: true,
  },
  {
    id: "google-drive",
    name: "Google Drive",
    icon: "📁",
    description: "Docs, Sheets summaries, uploaded PDFs",
    statLabel: "Documents",
    secondaryLabel: "Drives",
    secondaryValue: "3",
    accentBg: "rgba(26,115,232,0.1)",
    accentBorder: "rgba(26,115,232,0.3)",
    backendReady: true,
  },
  {
    id: "notion",
    name: "Notion",
    icon: "⬛",
    description: "Pages, databases, team wikis",
    statLabel: "Pages",
    secondaryLabel: "Databases",
    secondaryValue: "24",
    backendReady: true,
  },
  {
    id: "github",
    name: "GitHub",
    icon: "🐙",
    description: "READMEs, docs, code comments",
    statLabel: "Repos",
    secondaryLabel: "Files",
    secondaryValue: "2,840",
    backendReady: true,
  },
  {
    id: "jira",
    name: "Jira",
    icon: "🎫",
    description: "Issues, epics, resolution notes",
    statLabel: "Issues",
    secondaryLabel: "Projects",
    secondaryValue: "7",
    accentBg: "rgba(0,82,204,0.1)",
    backendReady: true,
  },
  {
    id: "sharepoint",
    name: "SharePoint",
    icon: "📋",
    description: "Document libraries, Microsoft 365",
    statLabel: "Documents",
    secondaryLabel: "Libraries",
    secondaryValue: "—",
    backendReady: false,
  },
  {
    id: "zendesk",
    name: "Zendesk",
    icon: "💬",
    description: "Support tickets, help center articles",
    statLabel: "Tickets",
    secondaryLabel: "Groups",
    secondaryValue: "—",
    backendReady: false,
  },
  {
    id: "file-upload",
    name: "File Upload",
    icon: "📂",
    description: "Manually upload PDFs, DOCX, TXT files",
    statLabel: "Documents",
    secondaryLabel: "Status",
    secondaryValue: "Manual",
    manualOnly: true,
    backendReady: false,
  },
];

type ConnectorRow = {
  catalog: CatalogItem;
  backendId: string | null;
  status: string;
  lastSync: string | null;
  docCount: number;
};

function mapUiStatus(apiStatus: string): ConnectorRow["status"] {
  const s = apiStatus.toLowerCase();
  if (s === "active" || s === "connected") return "active";
  if (s === "syncing") return "syncing";
  if (s === "error" || s === "failed") return "error";
  if (s === "skipped") return "pending";
  return "pending";
}

function statusBadge(status: string) {
  const map: Record<string, { label: string; className: string }> = {
    none: { label: "Not connected", className: "badge bgray" },
    manual: { label: "Manual", className: "badge bgray" },
    pending: { label: "Pending", className: "badge bgray" },
    active: { label: "● Synced", className: "badge bgreen" },
    syncing: { label: "● Syncing", className: "badge bblue" },
    error: { label: "● Sync error", className: "badge bred" },
  };
  const s = map[status] ?? map.none;
  return <span className={s.className}>{s.label}</span>;
}

export function AdminConnectorsPage() {
  const { orgs, orgId, onOrgChange } = useAdminOrgScope();
  const [workspaces, setWorkspaces] = useState<Ws[]>([]);
  const [rows, setRows] = useState<ConnectorRow[]>(() =>
    CATALOG.map((c) => ({
      catalog: c,
      backendId: null,
      status: "none",
      lastSync: null,
      docCount: 0,
    })),
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const connectedRows = useMemo(() => rows.filter((r) => Boolean(r.backendId)), [rows]);
  const totalDocs = useMemo(() => rows.reduce((sum, r) => sum + r.docCount, 0), [rows]);
  const latestSync = useMemo(() => {
    const times = rows
      .map((r) => (r.lastSync ? new Date(r.lastSync).getTime() : 0))
      .filter((t) => Number.isFinite(t) && t > 0);
    if (!times.length) return null;
    return new Date(Math.max(...times));
  }, [rows]);

  const refreshBackend = useCallback(async () => {
    if (!orgId) return;
    const { data } = await api.get<
      {
        id: string;
        connector_type: string;
        status: string;
        last_synced_at: string | null;
        document_count: number;
      }[]
    >(`/admin/connectors/${orgId}`);
    setRows(
      CATALOG.map((c) => {
        const hit = data.find((d) => connectorCatalogMatch(c.id, d.connector_type));
        return {
          catalog: c,
          backendId: hit ? hit.id : null,
          status: hit ? mapUiStatus(hit.status) : "none",
          lastSync: hit?.last_synced_at ?? null,
          docCount: hit?.document_count ?? 0,
        };
      }),
    );
  }, [orgId]);

  useEffect(() => {
    if (!orgId) return;
    void api
      .get<Ws[]>(`/workspaces/org/${orgId}`)
      .then((r) => setWorkspaces(r.data))
      .catch(() => setWorkspaces([]));
  }, [orgId]);

  useEffect(() => {
    if (!orgId) return;
    void refreshBackend().catch(() => {
      setRows(
        CATALOG.map((c) => ({
          catalog: c,
          backendId: null,
          status: "none",
          lastSync: null,
          docCount: 0,
        })),
      );
    });
  }, [orgId, refreshBackend]);

  async function connect(catalogId: string) {
    if (!orgId) {
      setMsg("Select an organization first.");
      return;
    }
    const ws = workspaces[0]?.id;
    if (!ws) {
      setMsg("Create a workspace in this organization before connecting.");
      return;
    }
    const cat = CATALOG.find((c) => c.id === catalogId);
    if (cat?.manualOnly) {
      setMsg("File upload is available from the Documents screen.");
      return;
    }
    if (cat && !cat.backendReady) {
      setMsg(`${cat.name} is on the roadmap — use Confluence, Drive, Notion, GitHub, or Jira for a live sync demo.`);
      return;
    }
    setBusy(catalogId);
    setMsg(null);
    try {
      const connectionId = await obtainConnectorConnectionId(catalogId);
      const { data } = await api.post<{ connector_id: string | null }>("/connectors/activate", {
        integration_id: catalogId,
        connection_id: connectionId,
        organization_id: orgId,
        workspace_id: ws,
      });
      setMsg(
        data.connector_id
          ? `Saved. Use “Sync now” to pull documents (requires NANGO_SECRET_KEY + provider credentials in Nango). ID: ${data.connector_id.slice(0, 8)}…`
          : "Activation accepted — ensure organization_id was sent.",
      );
      await refreshBackend();
    } catch (e) {
      setMsg(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function syncNow(catalogId: string, backendId: string | null) {
    if (!backendId) return;
    setBusy(catalogId);
    setMsg(null);
    try {
      const { data } = await api.post(`/connectors/${backendId}/sync`, {}, { params: { full_sync: false } });
      setMsg(typeof data === "object" && data && "detail" in data ? String((data as { detail?: string }).detail) : "Sync finished.");
      await refreshBackend();
    } catch (e) {
      setMsg(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  function latestSyncLabel() {
    if (!latestSync) return "No sync yet";
    const mins = Math.max(1, Math.round((Date.now() - latestSync.getTime()) / 60000));
    if (mins < 60) return `Synced ${mins} min ago`;
    const hrs = Math.round(mins / 60);
    return `Synced ${hrs} hr ago`;
  }

  function number(value: number) {
    return new Intl.NumberFormat().format(value);
  }

  return (
    <RequireAdmin>
      <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Connectors" />
        <main className="ska-main">
          {orgs.length > 0 && (
            <div className="sk-panel" style={{ marginBottom: "1rem", maxWidth: 420 }}>
              <label className="sk-label" htmlFor="conn-org">
                Organization
              </label>
              <select id="conn-org" className="sk-input" style={{ maxWidth: 360 }} value={orgId} onChange={(e) => onOrgChange(e.target.value)}>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="sk-panel sk-connectors-header">
            <div>
              <div className="sk-connectors-title">Connectors</div>
              <div className="sk-connectors-sub">
                {connectedRows.length} active · {latestSyncLabel()} · {number(totalDocs)} documents
              </div>
            </div>
            <button type="button" className="sk-btn" onClick={() => setMsg("Use Connect on any available source card below.")}>
              + Add connector
            </button>
          </div>

          {msg && <p className="sk-muted">{msg}</p>}

          <div className="sk-connectors-grid">
            {rows.map((r) => (
              <div
                key={r.catalog.id}
                className={`sk-panel sk-connector-card ${!r.backendId ? "is-disconnected" : "is-connected"} ${r.status === "error" ? "is-error" : ""}`}
              >
                <div className="sk-row" style={{ alignItems: "center" }}>
                  <div
                    className="sk-connector-logo"
                    style={{
                      background: r.catalog.accentBg ?? "var(--surface2)",
                      borderColor: r.catalog.accentBorder ?? "var(--border)",
                    }}
                  >
                    {r.catalog.icon}
                  </div>
                </div>
                <h3 className="sk-connector-name">{r.catalog.name}</h3>
                <p className="sk-muted sk-connector-desc">
                  {r.catalog.description}
                </p>

                {r.backendId && (
                  <div className="sk-connector-stats">
                    <div>
                      <div className="sk-connector-stat-label">{r.catalog.statLabel}</div>
                      <div className="sk-connector-stat-value">{number(r.docCount)}</div>
                    </div>
                    <div>
                      <div className="sk-connector-stat-label">{r.catalog.secondaryLabel}</div>
                      <div className="sk-connector-stat-value">{r.catalog.secondaryValue}</div>
                    </div>
                  </div>
                )}

                <div className="sk-connector-foot">
                  {statusBadge(r.backendId ? r.status : r.catalog.manualOnly ? "manual" : "none")}

                  {!r.backendId && (
                    <button
                      type="button"
                      className="sk-btn"
                      style={{ padding: "0.25rem 0.625rem", fontSize: "0.7rem" }}
                      disabled={busy === r.catalog.id || !orgId}
                      onClick={() => void connect(r.catalog.id)}
                    >
                      {busy === r.catalog.id ? "..." : r.catalog.manualOnly ? "Upload →" : "Connect →"}
                    </button>
                  )}

                  {r.backendId && (
                    <div style={{ display: "flex", gap: 4 }}>
                      <button
                        type="button"
                        className={`sk-btn ${r.status === "error" ? "" : "secondary"}`}
                        style={{ padding: "0.2rem 0.45rem", fontSize: "0.65rem" }}
                        disabled={busy === r.catalog.id || r.status === "syncing"}
                        onClick={() => void syncNow(r.catalog.id, r.backendId)}
                      >
                        {busy === r.catalog.id ? "..." : r.status === "error" ? "Retry" : "Sync now"}
                      </button>
                      {r.status !== "error" && (
                        <button
                          type="button"
                          className="sk-btn secondary"
                          style={{ padding: "0.2rem 0.45rem", fontSize: "0.65rem" }}
                          onClick={() => setMsg(`${r.catalog.name} settings are coming next.`)}
                        >
                          Settings
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {r.backendId && (
                  <div className={`sk-connector-sync ${r.status === "error" ? "is-error" : ""}`}>
                    {r.status === "error"
                      ? "Token expired · Reconnect"
                      : `Last sync: ${r.lastSync ? new Date(r.lastSync).toLocaleString() : "No sync yet"}`}
                  </div>
                )}

                {!r.backendId && !r.catalog.backendReady && !r.catalog.manualOnly && (
                  <div className="sk-connector-sync">
                    Roadmap connector
                  </div>
                )}
                {!r.backendId && r.catalog.manualOnly && (
                  <div className="sk-connector-sync">
                    Use Documents upload for ingestion
                  </div>
                )}
              </div>
            ))}
          </div>
        </main>
      </div>
    </RequireAdmin>
  );
}
