import type { Citation } from "../../lib/chatSse";

type Props = {
  citations: Citation[];
  selected: Citation | null;
  onSelect: (c: Citation) => void;
};

export function ChatSourcesPanel({ citations, selected, onSelect }: Props) {
  const best = citations.length > 0 ? Math.max(...citations.map((c) => c.score || 0)) : 0;
  const conf = best >= 0.75 ? "High" : best >= 0.55 ? "Medium" : "Low";
  return (
    <aside className="skc-sources">
      <div className="skc-sources-header">
        <h3 style={{ margin: 0, fontSize: "0.85rem" }}>Sources · {citations.length} cited</h3>
        <span className={`skc-pill ${conf === "High" ? "skc-pill-ok" : conf === "Medium" ? "skc-pill-med" : "skc-pill-low"}`}>{conf}</span>
      </div>
      <div className="skc-sources-list">
        {citations.length === 0 && <p className="sk-muted">Send a question to see grounded sources.</p>}
        {citations.map((c, i) => {
          const active = selected?.chunk_id === c.chunk_id;
          return (
            <button
              key={`${c.chunk_id}-${i}`}
              type="button"
              onClick={() => onSelect(c)}
              className={`skc-source-card ${active ? "on" : ""}`}
            >
              <div className="skc-source-head">
                <div className="skc-source-icon">📄</div>
                <div>
                  <div className="skc-source-name">{c.document_filename}</div>
                  <div className="skc-source-loc">
                    Page {c.page_number ?? "n/a"} · chunk {c.chunk_index}
                  </div>
                </div>
              </div>
              <div className="skc-source-excerpt">
                {c.quote.slice(0, 160)}
                {c.quote.length > 160 ? "…" : ""}
              </div>
              <div className="skc-source-score">
                <div className="skc-source-score-track">
                  <div className="skc-source-score-fill" style={{ width: `${Math.max(1, Math.min(100, c.score * 100))}%` }} />
                </div>
                <span className="skc-source-score-label">{Math.round(c.score * 100)}%</span>
              </div>
            </button>
          );
        })}
      </div>
      {selected && (
        <div style={{ padding: "0.85rem 0.95rem", borderTop: "1px solid var(--border)" }}>
          <div className="sk-label">Selected quote</div>
          <div
            style={{
              borderLeft: "3px solid var(--accent)",
              padding: "0.5rem 0.6rem",
              background: "var(--surface2)",
              borderRadius: "0 8px 8px 0",
              fontSize: "0.86rem",
              whiteSpace: "pre-wrap",
            }}
          >
            {selected.quote}
          </div>
        </div>
      )}
    </aside>
  );
}
