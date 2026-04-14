import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAdminOrgScope } from "../../hooks/useAdminOrgScope";

type AuditEvent = {
  id: string;
  created_at: string | null;
  actor_email: string;
  action: string;
  target_type: string;
  target_id: string | null;
  workspace_id: string | null;
  metadata: Record<string, unknown>;
};

export function AdminAuditPage() {
  const { orgs, orgId, onOrgChange, err: scopeErr } = useAdminOrgScope();
  const [action, setAction] = useState("");
  const [category, setCategory] = useState<"all" | "queries" | "admin" | "auth" | "sync">("all");
  const [eventSearch, setEventSearch] = useState("");
  const [userSearch, setUserSearch] = useState("");
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!orgId) return;
    setErr(null);
    try {
      const { data } = await api.get<AuditEvent[]>(`/admin/audit/${orgId}`, {
        params: { action: action || undefined, limit: 400 },
      });
      setRows(data);
    } catch (e) {
      setErr(apiErrorMessage(e));
    }
  }, [orgId, action]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredRows = rows.filter((r) => {
    const act = r.action.toLowerCase();
    const actor = (r.actor_email || "").toLowerCase();
    const text = `${r.action} ${r.target_type} ${JSON.stringify(r.metadata || {})}`.toLowerCase();
    if (category === "queries" && !act.includes("query")) return false;
    if (category === "admin" && !(act.includes("org") || act.includes("team") || act.includes("billing") || act.includes("admin"))) return false;
    if (category === "auth" && !(act.includes("auth") || act.includes("login") || act.includes("token"))) return false;
    if (category === "sync" && !(act.includes("sync") || act.includes("connector") || act.includes("document"))) return false;
    if (eventSearch && !text.includes(eventSearch.toLowerCase())) return false;
    if (userSearch && !actor.includes(userSearch.toLowerCase())) return false;
    return true;
  });

  function actionClass(actionName: string) {
    const a = actionName.toLowerCase();
    if (a.includes("query")) return "sk-action-tag acq";
    if (a.includes("auth") || a.includes("login")) return "sk-action-tag acau";
    if (a.includes("sync") || a.includes("connector") || a.includes("document")) return "sk-action-tag acs";
    return "sk-action-tag aca";
  }

  function resultBadge(r: AuditEvent) {
    const m = JSON.stringify(r.metadata || {}).toLowerCase();
    const fail = m.includes("error") || m.includes("failed") || m.includes("token_expired");
    return fail ? <span className="badge bred">token_expired</span> : <span className="badge bgreen">success</span>;
  }

  return (
    <RequireAdmin>
      <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Audit log" />
        <main className="ska-main">
          <div className="sk-panel sk-audit-header">
            <div>
              <div className="sk-connectors-title">Audit Log</div>
              <div className="sk-connectors-sub">Immutable record of all system events · Retained 2 years</div>
            </div>
            <button className="sk-btn secondary" type="button">
              Export to SIEM
            </button>
          </div>
          {(err || scopeErr) && <p className="sk-error">{err || scopeErr}</p>}
          <div className="sk-panel sk-spaced" style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: "0.75rem", maxWidth: 860 }}>
            <div>
              <label className="sk-label">Organization</label>
              <select className="sk-input" value={orgId} onChange={(e) => onOrgChange(e.target.value)}>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="sk-label">Action filter</label>
              <input className="sk-input" value={action} onChange={(e) => setAction(e.target.value)} placeholder="organization_updated" />
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
            <button type="button" className={`sk-filter-chip ${category === "queries" ? "on" : ""}`} onClick={() => setCategory("queries")}>
              Queries
            </button>
            <button type="button" className={`sk-filter-chip ${category === "admin" ? "on" : ""}`} onClick={() => setCategory("admin")}>
              Admin
            </button>
            <button type="button" className={`sk-filter-chip ${category === "auth" ? "on" : ""}`} onClick={() => setCategory("auth")}>
              Auth
            </button>
            <button type="button" className={`sk-filter-chip ${category === "sync" ? "on" : ""}`} onClick={() => setCategory("sync")}>
              Sync
            </button>
            <input className="sk-input" style={{ maxWidth: 220 }} placeholder="Search events..." value={eventSearch} onChange={(e) => setEventSearch(e.target.value)} />
            <input className="sk-input" style={{ maxWidth: 170 }} placeholder="User..." value={userSearch} onChange={(e) => setUserSearch(e.target.value)} />
            <button type="button" className="sk-filter-chip">
              Date range
            </button>
          </div>

          <div className="sk-panel" style={{ overflow: "auto" }}>
            <table className="sk-audit-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>IP</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.created_at ? new Date(r.created_at).toLocaleString() : "—"}</td>
                    <td>{r.actor_email || "system"}</td>
                    <td>
                      <span className={actionClass(r.action)}>{r.action}</span>
                    </td>
                    <td className="sk-mono">{r.target_type || "—"}</td>
                    <td>—</td>
                    <td>{resultBadge(r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredRows.length === 0 && <p className="sk-muted">No audit events for this scope.</p>}
          </div>
        </main>
      </div>
    </RequireAdmin>
  );
}
