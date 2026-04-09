import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, apiErrorMessage } from "../../api/client";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { AdminPermissionGuard } from "../../components/AdminPermissionGuard";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAuth } from "../../context/AuthContext";

type Summary = {
  totals: {
    queries_this_month: number;
    active_users_7d: number;
    documents_indexed: number;
    avg_response_time_ms: number;
  };
  queries_per_day: { date: string; count: number }[];
  top_queries: { text: string; frequency: number; avg_confidence: number; last_asked: string }[];
  unanswered_queries: { text: string; confidence: number; last_asked: string }[];
};

const DEMO: Summary = {
  totals: {
    queries_this_month: 1284,
    active_users_7d: 42,
    documents_indexed: 312,
    avg_response_time_ms: 840,
  },
  queries_per_day: Array.from({ length: 30 }, (_, i) => ({
    date: `Day ${i + 1}`,
    count: 20 + Math.round(15 * Math.sin(i / 3)),
  })),
  top_queries: [
    { text: "What is the refund policy?", frequency: 54, avg_confidence: 0.82, last_asked: "2026-04-06" },
    { text: "Security requirements for vendors", frequency: 41, avg_confidence: 0.76, last_asked: "2026-04-05" },
    { text: "Contract termination clause", frequency: 33, avg_confidence: 0.71, last_asked: "2026-04-04" },
  ],
  unanswered_queries: [
    { text: "Obscure tax edge case", confidence: 0.32, last_asked: "2026-04-03" },
    { text: "Legacy SKU mapping", confidence: 0.28, last_asked: "2026-04-02" },
  ],
};

type Org = { id: string; name: string };

