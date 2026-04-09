import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { AdminPermissionGuard } from "../../components/AdminPermissionGuard";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAuth } from "../../context/AuthContext";

type Org = { id: string; name: string };
type Ws = { id: string; name: string };
type DocRow = {
  id: string;
  workspace_id: string;
  workspace_name: string;
  filename: string;
  source_type: string;
  status: string;
  page_count: number;
  chunk_count: number;
  updated_at: string | null;
  last_indexed_at: string | null;
};

export function AdminDocumentsPage() {
  const { user } = useAuth();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [workspaces, setWorkspaces] = useState<Ws[]>([]);
  const [orgId, setOrgId] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [q, setQ] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [rows, setRows] = useState<DocRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<Org[]>("/organizations/me")
      .then((r) => {
        setOrgs(r.data);
        if (!orgId && r.data[0]) {
          setOrgId(r.data[0].id);
        }
      })
      .catch((e) => setErr(apiErrorMessage(e)));
  }, [orgId]);

  useEffect(() => {
    if (!user) return;
    if (!user.is_platform_owner && !orgId && user.org_ids_as_owner?.[0]) {
      setOrgId(user.org_ids_as_owner[0]);
    }
  }, [user, orgId]);

  useEffect(() => {
    if (!orgId) return;
    void api
      .get<Ws[]>(`/workspaces/org/${orgId}`)
      .then((r) => setWorkspaces(r.data))
      .catch(() => setWorkspaces([]));
  }, [orgId]);

  const load = useCallback(async () => {
    if (!orgId) return;
    setErr(null);
    try {
      const { data } = await api.get<DocRow[]>(`/admin/documents/${orgId}`, {
        params: {
          workspace_id: workspaceId || undefined,
          q: q.trim() || undefined,
          limit: 300,
        },
      });
      setRows(data);
    } catch (e: any) {
      const status = e.response?.status;
      if (status === 403) {
        setErr("You don't have permission to view admin documents. Organization owner access required.");
      } else if (status === 404) {
        setErr("Admin documents endpoint not available. This feature may not be enabled.");
      } else {
        setErr(apiErrorMessage(e));
      }
    }
  }, [orgId, workspaceId, q]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredRows = rows.filter((r) => {
    if (sourceFilter === "all") return true;
    if (sourceFilter === "needs_reindex") return r.status.toLowerCase() !== "indexed";
    return r.source_type.toLowerCase() === sourceFilter;
  });

  const uniqueSources = Array.from(new Set(rows.map((r) => r.source_type.toLowerCase()))).sort();

  function sourceBadge(source: string) {
    const s = source.toLowerCase();
    if (s.includes("confluence") || s.includes("google") || s.includes("notion")) return "badge bblue";
    if (s.includes("upload") || s.includes("file")) return "badge bgray";
    return "badge bgray";
  }

  function statusLabel(status: string) {
    const s = status.toLowerCase();
    if (s === "indexed") return { label: "Indexed", className: "doc-status ok" };
    if (s.includes("index")) return { label: "Indexing...", className: "doc-status running" };
    if (s.includes("stale") || s.includes("error") || s.includes("failed")) return { label: "Stale", className: "doc-status stale" };
    return { label: status, className: "doc-status" };
  }

  return (
    <RequireAdmin>
      <AdminPermissionGuard>
        <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Documents" />
        <main className="ska-main">
          <div className="sk-panel sk-docs-header">
            <div>
              <div className="sk-connectors-title">Document Library</div>
              <div className="sk-connectors-sub">
                {filteredRows.length.toLocaleString()} documents · {uniqueSources.length || 0} sources ·{" "}
                {filteredRows.every((r) => r.status.toLowerCase() === "indexed") ? "All indexed" : "Mixed status"}
              </div>
            </div>
            <button className="sk-btn" type="button" onClick={() => setErr("Use workspace upload in chat for file ingestion.")}>
              + Upload files
            </button>
          </div>
          {err && <p className="sk-error">{err}</p>}
          <div className="sk-panel sk-spaced" style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "1fr 1fr 1fr auto" }}>
            <div>
              <label className="sk-label">Organization</label>
              <select className="sk-input" value={orgId} onChange={(e) => setOrgId(e.target.value)}>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="sk-label">Workspace</label>
              <select className="sk-input" value={workspaceId} onChange={(e) => setWorkspaceId(e.target.value)}>
                <option value="">All</option>
                {workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="sk-label">Search</label>
              <input className="sk-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="filename or source type" />
            </div>
            <div style={{ alignSelf: "end" }}>
              <button className="sk-btn secondary" onClick={() => void load()}>
                Refresh
              </button>
            </div>
          </div>

          <div className="sk-doc-filters">
            <button type="button" className={`sk-filter-chip ${sourceFilter === "all" ? "on" : ""}`} onClick={() => setSourceFilter("all")}>
              All
            </button>
            {uniqueSources.map((s) => (
              <button key={s} type="button" className={`sk-filter-chip ${sourceFilter === s ? "on" : ""}`} onClick={() => setSourceFilter(s)}>
                {s}
              </button>
            ))}
            <button
              type="button"
              className={`sk-filter-chip ${sourceFilter === "needs_reindex" ? "on" : ""}`}
              onClick={() => setSourceFilter("needs_reindex")}
            >
              ⚠ Needs reindex
            </button>
          </div>

          <div className="sk-panel" style={{ overflow: "auto" }}>
            <table className="sk-doc-table">
              <thead>
                <tr>
                  <th style={{ width: "38%" }}>Document</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Chunks</th>
                  <th>Last indexed</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => {
                  const stat = statusLabel(r.status);
                  return (
                    <tr key={r.id}>
                      <td>
                        <div className="sk-doc-name-cell">
                          <div className="sk-doc-icon">📄</div>
                          <div>
                            <div className="sk-doc-title">{r.filename}</div>
                            <div className="sk-doc-sub">
                              {r.workspace_name} · {r.page_count || 0} pages
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={sourceBadge(r.source_type)}>{r.source_type}</span>
                      </td>
                      <td>
                        <span className={stat.className}>
                          <span className="sdot" />
                          {stat.label}
                        </span>
                      </td>
                      <td className="sk-mono">{r.chunk_count.toLocaleString()}</td>
                      <td>{r.last_indexed_at ? new Date(r.last_indexed_at).toLocaleString() : "—"}</td>
                      <td style={{ textAlign: "right" }}>
                        <button className="sk-btn secondary" style={{ padding: "0.2rem 0.45rem", fontSize: "0.66rem" }} type="button">
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filteredRows.length === 0 && <p className="sk-muted">No documents found for current scope.</p>}
          </div>
        </main>
      </div>
      </AdminPermissionGuard>
    </RequireAdmin>
  );
}
