import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, apiErrorMessage } from "../api/client";
import { useOrgShellUiOptional } from "../context/OrgShellThemeContext";

const T_DARK = {
  bg: "#0b0f18",
  card: "#111826",
  border: "rgba(255,255,255,0.07)",
  text: "#ebf1ff",
  muted: "#8ea2c0",
  dim: "#4a5a75",
  line: "rgba(255,255,255,0.05)",
  trackMuted: "rgba(255,255,255,0.06)",
  green: "#20c997",
  yellow: "#f2b035",
  red: "#ef5350",
  blue: "#2563eb",
  sans: '"DM Sans",sans-serif',
  serif: '"Instrument Serif",Georgia,serif',
};

const T_BRIGHT = {
  bg: "#f4f6fb",
  card: "#ffffff",
  border: "rgba(15,23,42,0.1)",
  text: "#0f172a",
  muted: "#475569",
  dim: "#64748b",
  line: "rgba(15,23,42,0.08)",
  trackMuted: "rgba(15,23,42,0.08)",
  green: "#059669",
  yellow: "#b45309",
  red: "#dc2626",
  blue: "#2563eb",
  sans: '"DM Sans",sans-serif',
  serif: '"Instrument Serif",Georgia,serif',
};

type KTokens = typeof T_DARK;

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

function useKnowledgePanelTokens(): KTokens {
  const ui = useOrgShellUiOptional();
  return ui?.brightMode ? T_BRIGHT : T_DARK;
}

function confColor(c: number, T: KTokens): string {
  if (c >= 0.65) return T.green;
  if (c >= 0.4) return T.yellow;
  return T.red;
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
  a.download = "knowledge-analytics-top-queries.csv";
  a.click();
  URL.revokeObjectURL(url);
}

function StatCard({
  label,
  value,
  note,
  valueColor,
}: {
  label: string;
  value: string;
  note: string;
  valueColor?: string;
}) {
  const T = useKnowledgePanelTokens();
  const vc = valueColor ?? T.text;
  return (
    <div
      style={{
        background: T.card,
        border: `1px solid ${T.border}`,
        borderRadius: 10,
        padding: "14px 16px",
      }}
    >
      <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", color: T.dim, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontFamily: T.serif, fontSize: 30, color: vc, lineHeight: 1.1 }}>{value}</div>
      <div style={{ marginTop: 6, color: T.muted, fontSize: 12 }}>{note}</div>
    </div>
  );
}

