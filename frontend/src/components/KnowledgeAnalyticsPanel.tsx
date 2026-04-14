import { useMemo } from "react";
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

function useKnowledgePanelTokens(): KTokens {
  const ui = useOrgShellUiOptional();
  return ui?.brightMode ? T_BRIGHT : T_DARK;
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

function CoverageRow({
  area,
  value,
  color,
  pct,
}: {
  area: string;
  value: number;
  color: string;
  pct: string;
}) {
  const T = useKnowledgePanelTokens();
  return (
    <div style={{ display: "grid", gridTemplateColumns: "160px 1fr 48px", gap: 12, alignItems: "center" }}>
      <div style={{ color: T.muted, fontSize: 12 }}>{area}</div>
      <div style={{ height: 6, borderRadius: 100, background: T.trackMuted, overflow: "hidden" }}>
        <div style={{ width: `${value}%`, height: "100%", background: color }} />
      </div>
      <div style={{ color: T.muted, fontSize: 12, textAlign: "right" }}>{pct}</div>
    </div>
  );
}

export function KnowledgeAnalyticsPanel({
  workspaceName,
  organizationName,
}: {
  workspaceName?: string | null;
  organizationName?: string | null;
} = {}) {
  const T = useKnowledgePanelTokens();
  const rows = useMemo(
    () => [
      { area: "Vendor management", value: 88, color: T.green, pct: "88%" },
      { area: "HR & benefits", value: 82, color: T.green, pct: "82%" },
      { area: "IT compliance", value: 74, color: T.green, pct: "74%" },
      { area: "Contract mgmt", value: 54, color: T.yellow, pct: "54%" },
      { area: "Financial planning", value: 29, color: T.yellow, pct: "29%" },
      { area: "Legal & NDA", value: 22, color: T.red, pct: "22%" },
    ],
    [T.green, T.red, T.yellow],
  );

  const topQueries = [
    ["Vendor SLA policy for Tier1 incidents", "142"],
    ["Remote work benefit eligibility", "118"],
    ["IRQ contract modification process", "94"],
    ["Security incident response playbook", "87"],
    ["PTO accrual and carryover rules", "76"],
  ];

  const tags = useMemo(
    () =>
      [
        ["Vendor policy", T.blue],
        ["HR & benefits", T.green],
        ["Compliance", "#3b82f6"],
        ["Contracts", T.yellow],
        ["Security", "#4f46e5"],
        ["Engineering", "#0ea5e9"],
        ["Legal", "#10b981"],
        ["Finance", "#64748b"],
      ] as const,
    [T.blue, T.green, T.yellow],
  );

  return (
    <div style={{ background: T.bg, minHeight: "100%", padding: "20px 12px 20px 12px", fontFamily: T.sans }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
        <div>
          <div style={{ fontFamily: T.serif, color: T.text, fontSize: 30, lineHeight: 1.15 }}>Knowledge Analytics</div>
          <div style={{ color: T.muted, fontSize: 12 }}>
            {workspaceName ? (
              <>
                Metrics scoped to <span style={{ color: T.text, fontWeight: 600 }}>{workspaceName}</span>
                {organizationName ? ` · ${organizationName}` : ""}
              </>
            ) : (
              "What your team knows, what it does not, and what it asks most"
            )}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button type="button" style={{ background: T.card, border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            Last 30 days
          </button>
          <button type="button" style={{ background: "transparent", border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            Export
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginBottom: 10 }}>
        <StatCard label="Knowledge coverage" value="68%" note="queries answered with high confidence" />
        <StatCard label="Active knowledge areas" value="14" note="top clusters identified" />
        <StatCard label="Unanswered queries" value="10%" note="knowledge gaps to fill" valueColor={T.red} />
      </div>

      <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 14px", marginBottom: 10 }}>
        <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 }}>
          Topic coverage by area
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {rows.map((row) => (
            <CoverageRow key={row.area} area={row.area} value={row.value} color={row.color} pct={row.pct} />
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 14px" }}>
          <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
            Trending queries (last 7 days)
          </div>
          {topQueries.map(([q, c]) => (
            <div key={q} style={{ display: "grid", gridTemplateColumns: "1fr 56px", padding: "7px 0", borderTop: `1px solid ${T.line}`, alignItems: "center" }}>
              <div style={{ color: T.text, fontSize: 12 }}>{q}</div>
              <div style={{ color: T.text, fontSize: 13, textAlign: "right", fontWeight: 700 }}>{c}</div>
            </div>
          ))}
        </div>

        <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "12px 14px" }}>
          <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 8 }}>
            Knowledge topics
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {tags.map(([label, color]) => (
              <span key={label} style={{ fontSize: 11, color: "#fff", background: color, padding: "4px 8px", borderRadius: 999 }}>
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
