import { useEffect, useRef, useState } from "react";
import { useOrgShellTokens } from "../../context/OrgShellThemeContext";

type Org = {
  id: string;
  name: string;
};

type Workspace = {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
};

export function WorkspaceSelect({
  workspaces,
  orgs,
  selectedId,
  onSelect,
}: {
  workspaces: Workspace[];
  orgs: Org[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const selected = workspaces.find((w) => w.id === selectedId) ?? workspaces[0];

  const filtered = query.trim()
    ? workspaces.filter((w) => {
        const org = orgs.find((o) => o.id === w.organization_id);
        const q = query.toLowerCase();
        return (
          w.name.toLowerCase().includes(q) ||
          (w.description ?? "").toLowerCase().includes(q) ||
          (org?.name ?? "").toLowerCase().includes(q)
        );
      })
    : workspaces;

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (open) setTimeout(() => searchRef.current?.focus(), 50);
    else setQuery("");
  }, [open]);

  if (!selected) return null;

  const selOrg = orgs.find((o) => o.id === selected.organization_id);

  return (
    <div ref={ref} style={{ position: "relative", width: "100%" }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 12,
          padding: "13px 16px", background: C.bgCard,
          border: `1px solid ${open ? "rgba(37,99,235,0.5)" : C.bd2}`,
          borderRadius: open ? "12px 12px 0 0" : 12,
          cursor: "pointer", fontFamily: C.sans,
          boxShadow: open ? `0 0 0 3px rgba(37,99,235,0.1)` : "none",
          transition: "all .15s",
        }}
      >
        <div style={{
          width: 38, height: 38, borderRadius: 9, flexShrink: 0,
          background: "linear-gradient(135deg,rgba(37,99,235,0.35),rgba(139,92,246,0.35))",
          border: "1px solid rgba(37,99,235,0.35)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, fontWeight: 700, color: "#93c5fd",
        }}>
          {selected.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
        </div>
        <div style={{ flex: 1, textAlign: "left" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 2 }}>
            {selected.name}
          </div>
          <div style={{ fontSize: 10, color: C.t3, fontFamily: C.mono }}>
            {selOrg?.name ?? "Organization"} · {selected.id.slice(0, 8)}…
          </div>
        </div>
        <svg viewBox="0 0 16 16" width="14" height="14" style={{
          fill: C.t3, flexShrink: 0,
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform .15s",
        }}>
          <path d="M8 10.5L2.5 5h11L8 10.5z" />
        </svg>
      </button>

      {open && (
        <div style={{
          position: "absolute", left: 0, right: 0, zIndex: 100,
          background: C.bgCard, border: `1px solid rgba(37,99,235,0.3)`,
          borderTop: "none", borderRadius: "0 0 12px 12px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        }}>
          <div style={{ padding: "10px 12px", borderBottom: `1px solid ${C.bd}` }}>
            <div style={{ position: "relative" }}>
              <svg viewBox="0 0 16 16" width="13" height="13" style={{
                position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)",
                fill: "none", stroke: C.t3, strokeWidth: 1.5, strokeLinecap: "round",
              }}>
                <circle cx="6.5" cy="6.5" r="4" />
                <path d="M10 10l3 3" />
              </svg>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search workspaces…"
                style={{
                  width: "100%", padding: "7px 10px 7px 30px",
                  background: C.bgE, border: `1px solid ${C.bd}`, borderRadius: 7,
                  fontSize: 12, color: C.t1, fontFamily: C.sans, outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
          <div style={{ maxHeight: 260, overflowY: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: C.t3 }}>
                No workspaces match "{query}"
              </div>
            ) : (
              filtered.map((ws, i) => {
                const org = orgs.find((o) => o.id === ws.organization_id);
                return (
                  <button
                    key={ws.id}
                    type="button"
                    onClick={() => { onSelect(ws.id); setOpen(false); setQuery(""); }}
                    style={{
                      width: "100%", display: "flex", alignItems: "center", gap: 10,
                      padding: "11px 16px",
                      background: ws.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent",
                      borderBottom: i < filtered.length - 1 ? `1px solid ${C.bd}` : "none",
                      border: "none", cursor: "pointer", fontFamily: C.sans, transition: "background .1s",
                    }}
                    onMouseEnter={(e) => { if (ws.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = C.rowHover; }}
                    onMouseLeave={(e) => { if (ws.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = ws.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent"; }}
                  >
                    <div style={{
                      width: 30, height: 30, borderRadius: 7, flexShrink: 0,
                      background: "rgba(37,99,235,0.18)", border: "1px solid rgba(37,99,235,0.25)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 10, fontWeight: 700, color: "#93c5fd",
                    }}>
                      {ws.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, textAlign: "left", minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: ws.id === selectedId ? 600 : 500, color: C.t1 }}>
                        {ws.name}
                      </div>
                      <div style={{ fontSize: 10, color: C.t3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {org?.name ?? "—"}
                      </div>
                    </div>
                    {ws.id === selectedId && (
                      <svg viewBox="0 0 16 16" width="12" height="12" style={{ fill: "none", flexShrink: 0 }}>
                        <path d="M3 8l3.5 3.5 6.5-7" stroke={C.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