/** Matches original static layout: fixed label column + bar + percent. */
function CoverageRow({
  area,
  fullTitle,
  value,
  color,
  pct,
}: {
  area: string;
  fullTitle: string;
  value: number;
  color: string;
  pct: string;
}) {
  const T = useKnowledgePanelTokens();
  return (
    <div style={{ display: "grid", gridTemplateColumns: "160px 1fr 48px", gap: 12, alignItems: "center" }}>
      <div
        style={{
          color: T.muted,
          fontSize: 12,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
        title={fullTitle}
      >
        {area}
      </div>
      <div style={{ height: 6, borderRadius: 100, background: T.trackMuted, overflow: "hidden", minWidth: 0 }}>
        <div style={{ width: `${value}%`, height: "100%", background: color }} />
      </div>
      <div style={{ color: T.muted, fontSize: 12, textAlign: "right" }}>{pct}</div>
    </div>
  );
}

export function KnowledgeAnalyticsPanel({
  workspaceName,
  organizationName,
  organizationId,
}: {
  workspaceName?: string | null;
  organizationName?: string | null;
  organizationId?: string | null;
} = {}) {
  const T = useKnowledgePanelTokens();
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
      const { data } = await api.get<Summary>("/metrics/summary", {
        params: { organization_id: organizationId },
      });
      setSummary(data);
    } catch (e) {
      setErr(apiErrorMessage(e));
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const weightedHighCoveragePct = useMemo(() => {
    const rows = summary?.top_queries ?? [];
    if (!rows.length) return 0;
    let w = 0;
    let hi = 0;
    for (const r of rows) {
      w += r.frequency;
      if (r.avg_confidence >= 0.65) hi += r.frequency;
    }
    return w ? Math.round((100 * hi) / w) : 0;
  }, [summary]);

  const gapSignalPct = useMemo(() => {
    const q = summary?.totals.queries_this_month ?? 0;
    const u = summary?.unanswered_queries?.length ?? 0;
    if (!q) return u ? 100 : 0;
    return Math.min(100, Math.round((100 * u) / q));
  }, [summary]);

  /** Up to 6 rows like the original mock; bar = relative volume; pct = confidence as % for display */
  const coverageRows = useMemo(() => {
    const rows = summary?.top_queries ?? [];
    const maxF = Math.max(1, ...rows.map((r) => r.frequency));
    return rows.slice(0, 6).map((r) => {
      const full = r.text || "(empty)";
      const short = full.length > 36 ? `${full.slice(0, 36)}…` : full;
      const widthPct = Math.max(6, Math.round((100 * r.frequency) / maxF));
      return {
        area: short,
        fullTitle: full,
        value: widthPct,
        color: confColor(r.avg_confidence, T),
        pct: `${r.frequency}`,
      };
    });
  }, [summary, T]);

  const chartData = useMemo(() => {
    const rows = summary?.queries_per_day ?? [];
    const tail = rows.slice(-14);
    return tail.map((d, i) => ({
      label: d.date.length >= 10 ? d.date.slice(5, 10) : d.date,
      q: d.count,
      highlight: i === tail.length - 1,
    }));
  }, [summary]);

  const trending = summary?.top_queries?.slice(0, 5) ?? [];

  const topicTags = useMemo(() => {
    return (summary?.top_queries ?? []).slice(0, 8).map((q) => {
      const t = q.text || "";
      const label = t.length > 28 ? `${t.slice(0, 28)}…` : t;
      return { label, color: confColor(q.avg_confidence, T) };
    });
  }, [summary, T]);

  const hasOrg = Boolean(organizationId);
  const activeThemes = summary?.top_queries?.length ?? 0;

  return (
    <div style={{ background: T.bg, minHeight: "100%", padding: "20px 12px 20px 12px", fontFamily: T.sans }}>
      {/* —— Header (same structure as static: title + subtitle + two header buttons) —— */}
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
        <div>
          <div style={{ fontFamily: T.serif, color: T.text, fontSize: 30, lineHeight: 1.15 }}>Knowledge Analytics</div>
          <div style={{ color: T.muted, fontSize: 12, marginTop: 4, maxWidth: 560 }}>
            {hasOrg ? (
              workspaceName ? (
                <>
                  Metrics scoped to <span style={{ color: T.text, fontWeight: 600 }}>{workspaceName}</span>
                  {organizationName ? ` · ${organizationName}` : ""}
                  <span style={{ display: "block", marginTop: 4, fontSize: 11, opacity: 0.9 }}>
                    Live data: org-wide query logs & indexed documents.
                  </span>
                </>
              ) : (
                <>
                  What your team asks, how confidently it is answered, and where knowledge gaps show up
                  {organizationName ? ` — ${organizationName}` : ""}.
                </>
              )
            ) : (
              "Select an organization in the context bar to load metrics."
            )}
          </div>
          {err && (
            <p style={{ margin: "10px 0 0", fontSize: 12, color: T.red, maxWidth: 560, lineHeight: 1.45 }}>{err}</p>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
          <button
            type="button"
            style={{
              background: T.card,
              border: `1px solid ${T.border}`,
              color: T.text,
              borderRadius: 8,
              padding: "8px 10px",
              fontSize: 12,
              cursor: "default",
              fontFamily: T.sans,
            }}
          >
            Last 30 days
          </button>
          <button
            type="button"
            disabled={!summary?.top_queries?.length}
            onClick={() => summary?.top_queries?.length && downloadTopQueriesCsv(summary.top_queries)}
            style={{
              background: "transparent",
              border: `1px solid ${T.border}`,
              color: T.text,
              borderRadius: 8,
              padding: "8px 10px",
              fontSize: 12,
              fontFamily: T.sans,
              cursor: summary?.top_queries?.length ? "pointer" : "not-allowed",
              opacity: summary?.top_queries?.length ? 1 : 0.45,
            }}
          >
            Export
          </button>
        </div>
      </div>

      {!hasOrg ? (
        <div
          style={{
            background: T.card,
            border: `1px solid ${T.border}`,
            borderRadius: 10,
            padding: "28px 20px",
            color: T.muted,
            fontSize: 13,
            textAlign: "center",
          }}
        >
          Choose an organization from the platform context bar or Organizations menu to view analytics.
        </div>
      ) : (
        <>
          {/* —— Three KPIs (original labels; values from API) —— */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 10 }}>
            <StatCard
              label="Knowledge coverage"
              value={loading ? "…" : `${weightedHighCoveragePct}%`}
              note="queries answered with high confidence (weighted by volume)"
            />
            <StatCard
              label="Active knowledge areas"
              value={loading ? "…" : String(activeThemes)}
              note="top clusters identified (recurring question themes)"
            />
            <StatCard
              label="Unanswered queries"
              value={loading ? "…" : `${gapSignalPct}%`}
              note="knowledge gaps to fill (gap signals vs. monthly queries)"
              valueColor={gapSignalPct > 25 ? T.red : T.text}
            />
          </div>

          {/* —— Topic coverage (same card + rows layout as static) —— */}
          <div
            style={{
              background: T.card,
              border: `1px solid ${T.border}`,
              borderRadius: 10,
              padding: "12px 14px",
              marginBottom: 10,
            }}
          >
            <div
              style={{
                color: T.dim,
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: 10,
              }}
            >
              Topic coverage by area
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {loading ? (
                <div style={{ color: T.muted, fontSize: 12 }}>Loading…</div>
              ) : coverageRows.length === 0 ? (
                <div style={{ color: T.muted, fontSize: 12 }}>
                  No query themes yet — use chat or document search to build history.
                </div>
              ) : (
                coverageRows.map((row) => (
                  <CoverageRow
                    key={row.fullTitle}
                    area={row.area}
                    fullTitle={row.fullTitle}
                    value={row.value}
                    color={row.color}
                    pct={row.pct}
                  />
                ))
              )}
            </div>
          </div>

          {/* —— Two columns: trending + tags (original grid) —— */}
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10, marginBottom: 10 }}>
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 14px" }}>
              <div
                style={{
                  color: T.dim,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: 8,
                }}
              >
                Trending queries (last 7 days)
              </div>
              <div style={{ fontSize: 10, color: T.muted, marginBottom: 6 }}>
                Ranked by frequency in your org (rolling data from query logs).
              </div>
              {loading ? (
                <div style={{ color: T.muted, fontSize: 12 }}>Loading…</div>
              ) : trending.length === 0 ? (
                <div style={{ color: T.muted, fontSize: 12 }}>No queries yet.</div>
              ) : (
                trending.map((row) => (
                  <div
                    key={row.text}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 56px",
                      padding: "7px 0",
                      borderTop: `1px solid ${T.line}`,
                      alignItems: "center",
                    }}
                  >
                    <div style={{ color: T.text, fontSize: 12 }}>{row.text}</div>
                    <div style={{ color: T.text, fontSize: 13, textAlign: "right", fontWeight: 700 }}>
                      {row.frequency}
                    </div>
                  </div>
                ))
              )}
            </div>

            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 14px" }}>
              <div
                style={{
                  color: T.dim,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  marginBottom: 8,
                }}
              >
                Knowledge topics
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {loading ? (
                  <span style={{ color: T.muted, fontSize: 12 }}>…</span>
                ) : topicTags.length === 0 ? (
                  <span style={{ color: T.muted, fontSize: 12 }}>Topics appear from your questions.</span>
                ) : (
                  topicTags.map((tag, i) => (
                    <span
                      key={`${i}-${tag.label}`}
                      style={{
                        fontSize: 11,
                        color: "#fff",
                        background: tag.color,
                        padding: "4px 8px",
                        borderRadius: 999,
                      }}
                    >
                      {tag.label}
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* —— Extra: 30-day volume (not in original static; kept below so layout above matches the mock) —— */}
          <div
            style={{
              background: T.card,
              border: `1px solid ${T.border}`,
              borderRadius: 10,
              padding: "12px 14px",
            }}
          >
            <div
              style={{
                color: T.dim,
                fontSize: 10,
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: 10,
              }}
            >
              Query volume — last 14 days
            </div>
            <div style={{ width: "100%", height: 180 }}>
              {loading ? (
                <div style={{ color: T.muted, fontSize: 12, padding: 16 }}>Loading…</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <XAxis
                      dataKey="label"
                      tick={{ fill: T.dim, fontSize: 9 }}
                      tickLine={false}
                      axisLine={{ stroke: T.border }}
                    />
                    <YAxis hide domain={[0, "auto"]} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.04)" }}
                      contentStyle={{
                        background: T.card,
                        border: `1px solid ${T.border}`,
                        borderRadius: 8,
                        fontSize: 12,
                        color: T.text,
                      }}
                      formatter={(v: number) => [`${v}`, "Queries"]}
                    />
                    <Bar dataKey="q" radius={[3, 3, 0, 0]} maxBarSize={12}>
                      {chartData.map((entry, index) => (
                        <Cell key={`c-${index}`} fill={entry.highlight ? T.blue : T.trackMuted} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
