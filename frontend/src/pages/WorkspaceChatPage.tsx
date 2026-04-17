import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";

type ChatSession = {
  id: string;
  workspace_id: string;
  title: string | null;
  created_at: string;
};

type ChatMessage = {
  id: string;
  role: string;
  content: string;
  citations: {
    chunk_id: string;
    document_id: string;
    document_filename: string;
    chunk_index: number;
    page_number: number | null;
    score: number;
    quote: string;
  }[];
};

type SessionDetail = {
  session: ChatSession;
  messages: ChatMessage[];
};

export function WorkspaceChatPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [question, setQuestion] = useState("");
  const [uploading, setUploading] = useState(false);
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function loadSessions() {
    if (!workspaceId) return;
    const { data } = await api.get<ChatSession[]>(`/chat/workspaces/${workspaceId}/sessions`);
    setSessions(data);
  }

  useEffect(() => {
    if (!workspaceId) return;
    loadSessions().catch((ex) => setErr(apiErrorMessage(ex)));
  }, [workspaceId]);

  useEffect(() => {
    if (!activeId) {
      setDetail(null);
      return;
    }
    (async () => {
      const { data } = await api.get<SessionDetail>(`/chat/sessions/${activeId}`);
      setDetail(data);
    })().catch((ex) => setErr(apiErrorMessage(ex)));
  }, [activeId]);

  async function newSession() {
    if (!workspaceId) return;
    setErr(null);
    const { data } = await api.post<ChatSession>(`/chat/workspaces/${workspaceId}/sessions`, { title: "Conversation" });
    setActiveId(data.id);
    await loadSessions();
  }

  async function onUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!workspaceId) return;
    const form = e.currentTarget;
    const file = (form.elements.namedItem("file") as HTMLInputElement)?.files?.[0];
    if (!file) return;
    setUploading(true);
    setErr(null);
    try {
      const body = new FormData();
      body.append("file", file);
      await api.post(`/documents/workspaces/${workspaceId}/upload`, body);
      form.reset();
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setUploading(false);
    }
  }

  async function sendMessage(e: FormEvent) {
    e.preventDefault();
    if (!activeId || !question.trim()) return;
    setSending(true);
    setErr(null);
    try {
      await api.post(`/chat/sessions/${activeId}/messages`, { content: question.trim(), top_k: 5 });
      setQuestion("");
      const { data } = await api.get<SessionDetail>(`/chat/sessions/${activeId}`);
      setDetail(data);
      await loadSessions();
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setSending(false);
    }
  }

  if (!workspaceId) {
    return <p className="sk-error">Missing workspace</p>;
  }

  return (
    <div className="sk-layout">
      <aside className="sk-nav">
        <Link to="/organizations">← Organizations</Link>
        <h2 style={{ fontSize: "1rem", margin: "1rem 0 0.5rem" }}>Sessions</h2>
        <button type="button" className="sk-btn" style={{ width: "100%", marginBottom: "0.75rem" }} onClick={() => newSession().catch((ex) => setErr(apiErrorMessage(ex)))}>
          New chat
        </button>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {sessions.map((s) => (
            <li key={s.id} style={{ marginBottom: "0.35rem" }}>
              <button
                type="button"
                onClick={() => setActiveId(s.id)}
                className="sk-btn secondary"
                style={{
                  width: "100%",
                  textAlign: "left",
                  fontWeight: activeId === s.id ? 700 : 500,
                  borderColor: activeId === s.id ? "var(--accent)" : undefined,
                }}
              >
                {s.title || "Chat"}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <main className="sk-main">
        <header className="sk-page-header">
          <h2 style={{ margin: 0 }}>Workspace Chat</h2>
          <p className="sk-muted sk-mono" style={{ margin: 0 }}>
            {workspaceId}
          </p>
        </header>

        <div className="sk-panel sk-spaced">
          <h3 style={{ marginTop: 0 }}>Upload document</h3>
          <form onSubmit={onUpload} className="sk-row">
            <input
              type="file"
              name="file"
              accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm,.pptx,.xlsx,.xls,.csv,.rtf,.eml,.msg,.epub,.mobi,.png,.jpg,.jpeg,.webp,.tif,.tiff"
              required
            />
            <button className="sk-btn secondary" type="submit" disabled={uploading}>
              {uploading ? "Uploading…" : "Upload"}
            </button>
          </form>
        </div>

        {err && <p className="sk-error">{err}</p>}

        {!activeId && <p className="sk-muted">Select or create a chat session.</p>}

        {detail && (
          <>
            <div className="sk-chat-log sk-spaced">
              {detail.messages.map((m) => (
                <div key={m.id} className={`sk-panel ${m.role === "user" ? "sk-user-msg" : ""}`}>
                  <div className="sk-label">{m.role === "user" ? "You" : "Assistant"}</div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                  {m.role === "assistant" && m.citations.length > 0 && (
                    <div style={{ marginTop: "0.75rem" }}>
                      <div className="sk-label">Citations</div>
                      {m.citations.map((c, i) => (
                        <div key={`${c.chunk_id}-${i}`} className="citation">
                          <span className="sk-mono">
                            [{i + 1}] {c.document_filename}
                            {c.page_number != null ? ` p.${c.page_number}` : ""} (score {c.score.toFixed(3)})
                          </span>
                          <div style={{ marginTop: "0.35rem" }}>{c.quote}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
            <form onSubmit={sendMessage} className="sk-panel">
              <label className="sk-label">Ask a question</label>
              <textarea className="sk-input" rows={3} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask about the uploaded documents..." required />
              <button className="sk-btn" type="submit" disabled={sending} style={{ marginTop: "0.75rem" }}>
                {sending ? "Sending…" : "Send"}
              </button>
            </form>
          </>
        )}
      </main>
    </div>
  );
}
