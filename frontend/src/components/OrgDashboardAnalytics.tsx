import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, apiErrorMessage } from "../api/client";
import { useOrgShellUiOptional } from "../context/OrgShellThemeContext";

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

function formatAvgResponse(ms: number): string {
  if (ms <= 0) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms} ms`;
}

/** Design tokens aligned with analytics dashboard mock (dark enterprise) */
const T_DARK = {
  bg: "#0b0e14",
  card: "#161b22",
  cardBorder: "rgba(255,255,255,0.06)",
  primary: "#2357ff",
  barMuted: "#1e3a5f",
  t1: "#f0f3f8",
  t2: "#8b949e",
  t3: "#484f58",
  green: "#3fb950",
  orange: "#d29922",
  red: "#f85149",
  serif: '"Instrument Serif",Georgia,serif',
  sans: '"DM Sans",sans-serif',
};

const T_BRIGHT = {
  bg: "#f4f6fb",
  card: "#ffffff",
  cardBorder: "rgba(15,23,42,0.1)",
  primary: "#2563eb",
  barMuted: "#bfdbfe",
  t1: "#0f172a",
  t2: "#475569",
  t3: "#64748b",
  green: "#059669",
  orange: "#b45309",
  red: "#dc2626",
  serif: '"Instrument Serif",Georgia,serif',
  sans: '"DM Sans",sans-serif',
};

type AnalyticsTokens = typeof T_DARK;

function useOrgAnalyticsTokens(): AnalyticsTokens {
  const ui = useOrgShellUiOptional();
  return ui?.brightMode ? T_BRIGHT : T_DARK;
}

function Btn({
  children,
  variant = "primary",
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  variant?: "primary" | "ghost";
  onClick?: () => void;
  disabled?: boolean;
}) {
  const T = useOrgAnalyticsTokens();
  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 14px",
    borderRadius: 8,
    fontSize: 12,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: T.sans,
    border: "none",
    transition: "opacity .15s",
    opacity: disabled ? 0.45 : 1,
  };
  if (variant === "primary") {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={disabled ? undefined : onClick}
        style={{
          ...base,
          background: T.primary,
          color: "#fff",
          boxShadow: `0 0 20px rgba(35,87,255,0.25)`,
        }}
      >
        {children}
      </button>
    );
  }
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      style={{
        ...base,
        background: "transparent",
        color: T.t2,
        border: `1px solid ${T.cardBorder}`,
      }}
    >
      {children}
    </button>
  );
}

function KpiCard({
  label,
  value,
  delta,
  deltaTone,
  sub,
}: {
  label: string;
  value: string;
  delta: string;
  deltaTone: "upGood" | "upBad" | "neutral";
  sub?: string;
}) {
  const T = useOrgAnalyticsTokens();
  const deltaColor =
    deltaTone === "upGood" ? T.green : deltaTone === "upBad" ? T.red : T.t2;
  return (
    <div
      style={{
        background: T.card,
        border: `1px solid ${T.cardBorder}`,
        borderRadius: 12,
        padding: "18px 20px",
        minHeight: 108,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.1em",
          color: T.t3,
          textTransform: "uppercase",
          marginBottom: 10,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: T.serif,
          fontSize: 28,
          color: T.t1,
          lineHeight: 1.1,
          marginBottom: 6,
        }}
      >
        {value}
      </div>
      <div style={{ fontSize: 12, fontWeight: 500, color: deltaColor }}>{delta}</div>
      {sub && <div style={{ fontSize: 11, color: T.t2, marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

function ConfidenceBar({
  segments,
  emptyHint,
}: {
  segments: { pct: number; label: string; color: string }[];
  emptyHint?: string;
}) {
  const T = useOrgAnalyticsTokens();
  if (!segments.length) {
    return (
      <div
        style={{
          background: T.card,
          border: `1px solid ${T.cardBorder}`,
          borderRadius: 12,
          padding: "18px 20px",
          height: "100%",
          minHeight: 280,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 600, color: T.t1, marginBottom: 12, fontFamily: T.sans }}>
          Answer confidence
        </div>
        <div style={{ fontSize: 12, color: T.t3, lineHeight: 1.5 }}>{emptyHint ?? "No query samples yet."}</div>
      </div>
    );
  }
  return (
    <div
      style={{
        background: T.card,
        border: `1px solid ${T.cardBorder}`,
        borderRadius: 12,
        padding: "18px 20px",
        height: "100%",
        minHeight: 280,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          color: T.t1,
          marginBottom: 20,
          fontFamily: T.sans,
        }}
      >
        Answer confidence
      </div>
      <div
        style={{
          display: "flex",
          height: 12,
          borderRadius: 6,
          overflow: "hidden",
          marginBottom: 22,
        }}
      >
        {segments.map((s) => (
          <div
            key={s.label}
            style={{ width: `${s.pct}%`, background: s.color, flexShrink: 0 }}
            title={`${s.label} ${s.pct}%`}
          />
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {segments.map((s) => (
          <div
            key={s.label}
            style={{ display: "flex", alignItems: "center", gap: 10 }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: s.color,
                flexShrink: 0,
              }}
            />
            <div style={{ flex: 1, fontSize: 12, color: T.t2, fontFamily: T.sans }}>
              {s.label}{" "}
              <span style={{ color: T.t1, fontWeight: 600 }}>({s.pct}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function confidenceLevel(avg: number): "High" | "Medium" | "Low" {
  if (avg >= 0.65) return "High";
  if (avg >= 0.4) return "Medium";
  return "Low";
}

function ConfPill({ level }: { level: "High" | "Medium" | "Low" }) {
  const T = useOrgAnalyticsTokens();
  const bg =
    level === "High"
      ? "rgba(63,185,80,0.15)"
      : level === "Medium"
        ? "rgba(210,153,34,0.15)"
        : "rgba(248,81,73,0.12)";
  const color = level === "High" ? T.green : level === "Medium" ? T.orange : T.red;
  const border =
    level === "High"
      ? "rgba(63,185,80,0.35)"
      : level === "Medium"
        ? "rgba(210,153,34,0.35)"
        : "rgba(248,81,73,0.35)";
  return (
    <span
      style={{
        display: "inline-flex",
        padding: "3px 10px",
        borderRadius: 100,
        fontSize: 11,
        fontWeight: 600,
        background: bg,
        color,
        border: `1px solid ${border}`,
        fontFamily: T.sans,
      }}
    >
      {level}
    </span>
  );
}

function downloadTopQueriesCsv(rows: Summary["top_queries"]) {
  const header = "query,frequency,avg_confidence,last_asked\n";
  const body = rows
    .map(
      (r) =>
        `"${r.text.replace(/"/g, '""')}",${r.frequency},${r.avg_confidence.toFixed(3)},${r.last_asked}`,
    )
    .join("\n");
  const blob = new Blob([header + body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "top-queries-this-month.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export function OrgDashboardAnalytics({
  organizationId,
  orgDisplayName,
  onExportCsv,
  onInviteTeam,
  onOpenOrganizations,
}: {
  organizationId: string | null;
  orgDisplayName: string;
  onExportCsv?: () => void;
  onInviteTeam?: () => void;
  /** Shown when no org is scoped (e.g. platform owner on platform-wide context). */
  onOpenOrganizations?: () => void;
}) {
  const T = useOrgAnalyticsTokens();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!organizationId) {
      setSummary(null);
      setErr(null);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const { data } = await api.get<Summary>("/admin/metrics/summary", {
        params: { organization_id: organizationId },
      });
      setSummary(data);
    } catch (e) {
      const status = (e as { response?: { status?: number } }).response?.status;
      if (status === 403) {
        setErr(
          "Usage analytics are limited to organization owners (or platform administrators). Ask an owner to grant access.",
        );
      } else if (status === 400) {
        setErr(apiErrorMessage(e));
      } else {
        setErr(apiErrorMessage(e));
      }
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const chartData = useMemo(() => {
    const rows = summary?.queries_per_day ?? [];
    return rows.map((d, i) => ({
      day: i + 1,
      label: d.date.length >= 10 ? d.date.slice(5, 10) : d.date,
      q: d.count,
      highlight: i === rows.length - 1,
    }));
  }, [summary]);

  const confidenceSegments = useMemo(() => {
    const rows = summary?.top_queries ?? [];
    if (!rows.length) return [] as { pct: number; label: string; color: string }[];
    let high = 0;
    let med = 0;
    let low = 0;
    for (const r of rows) {
      const c = r.avg_confidence;
      if (c >= 0.65) high += 1;
      else if (c >= 0.4) med += 1;
      else low += 1;
    }
    const n = rows.length;
    const pct = (x: number) => Math.max(0, Math.round((100 * x) / n));
    return [
      { pct: pct(high), label: "High", color: "#3fb950" },
      { pct: pct(med), label: "Medium", color: "#d29922" },
      { pct: pct(low), label: "Low / Not found", color: "#f85149" },
    ].filter((s) => s.pct > 0);
  }, [summary]);

  const metricsSuffix = " · Last 30 days (query logs)";

  return (
    <div
      style={{
        background: T.bg,
        minHeight: "100%",
        padding: "26px 28px 40px",
        fontFamily: T.sans,
      }}
    >
      {!organizationId && onOpenOrganizations && (
        <div
          style={{
            marginBottom: 20,
            padding: "14px 18px",
            borderRadius: 12,
            border: `1px solid ${T.cardBorder}`,
            background: T.card,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <p style={{ margin: 0, fontSize: 13, color: T.t2, lineHeight: 1.5, maxWidth: 520 }}>
            No organization is selected. Open the Organizations page to pick one (or create one), then return here for
            dashboards scoped to that org.
          </p>
          <Btn variant="primary" onClick={onOpenOrganizations}>
            Organizations →
          </Btn>
        </div>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 20,
          marginBottom: 28,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: T.serif,
              fontSize: 32,
              fontWeight: 400,
              color: T.t1,
              margin: 0,
              lineHeight: 1.15,
            }}
          >
            Dashboard
          </h1>
          <p style={{ margin: "8px 0 0", fontSize: 13, color: T.t2, lineHeight: 1.5 }}>
            {organizationId ? (
              <>
                {onOpenOrganizations ? (
                  <button
                    type="button"
                    onClick={onOpenOrganizations}
                    title="Open organization details"
                    style={{
                      padding: 0,
                      border: "none",
                      background: "none",
                      cursor: "pointer",
                      font: "inherit",
                      fontSize: 13,
                      fontWeight: 600,
                      color: T.primary,
                      fontFamily: T.sans,
                      textDecoration: "underline",
                      textUnderlineOffset: 3,
                    }}
                  >
                    {orgDisplayName}
                  </button>
                ) : (
                  <span style={{ fontWeight: 600, color: T.t1 }}>{orgDisplayName}</span>
                )}
                <span style={{ color: T.t2 }}>{metricsSuffix}</span>
              </>
            ) : (
              "Choose an organization to load usage metrics and charts."
            )}
          </p>
          {err && (
            <p
              style={{
                margin: "10px 0 0",
                fontSize: 12,
                color: T.red,
                maxWidth: 560,
                lineHeight: 1.45,
              }}
            >
              {err}
            </p>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Btn
            variant="ghost"
            disabled={!organizationId}
            onClick={
              onExportCsv ??
              (() => {
                if (summary?.top_queries?.length) downloadTopQueriesCsv(summary.top_queries);
              })
            }
          >
            Export CSV
          </Btn>
          <Btn variant="primary" disabled={!organizationId} onClick={onInviteTeam ?? (() => {})}>
            + Invite team
          </Btn>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 16,
          marginBottom: 20,
        }}
        className="org-dash-kpi-grid"
      >
        <KpiCard
          label="Queries this month"
          value={
            loading ? "…" : !organizationId || err ? "—" : String(summary?.totals.queries_this_month ?? 0)
          }
          delta="From query logs"
          deltaTone="neutral"
          sub="Calendar month (UTC)"
        />
        <KpiCard
          label="Active users (7d)"
          value={loading ? "…" : !organizationId || err ? "—" : String(summary?.totals.active_users_7d ?? 0)}
          delta="Distinct users with queries"
          deltaTone="neutral"
        />
        <KpiCard
          label="Documents indexed"
          value={
            loading ? "…" : !organizationId || err ? "—" : String(summary?.totals.documents_indexed ?? 0)
          }
          delta="Indexed in this organization"
          deltaTone="neutral"
        />
        <KpiCard
          label="Avg response time"
          value={
            loading
              ? "…"
              : !organizationId || err
                ? "—"
                : formatAvgResponse(summary?.totals.avg_response_time_ms ?? 0)
          }
          delta="From chat latency logs"
          deltaTone="neutral"
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 320px",
          gap: 16,
          marginBottom: 20,
          alignItems: "stretch",
        }}
        className="org-dash-charts-grid"
      >
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.cardBorder}`,
            borderRadius: 12,
            padding: "18px 12px 12px 12px",
            minHeight: 280,
          }}
        >
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: T.t1,
              paddingLeft: 12,
              marginBottom: 8,
            }}
          >
            Queries per day — last 30 days
          </div>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <XAxis
                  dataKey="label"
                  tick={{ fill: T.t3, fontSize: 9 }}
                  tickLine={false}
                  axisLine={{ stroke: T.cardBorder }}
                  interval="preserveStartEnd"
                />
                <YAxis hide domain={[0, "auto"]} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                  contentStyle={{
                    background: T.card,
                    border: `1px solid ${T.cardBorder}`,
                    borderRadius: 8,
                    fontSize: 12,
                    color: T.t1,
                  }}
                  labelFormatter={(label) => (label != null && label !== "" ? `Date ${label}` : "")}
                  formatter={(v: number) => [`${v}`, "Queries"]}
                />
                <Bar dataKey="q" radius={[3, 3, 0, 0]} maxBarSize={10}>
                  {chartData.map((entry, index) => (
                    <Cell
                      key={`c-${index}`}
                      fill={entry.highlight ? T.primary : T.barMuted}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {!loading && !organizationId && (
            <div style={{ padding: 12, fontSize: 12, color: T.t3 }}>Select an organization to load charts.</div>
          )}
          {!loading && organizationId && chartData.length === 0 && !err && (
            <div style={{ padding: 12, fontSize: 12, color: T.t3 }}>No query volume in the last 30 days yet.</div>
          )}
        </div>
        <ConfidenceBar
          segments={confidenceSegments}
          emptyHint={
            summary?.top_queries?.length
              ? undefined
              : "Top query samples will appear after users ask questions in chat."
          }
        />
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
        }}
        className="org-dash-tables-grid"
      >
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.cardBorder}`,
            borderRadius: 12,
            padding: "18px 20px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: T.t1 }}>
              Top queries this month
            </div>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
            <thead>
              <tr style={{ color: T.t3, textAlign: "left" }}>
                <th style={{ padding: "8px 0", fontWeight: 600 }}>QUERY</th>
                <th style={{ padding: "8px 0", fontWeight: 600, width: 72 }}>COUNT</th>
                <th style={{ padding: "8px 0", fontWeight: 600, width: 100 }}>CONFIDENCE</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={3} style={{ padding: "16px 0", color: T.t3 }}>
                    Loading…
                  </td>
                </tr>
              )}
              {!loading &&
                (summary?.top_queries ?? []).map((row, idx) => (
                  <tr
                    key={`${row.text}-${idx}`}
                    style={{ borderTop: `1px solid ${T.cardBorder}`, color: T.t2 }}
                  >
                    <td style={{ padding: "12px 8px 12px 0", color: T.t1 }}>{row.text}</td>
                    <td style={{ padding: "12px 8px 12px 0" }}>{row.frequency}</td>
                    <td style={{ padding: "12px 0" }}>
                      <ConfPill level={confidenceLevel(row.avg_confidence)} />
                    </td>
                  </tr>
                ))}
              {!loading && !err && (summary?.top_queries?.length ?? 0) === 0 && organizationId && (
                <tr>
                  <td colSpan={3} style={{ padding: "16px 0", color: T.t3 }}>
                    No queries recorded for this organization yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div
          style={{
            background: T.card,
            border: `1px solid ${T.cardBorder}`,
            borderRadius: 12,
            padding: "18px 20px",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: T.t1 }}>
              Knowledge gaps — unanswered
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {loading && (
              <div style={{ padding: "14px 0", color: T.t3, fontSize: 12 }}>Loading…</div>
            )}
            {!loading &&
              (summary?.unanswered_queries ?? []).map((g) => (
                <div
                  key={`${g.text}-${g.last_asked}`}
                  style={{
                    display: "flex",
                    gap: 12,
                    padding: "14px 0",
                    borderTop: `1px solid ${T.cardBorder}`,
                  }}
                >
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden
                    style={{ flexShrink: 0, marginTop: 2 }}
                  >
                    <path
                      d="M12 2L2 20h20L12 2z"
                      stroke={T.red}
                      strokeWidth="1.5"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M12 9v5M12 17h.01"
                      stroke={T.red}
                      strokeWidth="1.5"
                      strokeLinecap="round"
                    />
                  </svg>
                  <div>
                    <div style={{ fontSize: 13, color: T.t1, marginBottom: 4 }}>{g.text}</div>
                    <div style={{ fontSize: 11, color: T.t3 }}>
                      Low confidence or no evidence · Last: {g.last_asked}
                    </div>
                  </div>
                </div>
              ))}
            {!loading && !err && (summary?.unanswered_queries?.length ?? 0) === 0 && organizationId && (
              <div style={{ padding: "14px 0", fontSize: 12, color: T.t3 }}>
                No flagged knowledge gaps in recent logs.
              </div>
            )}
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 1200px) {
          .org-dash-kpi-grid { grid-template-columns: repeat(2, 1fr) !important; }
        }
        @media (max-width: 900px) {
          .org-dash-charts-grid { grid-template-columns: 1fr !important; }
          .org-dash-tables-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
