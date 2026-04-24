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

const DEFAULT_CATALOG: CatalogItem[] = [
  {
    id: "google-drive",
    name: "Google Drive",
    emoji: "📁",
    description:
      "Google Docs as text. Optionally limit sync to specific folders (and subfolders) via folder IDs from Drive URLs.",
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

type DriveSync = { folder_ids: string[]; include_subfolders: boolean };
type ConnectorViewFilter = "all" | "available" | "connected" | "coming-soon";

type Row = {
  catalog: CatalogItem;
  backendId: string | null;
  assigned: boolean;
  workspaceIds: string[];
  status: string;
  lastSync: string | null;
  docCount: number;
  driveSync?: DriveSync | null;
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
  const [catalog, setCatalog] = useState<CatalogItem[]>(DEFAULT_CATALOG);
  const [rows, setRows] = useState<Row[]>(() =>
    DEFAULT_CATALOG.map((c) => ({
      catalog: c,
      backendId: null,
      assigned: false,
      workspaceIds: [],
      status: "none",
      lastSync: null,
      docCount: 0,
      driveSync: null,
    })),
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [nangoHint, setNangoHint] = useState<string | null>(null);
  const [driveFolderText, setDriveFolderText] = useState("");
  const [driveIncludeSubfolders, setDriveIncludeSubfolders] = useState(true);
  const [workspaceNamesById, setWorkspaceNamesById] = useState<Record<string, string>>({});
  const [viewFilter, setViewFilter] = useState<ConnectorViewFilter>("all");
  const [showAddConnectorModal, setShowAddConnectorModal] = useState(false);
  const [modalQuery, setModalQuery] = useState("");
  const [modalFilter, setModalFilter] = useState<ConnectorViewFilter>("all");
  const [modalError, setModalError] = useState<string | null>(null);

  const googleDriveRow = useMemo(() => rows.find((r) => r.catalog.id === "google-drive"), [rows]);

  const driveSyncKey = googleDriveRow?.backendId
    ? `${googleDriveRow.backendId}:${JSON.stringify(googleDriveRow.driveSync?.folder_ids ?? [])}:${String(googleDriveRow.driveSync?.include_subfolders ?? true)}`
    : "";

  useEffect(() => {
    if (!driveSyncKey) return;
    const r = rows.find((x) => x.catalog.id === "google-drive" && x.backendId);
    setDriveFolderText((r?.driveSync?.folder_ids ?? []).join("\n"));
    setDriveIncludeSubfolders(r?.driveSync?.include_subfolders !== false);
    // Only re-apply from server when saved config changes (not on unrelated row refreshes).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [driveSyncKey]);

  const refresh = useCallback(async () => {
    if (!organizationId) return;
    const [connectorsResp, workspacesResp] = await Promise.all([
      api.get<
        {
          id: string;
          connector_type: string;
          status: string;
          last_synced_at: string | null;
          document_count: number;
          workspace_id?: string | null;
          workspace_ids?: string[] | null;
          drive_sync?: DriveSync | null;
          drive_sync_by_workspace?: Record<string, DriveSync> | null;
        }[]
      >(`/connectors/organization/${organizationId}`),
      api.get<{ id: string; name: string }[]>(`/workspaces/org/${organizationId}`),
    ]);
    const data = connectorsResp.data;
    const wsMap: Record<string, string> = {};
    for (const ws of workspacesResp.data) wsMap[ws.id] = ws.name;
    setWorkspaceNamesById(wsMap);
    setRows(
      catalog.map((c) => {
        const hit = data.find((d) => connectorCatalogMatch(c.id, d.connector_type));
        const workspaceIds = Array.isArray(hit?.workspace_ids)
          ? hit.workspace_ids.filter((id): id is string => typeof id === "string" && id.length > 0)
          : hit?.workspace_id
            ? [hit.workspace_id]
            : [];
        const assigned = workspaceIds.includes(workspaceId);
        return {
          catalog: c,
          backendId: hit ? hit.id : null,
          assigned,
          workspaceIds,
          status: hit && assigned ? mapUiStatus(hit.status) : "none",
          lastSync: hit?.last_synced_at ?? null,
          docCount: hit?.document_count ?? 0,
          driveSync:
            (hit?.drive_sync_by_workspace && workspaceId in hit.drive_sync_by_workspace
              ? hit.drive_sync_by_workspace[workspaceId]
              : hit?.drive_sync) ?? null,
        };
      }),
    );
  }, [organizationId, workspaceId, catalog]);

  useEffect(() => {
    void fetchPublicConfig()
      .then((cfg) => {
        if (Array.isArray(cfg.connector_catalog) && cfg.connector_catalog.length > 0) {
          const normalized = cfg.connector_catalog
            .map((item) => ({
              id: String(item.id || "").trim(),
              name: String(item.name || "").trim(),
              emoji: String(item.emoji || "🔌"),
              description: String(item.description || ""),
              backendReady: Boolean(item.backendReady),
            }))
            .filter((item) => item.id.length > 0 && item.name.length > 0);
          if (normalized.length > 0) setCatalog(normalized);
        }
        if (cfg.features?.nango_connect) {
          setNangoHint("OAuth via Nango is enabled — Connect opens Google (or the provider) to authorize.");
        } else {
          setNangoHint(
            "Set NANGO_SECRET_KEY on the API and configure Google Drive in Nango. Connect Session auth is required by Nango now.",
          );
        }
      })
      .catch(() => setNangoHint(null));
  }, []);

  useEffect(() => {
    if (!organizationId) return;
    void refresh().catch(() => {});
  }, [organizationId, refresh]);

  const activeCount = useMemo(() => rows.filter((r) => r.backendId).length, [rows]);
  const connectedInWorkspaceCount = useMemo(() => rows.filter((r) => r.assigned).length, [rows]);
  const totalDocs = useMemo(() => rows.reduce((s, r) => s + r.docCount, 0), [rows]);
  const availableCount = useMemo(
    () => rows.filter((r) => r.catalog.backendReady && !r.assigned).length,
    [rows],
  );
  const comingSoonCount = useMemo(
    () => rows.filter((r) => !r.catalog.backendReady && !r.backendId).length,
    [rows],
  );
  const addableRows = useMemo(
    () => rows.filter((r) => r.catalog.backendReady && !r.assigned),
    [rows],
  );
  const visibleRows = useMemo(() => {
    if (viewFilter === "available") return rows.filter((r) => r.catalog.backendReady && !r.assigned);
    if (viewFilter === "connected") return rows.filter((r) => r.assigned);
    if (viewFilter === "coming-soon") return rows.filter((r) => !r.catalog.backendReady && !r.backendId);
    return rows;
  }, [rows, viewFilter]);
  const modalRows = useMemo(() => {
    const q = modalQuery.trim().toLowerCase();
    const inScope = rows.filter((r) => {
      if (modalFilter === "available") return r.catalog.backendReady && !r.assigned;
      if (modalFilter === "connected") return r.assigned;
      if (modalFilter === "coming-soon") return !r.catalog.backendReady && !r.backendId;
      return true;
    });
    if (!q) return inScope;
    return inScope.filter((r) => {
      return (
        r.catalog.name.toLowerCase().includes(q) ||
        r.catalog.id.toLowerCase().includes(q) ||
        r.catalog.description.toLowerCase().includes(q)
      );
    });
  }, [rows, modalFilter, modalQuery]);

  async function connect(row: Row): Promise<{ ok: boolean; error?: string }> {
    const catalogId = row.catalog.id;
    if (!row.catalog.backendReady) return { ok: false, error: "This connector is not enabled yet." };
    setBusy(catalogId);
    setMsg(null);
    try {
      if (row.backendId) {
        await api.put(`/connectors/${row.backendId}/workspaces/${workspaceId}`);
        setMsg(`Connector enabled for “${wsName}”.`);
      } else {
        const connectionId = await obtainConnectorConnectionId(catalogId, organizationId);
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
      }
      await refresh();
      return { ok: true };
    } catch (e) {
      const errMsg = apiErrorMessage(e);
      setMsg(errMsg);
      return { ok: false, error: errMsg };
    } finally {
      setBusy(null);
    }
  }

  async function removeConnector(catalogId: string, backendId: string | null) {
    if (!backendId) return;
    if (!window.confirm(`Remove this connector from workspace “${wsName}”? Ingested documents are not deleted.`)) return;
    setBusy(catalogId);
    setMsg(null);
    try {
      await api.delete(`/connectors/${backendId}/workspaces/${workspaceId}`);
      setMsg(`Connector removed from “${wsName}”.`);
      await refresh();
    } catch (e) {
      setMsg(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  }

  async function saveDriveFolderScope(backendId: string) {
    setBusy("google-drive");
    setMsg(null);
    const ids = driveFolderText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    try {
      await api.patch(`/connectors/${backendId}/config`, {
        workspace_id: workspaceId,
        drive_folder_ids: ids,
        drive_include_subfolders: driveIncludeSubfolders,
      });
      setMsg("Google Drive folder scope saved. Run sync to pull documents.");
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
      const { data } = await api.post<{
        status?: string;
        detail?: string;
        documents_ingested?: number;
        errors?: string[];
      }>(`/connectors/${backendId}/sync`, {}, { params: { full_sync: false, workspace_id: workspaceId } });
      const status = String(data?.status || "ok").toLowerCase();
      const detail = typeof data?.detail === "string" ? data.detail : "";
      const docs = Number.isFinite(data?.documents_ingested) ? Number(data?.documents_ingested) : null;
      const errCount = Array.isArray(data?.errors) ? data.errors.filter(Boolean).length : 0;
      if (status === "error") {
        setMsg(detail || (errCount > 0 ? `Sync failed with ${errCount} item errors.` : "Sync failed."));
      } else if (detail) {
        setMsg(detail);
      } else if (docs !== null) {
        if (docs > 0) {
          setMsg(
            errCount > 0
              ? `Sync finished: ${docs} documents ingested (${errCount} item errors).`
              : `Sync finished: ${docs} documents ingested.`,
          );
        } else {
          setMsg(
            "Sync finished: 0 documents ingested. Verify the folder has Google Docs or text files this connected account can access.",
          );
        }
      } else {
        setMsg("Sync finished.");
      }
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
        <span style={{ color: C.green, fontWeight: 600 }}>{connectedInWorkspaceCount} connected</span>
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
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {[
          { id: "all", label: "All", count: rows.length },
          { id: "available", label: "Available", count: availableCount },
          { id: "connected", label: "Connected", count: connectedInWorkspaceCount },
          { id: "coming-soon", label: "Coming soon", count: comingSoonCount },
        ].map((item) => {
          const active = viewFilter === (item.id as ConnectorViewFilter);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setViewFilter(item.id as ConnectorViewFilter)}
              style={{
                padding: "5px 10px",
                borderRadius: 999,
                border: `1px solid ${active ? C.accent : C.bd}`,
                background: active ? "rgba(37,99,235,0.1)" : C.bgE,
                color: active ? C.accent : C.t2,
                fontSize: 10,
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: C.sans,
              }}
            >
              {item.label} ({item.count})
            </button>
          );
        })}
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
          gap: 12,
        }}
        className="workspace-connector-grid"
      >
        <button
          type="button"
          onClick={() => {
            setModalFilter("all");
            setModalQuery("");
            setModalError(null);
            setShowAddConnectorModal(true);
          }}
          style={{
            background: C.bgCard,
            border: `1px dashed ${C.bd}`,
            borderRadius: 14,
            padding: "14px 14px 12px",
            minHeight: 148,
            display: "flex",
            flexDirection: "column",
            alignItems: "flex-start",
            justifyContent: "space-between",
            textAlign: "left",
            cursor: "pointer",
            fontFamily: C.sans,
          }}
        >
          <div>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                border: `1px solid ${C.bd}`,
                background: C.bgE,
                color: C.accent,
                fontSize: 24,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 10,
              }}
            >
              +
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 4 }}>Add connector</div>
            <div style={{ fontSize: 10, color: C.t3, lineHeight: 1.35 }}>
              Pick from available platform connectors and add one to this workspace.
            </div>
          </div>
          <div style={{ fontSize: 10, color: C.t2 }}>
            {addableRows.length} available
          </div>
        </button>
        {visibleRows.map((r) => {
          const assignedWorkspaceNames = r.workspaceIds.map((id) => workspaceNamesById[id] ?? id);
          const assignedWorkspaceTitle = assignedWorkspaceNames.length
            ? assignedWorkspaceNames.join(", ")
            : "Not assigned to any workspace";
          const isComingSoon = !r.catalog.backendReady && !r.backendId;
          return (
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
                {isComingSoon && (
                  <div
                    style={{
                      marginTop: 6,
                      display: "inline-flex",
                      alignItems: "center",
                      borderRadius: 999,
                      border: `1px solid ${C.bd}`,
                      background: C.bgE,
                      color: C.t3,
                      fontSize: 9,
                      padding: "2px 8px",
                    }}
                  >
                    Coming soon
                  </div>
                )}
                {r.backendId && (
                  <div
                    title={assignedWorkspaceTitle}
                    style={{
                      marginTop: 6,
                      display: "inline-flex",
                      alignItems: "center",
                      borderRadius: 999,
                      border: `1px solid ${C.bd}`,
                      background: C.bgE,
                      color: C.t2,
                      fontSize: 9,
                      padding: "2px 8px",
                    }}
                  >
                    {r.workspaceIds.length} workspace{r.workspaceIds.length === 1 ? "" : "s"}
                  </div>
                )}
              </div>
            </div>
            {isComingSoon && (
              <div style={{ marginBottom: 8, fontSize: 10, color: C.t3 }}>
                This connector card is visible, but backend sync support is not enabled yet.
              </div>
            )}
            {r.backendId && r.assigned && (
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Indexed: <span style={{ fontFamily: C.mono, color: C.t1 }}>{r.docCount}</span>
              </div>
            )}
            <div style={{ marginTop: "auto", display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              {isComingSoon && (
                <button
                  type="button"
                  style={{
                    padding: "6px 12px",
                    borderRadius: 8,
                    border: `1px solid ${C.bd}`,
                    background: C.bgE,
                    color: C.t3,
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "not-allowed",
                    fontFamily: C.sans,
                  }}
                  disabled
                  title="Connector visible in catalog, but backend implementation is not enabled yet."
                >
                  Coming soon
                </button>
              )}
              {(!r.backendId || !r.assigned) && r.catalog.backendReady && (
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
                  onClick={() => void connect(r)}
                >
                  {busy === r.catalog.id ? "…" : r.backendId ? "Add to workspace" : "Add connector"}
                </button>
              )}
              {r.backendId && r.assigned && (
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
            {r.catalog.id === "google-drive" && r.backendId && r.assigned && (
              <div
                style={{
                  marginTop: 10,
                  paddingTop: 10,
                  borderTop: `1px solid ${C.bd}`,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div style={{ fontSize: 10, fontWeight: 600, color: C.t2 }}>Sync scope</div>
                <div style={{ fontSize: 10, color: C.t3, lineHeight: 1.35 }}>
                  Paste one folder ID per line (from a Drive folder URL). Leave empty to sync all Google Docs the
                  account can list. Subfolders are included when enabled.
                </div>
                <textarea
                  value={driveFolderText}
                  onChange={(e) => setDriveFolderText(e.target.value)}
                  rows={4}
                  spellCheck={false}
                  placeholder={"e.g. 1a2b3c4d5e6f7g8h9i0j\n(second root folder id)"}
                  style={{
                    width: "100%",
                    resize: "vertical",
                    boxSizing: "border-box",
                    fontSize: 10,
                    fontFamily: C.mono,
                    color: C.t1,
                    background: C.bgE,
                    border: `1px solid ${C.bd}`,
                    borderRadius: 8,
                    padding: 8,
                  }}
                />
                <label style={{ fontSize: 10, color: C.t2, display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={driveIncludeSubfolders}
                    onChange={(e) => setDriveIncludeSubfolders(e.target.checked)}
                  />
                  Include subfolders
                </label>
                <button
                  type="button"
                  style={{
                    alignSelf: "flex-start",
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
                  disabled={busy === "google-drive"}
                  onClick={() => void saveDriveFolderScope(r.backendId as string)}
                >
                  {busy === "google-drive" ? "…" : "Save folder scope"}
                </button>
              </div>
            )}
            </div>
          );
        })}
      </div>
      {visibleRows.length === 0 && (
        <div style={{ fontSize: 11, color: C.t3 }}>
          No connectors match this filter in the current workspace context.
        </div>
      )}
      {showAddConnectorModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(2,6,23,0.55)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 2000,
            padding: 20,
          }}
        >
          <div
            style={{
              width: "min(920px, 96vw)",
              maxHeight: "85vh",
              overflow: "auto",
              background: C.bgCard,
              border: `1px solid ${C.bd}`,
              borderRadius: 16,
              padding: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: C.t1, marginBottom: 3 }}>Add connector</div>
                <div style={{ fontSize: 11, color: C.t3 }}>
                  Browse the full connector catalog for workspace <span style={{ color: C.t1 }}>{wsName}</span>.
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setModalError(null);
                  setShowAddConnectorModal(false);
                }}
                style={{
                  border: `1px solid ${C.bd}`,
                  background: C.bgE,
                  color: C.t2,
                  borderRadius: 8,
                  padding: "6px 10px",
                  cursor: "pointer",
                  fontSize: 11,
                  fontFamily: C.sans,
                }}
              >
                Close
              </button>
            </div>
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 10,
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 12,
              }}
            >
              <input
                value={modalQuery}
                onChange={(e) => setModalQuery(e.target.value)}
                placeholder="Search connectors by name or id"
                style={{
                  width: "min(340px, 100%)",
                  border: `1px solid ${C.bd}`,
                  background: C.bgE,
                  color: C.t1,
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 11,
                  fontFamily: C.sans,
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {[
                  { id: "all", label: "All", count: rows.length },
                  { id: "available", label: "Available", count: availableCount },
                  { id: "connected", label: "Added", count: connectedInWorkspaceCount },
                  { id: "coming-soon", label: "Coming soon", count: comingSoonCount },
                ].map((item) => {
                  const active = modalFilter === (item.id as ConnectorViewFilter);
                  return (
                    <button
                      key={`modal-filter-${item.id}`}
                      type="button"
                      onClick={() => setModalFilter(item.id as ConnectorViewFilter)}
                      style={{
                        padding: "5px 10px",
                        borderRadius: 999,
                        border: `1px solid ${active ? C.accent : C.bd}`,
                        background: active ? "rgba(37,99,235,0.1)" : C.bgE,
                        color: active ? C.accent : C.t2,
                        fontSize: 10,
                        fontWeight: 600,
                        cursor: "pointer",
                        fontFamily: C.sans,
                      }}
                    >
                      {item.label} ({item.count})
                    </button>
                  );
                })}
              </div>
            </div>
            {modalError && (
              <div
                style={{
                  marginBottom: 10,
                  border: "1px solid rgba(239,68,68,0.35)",
                  background: "rgba(239,68,68,0.08)",
                  color: "#fca5a5",
                  borderRadius: 8,
                  padding: "8px 10px",
                  fontSize: 11,
                  lineHeight: 1.45,
                }}
              >
                {modalError}
              </div>
            )}
            {modalRows.length === 0 ? (
              <div style={{ fontSize: 12, color: C.t3, padding: "8px 2px" }}>
                No connectors match this filter.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {modalRows.map((r) => {
                  const isComingSoon = !r.catalog.backendReady && !r.backendId;
                  const isAdded = r.assigned;
                  const canAdd = !isAdded && !isComingSoon && r.catalog.backendReady;
                  return (
                    <div
                      key={`modal-${r.catalog.id}`}
                      style={{
                        border: `1px solid ${C.bd}`,
                        background: C.bgE,
                        borderRadius: 12,
                        padding: 12,
                        display: "grid",
                        gridTemplateColumns: "1fr auto",
                        gap: 12,
                        alignItems: "center",
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                          <div
                            style={{
                              width: 28,
                              height: 28,
                              borderRadius: 7,
                              border: `1px solid ${C.bd}`,
                              background: C.bgCard,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontSize: 14,
                              flexShrink: 0,
                            }}
                          >
                            {r.catalog.emoji}
                          </div>
                          <div style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>{r.catalog.name}</div>
                          <span
                            style={{
                              fontSize: 9,
                              borderRadius: 999,
                              border: `1px solid ${C.bd}`,
                              padding: "2px 8px",
                              color: isAdded ? C.green : isComingSoon ? C.t3 : C.t2,
                              background: C.bgCard,
                            }}
                          >
                            {isAdded ? "Already added" : isComingSoon ? "Coming soon" : "Available"}
                          </span>
                        </div>
                        <div style={{ fontSize: 10, color: C.t3, lineHeight: 1.4, marginBottom: 4 }}>
                          {r.catalog.description}
                        </div>
                        <div style={{ fontSize: 9, color: C.t3 }}>
                          id: <span style={{ fontFamily: C.mono }}>{r.catalog.id}</span>
                        </div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <button
                          type="button"
                          style={{
                            border: `1px solid ${canAdd ? C.accent : C.bd}`,
                            background: canAdd ? "rgba(37,99,235,0.1)" : C.bgCard,
                            color: canAdd ? C.accent : C.t3,
                            borderRadius: 8,
                            padding: "6px 10px",
                            fontSize: 11,
                            fontWeight: 600,
                            cursor: canAdd && busy !== r.catalog.id ? "pointer" : "not-allowed",
                            fontFamily: C.sans,
                            whiteSpace: "nowrap",
                          }}
                          disabled={!canAdd || busy === r.catalog.id}
                          onClick={() => {
                            setModalError(null);
                            void connect(r).then((res) => {
                              if (res.ok) {
                                setShowAddConnectorModal(false);
                                setModalError(null);
                              } else if (res.error) {
                                setModalError(res.error);
                              } else {
                                setModalError("Failed to add connector. Try again.");
                              }
                            });
                          }}
                        >
                          {isAdded
                            ? "Added"
                            : isComingSoon
                              ? "Coming soon"
                              : busy === r.catalog.id
                                ? "…"
                                : r.backendId
                                  ? "Add to workspace"
                                  : "Add connector"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
      <div style={{ fontSize: 10, color: C.t3 }}>
        {activeCount > 0
          ? `${activeCount} connector integration${activeCount === 1 ? "" : "s"} available in this organization.`
          : "No connector integrations configured yet for this organization."}{" "}
        {catalog.length > 0 ? `Catalog: ${catalog.length} available.` : ""}
      </div>
      <style>{`
        @media (max-width: 1100px) {
          .workspace-connector-grid { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        }
      `}</style>
    </div>
  );
}
