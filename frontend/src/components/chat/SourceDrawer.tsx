import type { Citation } from "../../lib/chatSse";

type Props = {
  open: boolean;
  onClose: () => void;
  citation: Citation | null;
};

export function SourceDrawer({ open, onClose, citation }: Props) {
  if (!open) return null;

  return (
    <>
      <button
        type="button"
        aria-label="Close sources"
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.45)",
          border: "none",
          zIndex: 40,
        }}
      />
      <aside
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          height: "100%",
          width: "min(400px, 100vw)",
          background: "var(--surface)",
          borderLeft: "1px solid var(--border)",
          zIndex: 50,
          padding: "1.25rem",
          overflow: "auto",
          boxShadow: "-8px 0 24px rgba(0,0,0,0.35)",
        }}
      >
        <div className="sk-row" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>Source</h3>
          <button type="button" className="sk-btn secondary" onClick={onClose}>
            Close
          </button>
        </div>
        {citation ? (
          <>
            <p style={{ fontWeight: 700, marginTop: 0 }}>{citation.document_filename}</p>
            <p className="sk-muted" style={{ fontSize: "0.85rem" }}>
              {citation.page_number != null ? `Page ${citation.page_number}` : "Page n/a"} · score {(citation.score ?? 0).toFixed(3)}
            </p>
            <div
              style={{
                marginTop: "1rem",
                padding: "0.75rem",
                borderRadius: 8,
                background: "var(--surface2)",
                borderLeft: "3px solid var(--accent)",
                whiteSpace: "pre-wrap",
                fontSize: "0.9rem",
              }}
            >
              {citation.quote}
            </div>
            <p className="sk-muted" style={{ marginTop: "1rem", fontSize: "0.8rem" }}>
              Open original: use document APIs when file links are exposed.
            </p>
            <div style={{ marginTop: "0.75rem", height: 6, borderRadius: 4, background: "var(--surface2)" }}>
              <div
                style={{
                  width: `${Math.min(100, (citation.score ?? 0) * 100)}%`,
                  height: "100%",
                  borderRadius: 4,
                  background: "linear-gradient(90deg, var(--accent), var(--ok))",
                }}
              />
            </div>
          </>
        ) : (
          <p className="sk-muted">Select a citation pill to inspect the passage.</p>
        )}
      </aside>
    </>
  );
}
