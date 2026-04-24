import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useOrgShellTokens } from "../context/OrgShellThemeContext";

type Org = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description?: string | null;
  preferred_chat_provider?: string | null;
  preferred_chat_model?: string | null;
  openai_api_key_configured?: boolean;
  cohere_api_key_configured?: boolean;
  anthropic_api_key_configured?: boolean;
  openai_api_base_url?: string | null;
  anthropic_api_base_url?: string | null;
  ollama_base_url?: string | null;
  retrieval_strategy?: string | null;
  use_hosted_rerank?: boolean;
};

type AdminSummary = {
  totals: {
    queries_this_month: number;
    active_users_7d: number;
    documents_indexed: number;
    avg_response_time_ms: number;
  };
};

type Props = {
  orgs: Org[];
  totalWorkspaces: number;
  workspaceCountByOrg: Record<string, number>;
  loadingOrgs: boolean;
  onEnterOrganization: (orgId: string) => void;
  onOpenOrganizationsNav: () => void;
};

export function PlatformOwnerDashboard({
  orgs,
  totalWorkspaces,
  workspaceCountByOrg,
  loadingOrgs,
  onEnterOrganization,
  onOpenOrganizationsNav,
}: Props) {
  const C = useOrgShellTokens();
  const [metrics, setMetrics] = useState<AdminSummary | null>(null);
  const [metricsErr, setMetricsErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .get<AdminSummary>("/metrics/summary", { params: {} })
      .then(({ data }) => {
        if (!cancelled) setMetrics(data);
      })
      .catch((e) => {
        if (!cancelled) setMetricsErr(apiErrorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const attentionOrgs = orgs.filter((o) => o.status !== "active");
  const billingIssues = 0;

  return (
    <div style={{ padding: "22px 26px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontFamily: C.serif, fontSize: 28, color: C.t1, marginBottom: 6 }}>Platform overview</div>
        <div style={{ fontSize: 13, color: C.t2, lineHeight: 1.5 }}>
          Global health, organizations, and what needs attention — then open an organization to work in context.
        </div>
      </div>

      {/* KPI strip */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
          gap: 12,
          marginBottom: 22,
        }}
      >
        {[
          { label: "Organizations", value: loadingOrgs ? "…" : String(orgs.length), sub: "registered" },
          { label: "Workspaces", value: loadingOrgs ? "…" : String(totalWorkspaces), sub: "across all orgs" },
          {
            label: "Connectors",
            value: "—",
            sub: "sync status tracked per workspace",
          },
          {
            label: "Billing alerts",
            value: billingIssues === 0 ? "None" : String(billingIssues),
            sub: "outstanding issues",
          },
        ].map((k) => (
          <div
            key={k.label}
            style={{
              background: C.bgCard,
              border: `1px solid ${C.bd}`,
              borderRadius: 12,
              padding: "14px 16px",
            }}
          >
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: C.t3, textTransform: "uppercase" }}>
              {k.label}
            </div>
            <div style={{ fontFamily: C.mono, fontSize: 22, color: C.t1, marginTop: 6 }}>{k.value}</div>
            <div style={{ fontSize: 11, color: C.t3, marginTop: 4 }}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        {/* Usage */}
        <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "18px 20px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.t3, letterSpacing: "0.1em", marginBottom: 12 }}>
            Platform usage
          </div>
          {metricsErr && <div style={{ fontSize: 12, color: C.red }}>{metricsErr}</div>}
          {metrics && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <div style={{ fontSize: 11, color: C.t3 }}>Queries (30d)</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.t1 }}>{metrics.totals.queries_this_month.toLocaleString()}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: C.t3 }}>Active users (7d)</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.t1 }}>{metrics.totals.active_users_7d}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: C.t3 }}>Documents indexed</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.t1 }}>{metrics.totals.documents_indexed.toLocaleString()}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: C.t3 }}>Avg response</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: C.t1 }}>{metrics.totals.avg_response_time_ms} ms</div>
              </div>
            </div>
          )}
          {!metrics && !metricsErr && <div style={{ fontSize: 12, color: C.t3 }}>Loading metrics…</div>}
        </div>

        {/* Alerts & audit */}
        <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, padding: "18px 20px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.t3, letterSpacing: "0.1em", marginBottom: 12 }}>
            Audit & alerts
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, color: C.t2, fontSize: 13, lineHeight: 1.7 }}>
            <li>
              <Link to="/home?panel=audit" style={{ color: C.accent, fontWeight: 600 }}>
                Open audit log
              </Link>{" "}
              for sign-ins, exports, and admin actions.
            </li>
            <li>Connector sync jobs run on a schedule; check workspace connectors for failures.</li>
            <li>
              Review{" "}
              <Link to="/billing" style={{ color: C.accent, fontWeight: 600 }}>
                billing
              </Link>{" "}
              for seat limits and invoices.
            </li>
          </ul>
        </div>
      </div>

      {/* Attention */}
      {(attentionOrgs.length > 0 || billingIssues > 0) && (
        <div
          style={{
            background: "rgba(245,158,11,0.08)",
            border: "1px solid rgba(245,158,11,0.28)",
            borderRadius: 12,
            padding: "14px 18px",
            marginBottom: 20,
            fontSize: 13,
            color: C.t1,
          }}
        >
          <strong>Needs attention:</strong>{" "}
          {attentionOrgs.length > 0 && (
            <span>
              {attentionOrgs.length} organization(s) not in <em>active</em> status.{" "}
            </span>
          )}
          {billingIssues > 0 && <span>{billingIssues} billing issue(s).</span>}
        </div>
      )}

      {/* Organizations table */}
      <div style={{ fontSize: 11, fontWeight: 700, color: C.t3, letterSpacing: "0.12em", marginBottom: 10, textTransform: "uppercase" }}>
        Organizations
      </div>
      <div style={{ background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 14, overflow: "hidden" }}>
        {loadingOrgs ? (
          <div style={{ padding: 24, color: C.t3, fontSize: 13 }}>Loading…</div>
        ) : orgs.length === 0 ? (
          <div style={{ padding: 32, textAlign: "center", color: C.t2, fontSize: 13 }}>
            No organizations yet. Use{" "}
            <button
              type="button"
              onClick={onOpenOrganizationsNav}
              style={{ background: "none", border: "none", color: C.accent, cursor: "pointer", fontWeight: 600 }}
            >
              Organizations
            </button>{" "}
            to create one.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.bd}`, textAlign: "left", color: C.t3, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                <th style={{ padding: "12px 16px" }}>Organization</th>
                <th style={{ padding: "12px 16px" }}>Slug</th>
                <th style={{ padding: "12px 16px" }}>Status</th>
                <th style={{ padding: "12px 16px" }}>Workspaces</th>
                <th style={{ padding: "12px 16px" }} />
              </tr>
            </thead>
            <tbody>
              {orgs.map((o) => (
                <tr key={o.id} style={{ borderBottom: `1px solid ${C.bd}` }}>
                  <td style={{ padding: "12px 16px", color: C.t1, fontWeight: 600 }}>{o.name}</td>
                  <td style={{ padding: "12px 16px", color: C.t3, fontFamily: C.mono, fontSize: 12 }}>/{o.slug}</td>
                  <td style={{ padding: "12px 16px" }}>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: "2px 8px",
                        borderRadius: 100,
                        background: o.status === "active" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
                        color: o.status === "active" ? C.green : C.gold,
                      }}
                    >
                      {o.status}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", color: C.t2, fontFamily: C.mono }}>
                    {workspaceCountByOrg[o.id] ?? 0}
                  </td>
                  <td style={{ padding: "12px 16px", textAlign: "right" }}>
                    <button
                      type="button"
                      onClick={() => onEnterOrganization(o.id)}
                      style={{
                        background: C.accent,
                        color: "#fff",
                        border: "none",
                        borderRadius: 8,
                        padding: "6px 14px",
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: "pointer",
                        fontFamily: C.sans,
                      }}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={{ marginTop: 16, fontSize: 12, color: C.t3 }}>
        Analytics highlights for a single organization are available after you open that organization from the table above.
      </div>
    </div>
  );
}
