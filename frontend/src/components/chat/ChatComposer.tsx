import type { FormEvent, KeyboardEvent } from "react";

type Ws = { id: string; name: string; organization_id: string };

type Props = {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  workspaces: Ws[];
  workspaceId: string;
  onWorkspaceChange: (id: string) => void;
};

const estTokens = (s: string) => Math.max(1, Math.ceil(s.length / 4));

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  disabled,
  workspaces,
  workspaceId,
  onWorkspaceChange,
}: Props) {
  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && value.trim()) onSubmit();
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!disabled && value.trim()) onSubmit();
  }

  return (
    <div
      className="sk-panel"
      style={{
        marginTop: "auto",
        borderTop: "1px solid var(--border)",
        borderRadius: "12px 12px 0 0",
        position: "sticky",
        bottom: 0,
        background: "rgba(8, 12, 20, 0.92)",
        backdropFilter: "blur(8px)",
      }}
    >
      <form onSubmit={handleSubmit}>
        <div className="sk-row" style={{ marginBottom: "0.5rem", flexWrap: "wrap", gap: "0.75rem" }}>
          <label className="sk-label" style={{ margin: 0 }}>
            Workspace
            <select
              className="sk-input"
              style={{ marginTop: "0.25rem", minWidth: 200 }}
              value={workspaceId}
              onChange={(e) => onWorkspaceChange(e.target.value)}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </label>
          <span className="sk-muted" style={{ fontSize: "0.8rem", marginLeft: "auto" }}>
            {value.length} chars · ~{estTokens(value)} tokens
          </span>
        </div>
        <textarea
          className="sk-input"
          rows={3}
          style={{ resize: "vertical", minHeight: "4.5rem", maxHeight: "40vh" }}
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
        />
        <div className="sk-row" style={{ marginTop: "0.75rem" }}>
          <span className="sk-muted sk-mono" style={{ fontSize: "0.74rem" }}>
            Enter to send · Shift+Enter for newline
          </span>
          <button className="sk-btn" type="submit" disabled={disabled || !value.trim()}>
            {disabled ? "Thinking…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
