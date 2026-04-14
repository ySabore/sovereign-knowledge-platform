import { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useOrgShellTokens } from "../context/OrgShellThemeContext";
import { connectorCatalogMatch } from "../lib/connectorIds";
import { obtainConnectorConnectionId } from "../lib/nangoConnect";
import { fetchPublicConfig } from "../lib/publicConfig";

type CatalogItem = {
  id: string;
  name: string;
  emoji: string;
  description: string;
  backendReady: boolean;
};

const CATALOG: CatalogItem[] = [
  {
    id: "google-drive",
    name: "Google Drive",
    emoji: "📁",
    description: "Google Docs (exported as text) and files your account can access.",
    backendReady: true,
  },
  {
    id: "confluence",
    name: "Confluence",
    emoji: "📘",
    description: "Wiki pages via your Atlassian site (configure site URL in Nango).",
    backendReady: true,
  },
  {
    id: "notion",
    name: "Notion",
    emoji: "📓",
    description: "Pages returned from Notion search.",
    backendReady: true,
  },
  {
    id: "github",
    name: "GitHub",
    emoji: "🐙",
    description: "Markdown/text from a repo (set owner/repo in connector config).",
    backendReady: true,
  },
  {
    id: "jira",
    name: "Jira",
    emoji: "🎫",
    description: "Issues and descriptions from Jira Cloud.",
    backendReady: true,
  },
];

type Row = {
  catalog: CatalogItem;
  backendId: string | null;
  status: string;
  lastSync: string | null;
  docCount: number;
};

function mapUiStatus(apiStatus: string): Row["status"] {
  const s = apiStatus.toLowerCase();
  if (s === "active" || s === "connected") return "active";
  if (s === "syncing") return "syncing";
  if (s === "error" || s === "failed") return "error";
  return "pending";
}

