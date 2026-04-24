import type { Citation } from "../../lib/chatSse";

type Props = {
  citations: Citation[];
  selected: Citation | null;
  onSelect: (c: Citation) => void;
  /** Close control when panel is used as a slide-over drawer. */
  onClose?: () => void;
  /**
   * Answer-level confidence (high | medium | low) — same signal as the assistant footer.
   * When set, the header pill uses this; retrieval scores are shown as a secondary line.
   */
  answerConfidence?: string | null;
  variant?: "drawer" | "dock";
  /** Pin the panel to the layout (drawer mode only). */
  onPin?: () => void;
  /** Return to overlay drawer layout (dock mode only). */
  onUnpin?: () => void;
};

function tierFromBestScore(best: number): "High" | "Medium" | "Low" {
  if (best >= 0.75) return "High";
  if (best >= 0.55) return "Medium";
  return "Low";
}

function pillClassForTier(label: "High" | "Medium" | "Low") {
  if (label === "High") return "skc-pill skc-pill-ok";
  if (label === "Medium") return "skc-pill skc-pill-med";
  return "skc-pill skc-pill-low";
}

export function ChatSourcesPanel({
  citations,
  selected,
  onSelect,
  onClose,
  answerConfidence,
  variant = "drawer",
  onPin,
  onUnpin,
}: Props) {
  const best = citations.length > 0 ? Math.max(...citations.map((c) => c.score || 0)) : 0;
  const retrievalTier = citations.length > 0 ? tierFromBestScore(best) : null;
  const ac = answerConfidence?.trim().toLowerCase() ?? "";
  const answerIsHml = ac === "high" || ac === "medium" || ac === "low";
  const answerTierLabel: "High" | "Medium" | "Low" | null = answerIsHml
    ? ((ac.charAt(0).toUpperCase() + ac.slice(1)) as "High" | "Medium" | "Low")
    : null;

  const primaryTier = answerTierLabel ?? retrievalTier;
  const showRetrievalHint =
    Boolean(answerTierLabel && retrievalTier && citations.length > 0) && answerTierLabel !== retrievalTier;

  return (
    <aside className="skc-sources">
      <div className="skc-sources-header">
        <div className="skc-sources-header-titles">
          <h3 style={{ fontSize: "0.85rem" }}>Sources · {citations.length} cited</h3>
          <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
            {primaryTier ? (
              <span
                className={pillClassForTier(primaryTier)}
                title={answerTierLabel ? "Answer confidence (matches chat footer)" : "Retrieval match strength (best chunk)"}
              >
                {primaryTier}
              </span>
            ) : (
              <span className="skc-pill" style={{ fontSize: "0.65rem", opacity: 0.75 }}>
                —
              </span>
            )}
          </div>
          {showRetrievalHint && retrievalTier && (
            <span className="skc-sources-match-hint">
              Retrieval only: {retrievalTier} (best chunk {Math.round(best * 100)}%) — can differ from answer confidence
            </span>
          )}
        </div>
        <div className="skc-sources-header-actions">
          {variant === "drawer" && onPin && (
            <button
              type="button"
              className="skc-sources-pin-btn"
              onClick={onPin}
              aria-label="Pin sources panel to the side"
              title="Pin panel"
            >
              📌
            </button>
          )}
          {variant === "dock" && onUnpin && (
            <button
              type="button"
              className="skc-sources-pin-btn"
              onClick={onUnpin}
              aria-pressed
              aria-label="Unpin sources panel"
              title="Unpin panel"
            >
              ⊟
            </button>
          )}
          {variant === "drawer" && onClose && (
            <button type="button" className="skc-sources-close" onClick={onClose} aria-label="Close sources panel">
              ×
            </button>
          )}
        </div>
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
