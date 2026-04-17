import { useEffect, useRef, useState } from "react";
import { useOrgShellTokens } from "../../context/OrgShellThemeContext";

type Org = {
  id: string;
  name: string;
  slug: string;
  status: string;
};

export function OrganizationSelect({
  orgs,
  selectedId,
  onSelect,
  allowEmpty,
  showBackToPlatform,
  onBackToPlatform,
}: {
  orgs: Org[];
  selectedId: string;
  onSelect: (id: string) => void;
  allowEmpty?: boolean;
  showBackToPlatform?: boolean;
  onBackToPlatform?: () => void;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const selected = selectedId ? orgs.find((o) => o.id === selectedId) : allowEmpty ? undefined : orgs[0];

  const filtered = query.trim()
    ? orgs.filter((o) =>
        o.name.toLowerCase().includes(query.toLowerCase()) ||
        o.slug.toLowerCase().includes(query.toLowerCase()),
      )
    : orgs;

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

  if (!orgs.length) return null;
  if (!selected && !allowEmpty) return null;

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
          background: selected
            ? "linear-gradient(135deg,rgba(37,99,235,0.35),rgba(139,92,246,0.35))"
            : "rgba(148,163,184,0.15)",
          border: `1px solid ${selected ? "rgba(37,99,235,0.35)" : C.bd}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 16, fontWeight: 700, color: selected ? "#93c5fd" : C.t3,
        }}>
          {selected ? selected.name.slice(0, 2).toUpperCase() : "?"}
        </div>
        <div style={{ flex: 1, textAlign: "left" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.t1, marginBottom: 2 }}>
            {selected ? selected.name : "Select organization…"}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {selected ? (
              <>
                <span style={{ fontSize: 10, color: C.t3, fontFamily: C.mono }}>/{selected.slug}</span>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 3,
                  padding: "1px 6px", borderRadius: 100, fontSize: 9, fontWeight: 700,
                  background: selected.status === "active" ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.12)",
                  color: selected.status === "active" ? C.green : C.gold,
                  border: `1px solid ${selected.status === "active" ? "rgba(16,185,129,0.25)" : "rgba(245,158,11,0.25)"}`,
                  fontFamily: C.sans,
                }}>
                  <span style={{ width: 4, height: 4, borderRadius: "50%", background: "currentColor", display: "inline-block" }} />
                  {selected.status}
                </span>
              </>
            ) : (
              <span style={{ fontSize: 10, color: C.t3 }}>Choose an org to manage details</span>
            )}
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
                placeholder="Search organizations…"
                style={{
                  width: "100%", padding: "7px 10px 7px 30px",
                  background: C.bgE, border: `1px solid ${C.bd}`, borderRadius: 7,
                  fontSize: 12, color: C.t1, fontFamily: C.sans, outline: "none",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
          {showBackToPlatform && onBackToPlatform && (
            <div style={{ padding: "8px 12px", borderBottom: `1px solid ${C.bd}` }}>
              <button
                type="button"
                onClick={() => {
                  onBackToPlatform();
                  setOpen(false);
                  setQuery("");
                }}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 12px", borderRadius: 8, border: `1px solid rgba(37,99,235,0.25)`,
                  background: "rgba(37,99,235,0.08)", cursor: "pointer", fontFamily: C.sans,
                  textAlign: "left", transition: "background .12s",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(37,99,235,0.14)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(37,99,235,0.08)";
                }}
              >
                <span style={{ fontSize: 16, lineHeight: 1 }} aria-hidden>🌐</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: C.t1 }}>Platform-wide view</div>
                  <div style={{ fontSize: 10, color: C.t3, marginTop: 2 }}>Leave org context · overview all organizations</div>
                </div>
              </button>
            </div>
          )}
          <div style={{ maxHeight: 240, overflowY: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: C.t3 }}>
                No organizations match "{query}"
              </div>
            ) : (
              filtered.map((org, i) => (
                <button
                  key={org.id}
                  type="button"
                  onClick={() => { onSelect(org.id); setOpen(false); setQuery(""); }}
                  style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 10,
                    padding: "11px 16px",
                    background: org.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent",
                    borderBottom: i < filtered.length - 1 ? `1px solid ${C.bd}` : "none",
                    border: "none", cursor: "pointer", fontFamily: C.sans, transition: "background .1s",
                  }}
                  onMouseEnter={(e) => { if (org.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = C.rowHover; }}
                  onMouseLeave={(e) => { if (org.id !== selectedId) (e.currentTarget as HTMLButtonElement).style.background = org.id === selectedId ? "rgba(37,99,235,0.1)" : "transparent"; }}
                >
                  <div style={{
                    width: 30, height: 30, borderRadius: 7, flexShrink: 0,
                    background: "rgba(37,99,235,0.18)", border: "1px solid rgba(37,99,235,0.25)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 700, color: "#93c5fd",
                  }}>
                    {org.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div style={{ flex: 1, textAlign: "left" }}>
                    <div style={{ fontSize: 12, fontWeight: org.id === selectedId ? 600 : 500, color: C.t1 }}>
                      {org.name}
                    </div>
                    <div style={{ fontSize: 10, color: C.t3, fontFamily: C.mono }}>/{org.slug}</div>
                  </div>
                  {org.id === selectedId && (
                    <svg viewBox="0 0 16 16" width="12" height="12" style={{ fill: "none", flexShrink: 0 }}>
                      <path d="M3 8l3.5 3.5 6.5-7" stroke={C.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