export function WorkspaceConnectorsPanel({
  organizationId,
  workspaceId,
  wsName,
}: {
  organizationId: string;
  workspaceId: string;
  wsName: string;
}) {
  const C = useOrgShellTokens();
  const [rows, setRows] = useState<Row[]>(() =>
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
  const [nangoHint, setNangoHint] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!organizationId) return;
    const { data } = await api.get<
      {
        id: string;
        connector_type: string;
        status: string;
        last_synced_at: string | null;
        document_count: number;
      }[]
    >(`/connectors/organization/${organizationId}`);
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
  }, [organizationId]);

  useEffect(() => {
    void fetchPublicConfig()
      .then((cfg) => {
        if (cfg.features?.nango_connect) {
          setNangoHint("OAuth via Nango is enabled — Connect opens Google (or the provider) to authorize.");
        } else if ((cfg.nango_public_key ?? "").trim()) {
          setNangoHint("Set NANGO_SECRET_KEY on the API and configure the Google Drive integration in Nango to sync files.");
        } else {
          setNangoHint("Add NANGO_PUBLIC_KEY and NANGO_SECRET_KEY to enable OAuth; until then, Connect stores a demo link (sync will be empty).");
        }
      })
      .catch(() => setNangoHint(null));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    void refresh().catch(() => {});
  }, [organizationId, refresh]);

  const activeCount = useMemo(() => rows.filter((r) => r.backendId).length, [rows]);
  const totalDocs = useMemo(() => rows.reduce((s, r) => s + r.docCount, 0), [rows]);

  async function connect(catalogId: string) {
    const cat = CATALOG.find((c) => c.id === catalogId);
    if (!cat?.backendReady) return;
    setBusy(catalogId);
    setMsg(null);
    try {
      const connectionId = await obtainConnectorConnectionId(catalogId);
      const { data } = await api.post<{ connector_id: string | null }>("/connectors/activate", {
        integration_id: catalogId,
        connection_id: connectionId,
        organization_id: organizationId,
        workspace_id: workspaceId,
      });
      setMsg(
        data.connector_id
          ? `Connected. Run sync to pull documents into “${wsName}”.`
          : "Activation accepted.",
      );
      await refresh();
    } catch (e) {
      setMsg(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function removeConnector(catalogId: string, backendId: string | null) {
    if (!backendId) return;
    if (!window.confirm("Remove this connector registration? Ingested documents are not deleted.")) return;
    setBusy(catalogId);
    setMsg(null);
    try {
      await api.delete(`/connectors/${backendId}`);
      setMsg("Connector removed.");
      await refresh();
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
      const detail = typeof data === "object" && data && "detail" in data ? String((data as { detail?: string }).detail) : "";
      setMsg(detail || "Sync finished.");
      await refresh();
    } catch (e) {
      setMsg(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div style={{ fontSize: 12, color: C.t2 }}>
        <span style={{ color: C.green, fontWeight: 600 }}>{activeCount} connected</span>
        <span style={{ color: C.t3 }}> · </span>
        <span style={{ fontFamily: C.mono, color: C.t1 }}>{totalDocs.toLocaleString()} documents</span>
        <span style={{ fontSize: 10, color: C.t3, marginLeft: 6 }}>· {wsName}</span>
      </div>
      {msg && (
        <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.45, maxWidth: 720 }}>
          {msg}
        </div>
      )}
      {nangoHint && (
        <div style={{ fontSize: 11, color: C.t3, lineHeight: 1.45, maxWidth: 720 }}>
          {nangoHint}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 12,
        }}
        className="workspace-connector-grid"
      >
        {rows.map((r) => (
          <div
            key={r.catalog.id}
            style={{
              background: C.bgCard,
              border: `1px solid ${r.status === "error" ? "rgba(239,68,68,0.35)" : C.bd}`,
              borderRadius: 14,
              padding: "14px 14px 12px",
              minHeight: 148,
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 8 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  flexShrink: 0,
                  background: C.bgE,
                  border: `1px solid ${C.bd}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 20,
                }}
              >
                {r.catalog.emoji}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 4 }}>{r.catalog.name}</div>
                <div style={{ fontSize: 10, color: C.t3, lineHeight: 1.35 }}>{r.catalog.description}</div>
              </div>
            </div>
            {r.backendId && (
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Indexed: <span style={{ fontFamily: C.mono, color: C.t1 }}>{r.docCount}</span>
              </div>
            )}
            <div style={{ marginTop: "auto", display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              {!r.backendId && r.catalog.backendReady && (
                <button
                  type="button"
                  style={{
                    padding: "6px 12px",
                    borderRadius: 8,
                    border: `1px solid ${C.accent}`,
                    background: "rgba(37,99,235,0.1)",
                    color: C.accent,
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: busy ? "wait" : "pointer",
                    fontFamily: C.sans,
                  }}
                  disabled={busy === r.catalog.id}
                  onClick={() => void connect(r.catalog.id)}
                >
                  {busy === r.catalog.id ? "…" : "Connect"}
                </button>
              )}
              {r.backendId && (
                <>
                  <button
                    type="button"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 8,
                      border: `1px solid ${C.bd}`,
                      background: C.bgE,
                      color: C.t1,
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: busy ? "wait" : "pointer",
                      fontFamily: C.sans,
                    }}
                    disabled={busy === r.catalog.id || r.status === "syncing"}
                    onClick={() => void syncNow(r.catalog.id, r.backendId)}
                  >
                    {busy === r.catalog.id ? "…" : "Sync now"}
                  </button>
                  <button
                    type="button"
                    style={{
                      padding: "6px 12px",
                      borderRadius: 8,
                      border: `1px solid rgba(239,68,68,0.35)`,
                      background: "rgba(239,68,68,0.06)",
                      color: "#f87171",
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: busy ? "wait" : "pointer",
                      fontFamily: C.sans,
                    }}
                    disabled={busy === r.catalog.id}
                    onClick={() => void removeConnector(r.catalog.id, r.backendId)}
                  >
                    Remove
                  </button>
                </>
              )}
              {r.lastSync && (
                <span style={{ fontSize: 9, color: C.t3, fontFamily: C.mono }}>
                  Last: {new Date(r.lastSync).toLocaleString()}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      <style>{`
        @media (max-width: 1100px) {
          .workspace-connector-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        }
      `}</style>
    </div>
  );
}