function exportUnansweredCsv(rows: Summary["unanswered_queries"]) {
  const header = "text,confidence,last_asked\n";
  const body = rows.map((r) => `"${r.text.replace(/"/g, '""')}",${r.confidence},${r.last_asked}`).join("\n");
  const blob = new Blob([header + body], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "unanswered-queries.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

export function AdminDashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<"frequency" | "avg_confidence" | "last_asked">("frequency");
  const [orgs, setOrgs] = useState<Org[]>([]);
  /** null = all orgs (platform owner only) */
  const [scopeOrgId, setScopeOrgId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    void api
      .get<Org[]>("/organizations/me")
      .then((r) => setOrgs(r.data))
      .catch(() => setOrgs([]));
  }, [user]);

  useEffect(() => {
    if (!user) return;
    if (!user.is_platform_owner && user.org_ids_as_owner?.length) {
      setScopeOrgId(user.org_ids_as_owner[0] ?? null);
    }
  }, [user]);

  const load = useCallback(async () => {
    if (!user) return;
    setErr(null);
    try {
      const params: Record<string, string> = {};
      if (!user.is_platform_owner) {
        const oid = scopeOrgId ?? user.org_ids_as_owner[0];
        if (!oid) {
          setErr("No organization — assign org owner role or create an organization.");
          setData(null);
          return;
        }
        params.organization_id = oid;
      } else if (scopeOrgId) {
        params.organization_id = scopeOrgId;
      }
      const { data: d } = await api.get<Summary>("/admin/metrics/summary", { params });
      setData(d);
    } catch (e: any) {
      const status = e.response?.status;
      if (status === 403) {
        setErr("Admin access required. Organization owner permissions needed.");
      } else if (status === 404) {
        setErr("Admin metrics endpoint not available. Showing demo data.");
      } else {
        setErr(apiErrorMessage(e));
      }
      setData(DEMO);
    }
  }, [user, scopeOrgId]);

  useEffect(() => {
    void load();
  }, [load]);

  const sortedTop = useMemo(() => {
    if (!data) return [];
    const rows = [...data.top_queries];
    rows.sort((a, b) => {
      if (sortKey === "frequency") return b.frequency - a.frequency;
      if (sortKey === "avg_confidence") return b.avg_confidence - a.avg_confidence;
      return b.last_asked.localeCompare(a.last_asked);
    });
    return rows;
  }, [data, sortKey]);

  const showDemoBanner = err && data === DEMO;

  return (
    <RequireAdmin>
      <AdminPermissionGuard>
        <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Admin" />
        <main className="ska-main">
          <h2 style={{ marginTop: 0 }}>Overview</h2>
          {user?.is_platform_owner && orgs.length > 0 && (
            <div className="sk-panel" style={{ marginBottom: "1rem" }}>
              <label className="sk-label" htmlFor="admin-scope">
                Scope
              </label>
              <select
                id="admin-scope"
                className="sk-input"
                style={{ maxWidth: 320 }}
                value={scopeOrgId ?? ""}
                onChange={(e) => setScopeOrgId(e.target.value || null)}
              >
                <option value="">All organizations</option>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
              <p className="sk-muted" style={{ fontSize: "0.85rem", marginTop: "0.5rem" }}>
                Metrics come from stored query logs and indexed documents (live data).
              </p>
            </div>
          )}

          {showDemoBanner && (
            <p className="sk-muted">
              API: {err} — showing <strong>demo</strong> metrics for the meeting preview.
            </p>
          )}
          {err && !showDemoBanner && <p className="sk-error">{err}</p>}

          {data && (
            <>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: "1rem",
                  marginBottom: "2rem",
                }}
              >
                <div className="sk-panel">
                  <div className="sk-label">Queries (month)</div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700 }}>{data.totals.queries_this_month}</div>
                </div>
                <div className="sk-panel">
                  <div className="sk-label">Active users (7d)</div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700 }}>{data.totals.active_users_7d}</div>
                </div>
                <div className="sk-panel">
                  <div className="sk-label">Documents indexed</div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700 }}>{data.totals.documents_indexed}</div>
                </div>
                <div className="sk-panel">
                  <div className="sk-label">Avg response (ms)</div>
                  <div style={{ fontSize: "1.75rem", fontWeight: 700 }}>{data.totals.avg_response_time_ms}</div>
                </div>
              </div>

              <div className="sk-panel sk-spaced" style={{ height: 280 }}>
                <h3 style={{ marginTop: 0 }}>Queries per day (30d)</h3>
                <ResponsiveContainer width="100%" height="85%">
                  <LineChart data={data.queries_per_day}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a3344" />
                    <XAxis dataKey="date" tick={{ fill: "var(--muted)", fontSize: 10 }} />
                    <YAxis tick={{ fill: "var(--muted)", fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: "var(--surface2)", border: "1px solid var(--border)" }} />
                    <Line type="monotone" dataKey="count" stroke="var(--accent)" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <h3>Top queries</h3>
              {sortedTop.length === 0 ? (
                <p className="sk-muted">No query history yet — use the chat app to generate analytics.</p>
              ) : (
                <div style={{ overflow: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                    <thead>
                      <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                        <th style={{ padding: "0.5rem" }}>Query</th>
                        <th style={{ padding: "0.5rem", cursor: "pointer" }} onClick={() => setSortKey("frequency")}>
                          Frequency
                        </th>
                        <th style={{ padding: "0.5rem", cursor: "pointer" }} onClick={() => setSortKey("avg_confidence")}>
                          Avg confidence
                        </th>
                        <th style={{ padding: "0.5rem", cursor: "pointer" }} onClick={() => setSortKey("last_asked")}>
                          Last asked
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedTop.map((row, i) => (
                        <tr key={`${row.text}-${i}`} style={{ borderBottom: "1px solid var(--border)" }}>
                          <td style={{ padding: "0.5rem" }}>{row.text}</td>
                          <td style={{ padding: "0.5rem" }}>{row.frequency}</td>
                          <td style={{ padding: "0.5rem" }}>{row.avg_confidence.toFixed(2)}</td>
                          <td style={{ padding: "0.5rem" }}>{row.last_asked}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <h3>Knowledge gaps (low confidence or no evidence)</h3>
              <div className="sk-panel">
                {data.unanswered_queries.length === 0 ? (
                  <p className="sk-muted">None flagged — or no query logs yet.</p>
                ) : (
                  <ul>
                    {data.unanswered_queries.map((u, i) => (
                      <li key={`${u.text}-${i}`} style={{ marginBottom: "0.5rem" }}>
                        <strong>{u.text}</strong>{" "}
                        <span className="sk-muted">
                          (conf {u.confidence.toFixed(2)}, {u.last_asked})
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <button
                  type="button"
                  className="sk-btn secondary"
                  onClick={() => exportUnansweredCsv(data.unanswered_queries)}
                  disabled={data.unanswered_queries.length === 0}
                >
                  Export CSV
                </button>
              </div>

              <h3>Connectors</h3>
              <p className="sk-muted">
                Manage integrations and last sync times on <Link to="/admin/connectors">Connectors</Link>.
              </p>
            </>
          )}
        </main>
      </div>
      </AdminPermissionGuard>
    </RequireAdmin>
  );
}
