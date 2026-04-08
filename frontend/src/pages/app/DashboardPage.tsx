import type { CSSProperties } from "react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { ChatComposer } from "../../components/chat/ChatComposer";
import { ChatSourcesPanel } from "../../components/chat/ChatSourcesPanel";
import { useAuth } from "../../context/AuthContext";
import { AppShell } from "../../layouts/AppShell";
import type { Citation, SseChatEvent } from "../../lib/chatSse";
import { streamChatSse } from "../../lib/chatSse";

type Ws = { id: string; name: string; organization_id: string };
type ChatSession = { id: string; workspace_id: string; title: string | null; updated_at: string };
type ChatMessage = {
  id: string;
  role: string;
  content: string;
  citations: Citation[];
};

const SUGGESTED = [
  "What are the key obligations in our policies?",
  "Summarize refund and cancellation rules.",
  "Which documents mention security or data retention?",
  "What are the deadlines or SLA terms?",
];

function confidenceStyle(level: string): CSSProperties {
  const l = level.toLowerCase();
  if (l === "high") return { color: "var(--ok)", borderColor: "var(--ok)" };
  if (l === "medium") return { color: "var(--accent)", borderColor: "var(--accent)" };
  return { color: "var(--danger)", borderColor: "var(--danger)" };
}

export function DashboardPage() {
  const { workspaceId: wid } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const { user, logout, token } = useAuth();

  const [workspaces, setWorkspaces] = useState<Ws[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [confidenceById, setConfidenceById] = useState<Record<string, string>>({});
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [feedbackByMsg, setFeedbackByMsg] = useState<Record<string, "up" | "down" | undefined>>({});
  const [loadingWs, setLoadingWs] = useState(true);

  const workspaceId = wid ?? "";

  const loadWorkspaces = useCallback(async () => {
    setLoadingWs(true);
    try {
      const { data: orgs } = await api.get<{ id: string }[]>("/organizations/me");
      const all: Ws[] = [];
      for (const o of orgs) {
        const { data: wss } = await api.get<Ws[]>(`/workspaces/org/${o.id}`);
        all.push(...wss);
      }
      setWorkspaces(all);
      if (workspaceId && !all.some((w) => w.id === workspaceId) && all[0]) {
        navigate(`/dashboard/${all[0].id}`, { replace: true });
      }
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setLoadingWs(false);
    }
  }, [workspaceId, navigate]);

  const loadSessions = useCallback(async () => {
    if (!workspaceId) return;
    const { data } = await api.get<ChatSession[]>(`/chat/workspaces/${workspaceId}/sessions`);
    setSessions(data);
    setActiveSessionId((prev) => prev ?? data[0]?.id ?? null);
  }, [workspaceId]);

  const loadMessages = useCallback(async () => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    const { data } = await api.get<{ messages: ChatMessage[] }>(`/chat/sessions/${activeSessionId}`);
    setMessages(data.messages);
    const firstCitation = data.messages
      .slice()
      .reverse()
      .find((m) => m.role === "assistant" && m.citations.length > 0)?.citations?.[0];
    setSelectedCitation(firstCitation ?? null);
    setStreamText("");
  }, [activeSessionId]);

  useEffect(() => {
    loadWorkspaces().catch((e) => setErr(apiErrorMessage(e)));
  }, [loadWorkspaces]);

  useEffect(() => {
    setActiveSessionId(null);
  }, [workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;
    loadSessions().catch((e) => setErr(apiErrorMessage(e)));
  }, [workspaceId, loadSessions]);

  useEffect(() => {
    loadMessages().catch((e) => setErr(apiErrorMessage(e)));
  }, [activeSessionId, loadMessages]);

  const onWorkspaceChange = (id: string) => {
    navigate(`/dashboard/${id}`);
    setActiveSessionId(null);
    setSessions([]);
    setMessages([]);
  };

  const ensureSession = async (): Promise<string> => {
    if (activeSessionId) return activeSessionId;
    const { data } = await api.post<ChatSession>(`/chat/workspaces/${workspaceId}/sessions`, { title: "Conversation" });
    setActiveSessionId(data.id);
    await loadSessions();
    return data.id;
  };

  const send = async () => {
    const q = input.trim();
    if (!q || !workspaceId || streaming) return;
    setErr(null);
    setInput("");
    setStreaming(true);
    setStreamText("");

    let sid: string;
    try {
      sid = await ensureSession();
    } catch (e) {
      setErr(apiErrorMessage(e));
      setStreaming(false);
      return;
    }

    const userMsg: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: q,
      citations: [],
    };
    setMessages((m) => [...m, userMsg]);

    const base = import.meta.env.VITE_API_BASE?.trim() || "";
    const url = `${base}/api/chat`;
    const authToken = token ?? localStorage.getItem("skp_token");

    let assistantContent = "";
    try {
      for await (const ev of streamChatSse(url, { session_id: sid, content: q, top_k: 5 }, authToken)) {
        const event = ev as SseChatEvent;
        if (event.type === "delta") {
          assistantContent += event.text;
          setStreamText(assistantContent);
        } else if (event.type === "done") {
          setConfidenceById((c) => ({ ...c, [event.assistant_message_id]: event.confidence }));
          setStreamText("");
        } else if (event.type === "error") {
          setErr(event.detail);
        }
      }
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setStreaming(false);
      await loadMessages().catch(() => {});
      await loadSessions().catch(() => {});
    }
  };

  const latestAssistantCitations =
    messages
      .slice()
      .reverse()
      .find((m) => m.role === "assistant" && m.citations.length > 0)?.citations ?? [];

  function fmtWhen(iso: string) {
    const d = new Date(iso);
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  const sidebar = (
    <aside className="sk-nav">
      <h1 style={{ fontSize: "1rem" }}>Sovereign Knowledge</h1>
      <p className="sk-muted" style={{ fontSize: "0.85rem" }}>
        <Link to="/home">Organizations</Link>
      </p>
      <h2 style={{ fontSize: "0.85rem", margin: "1rem 0 0.5rem" }}>Chat history</h2>
      <button
        type="button"
        className="sk-btn"
        style={{ width: "100%", marginBottom: "0.75rem" }}
        onClick={() => {
          setActiveSessionId(null);
          setMessages([]);
        }}
      >
        New chat
      </button>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, maxHeight: "50vh", overflow: "auto" }}>
        {sessions.map((s) => (
          <li key={s.id} style={{ marginBottom: "0.4rem" }}>
            <button
              type="button"
              style={{
                width: "100%",
                textAlign: "left",
                borderRadius: 8,
                border: activeSessionId === s.id ? "1px solid var(--accent)" : "1px solid var(--border)",
                background: activeSessionId === s.id ? "rgba(61,139,253,0.12)" : "var(--surface2)",
                padding: "0.5rem 0.55rem",
                color: "var(--text)",
              }}
              onClick={() => setActiveSessionId(s.id)}
            >
              <div style={{ fontSize: "0.82rem", fontWeight: 600, lineHeight: 1.35 }}>
                {s.title || "Untitled conversation"}
              </div>
              <div className="sk-muted sk-mono" style={{ fontSize: "0.7rem", marginTop: 2 }}>
                {fmtWhen(s.updated_at)}
              </div>
            </button>
          </li>
        ))}
      </ul>
      <p style={{ fontSize: "0.85rem", marginTop: "1.5rem" }}>{user?.email}</p>
      <button type="button" className="sk-btn secondary" style={{ marginTop: "0.75rem", width: "100%" }} onClick={() => void logout()}>
        Sign out
      </button>
    </aside>
  );

  if (!workspaceId || loadingWs) {
    return (
      <div className="sk-layout">
        {sidebar}
        <main className="sk-main">
          <p className="sk-muted">Loading workspace…</p>
        </main>
      </div>
    );
  }

  const showEmpty = messages.length === 0 && !streaming;

  return (
    <AppShell
      sidebar={sidebar}
      aside={<ChatSourcesPanel citations={latestAssistantCitations} selected={selectedCitation} onSelect={setSelectedCitation} />}
    >
      <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
        <header className="sk-page-header" style={{ padding: "0 1.5rem", flexShrink: 0 }}>
          <div>
            <h2 style={{ margin: 0 }}>Workspace chat</h2>
            <p className="sk-muted sk-mono" style={{ margin: "0.25rem 0 0", fontSize: "0.8rem" }}>
              {workspaces.find((w) => w.id === workspaceId)?.name ?? workspaceId}
            </p>
          </div>
          <Link className="sk-btn secondary" to="/admin">
            Admin
          </Link>
        </header>

        <div className="sk-main" style={{ flex: 1, overflow: "auto", paddingBottom: 0 }}>
          {err && <p className="sk-error">{err}</p>}

          {showEmpty && (
            <div className="sk-panel sk-spaced" style={{ maxWidth: 720 }}>
              <h3 style={{ marginTop: 0 }}>Ask your knowledge base</h3>
              <p className="sk-muted">Suggested questions (upload PDFs in this workspace first):</p>
              <ul>
                {SUGGESTED.map((s) => (
                  <li key={s} style={{ marginBottom: "0.35rem" }}>
                    <button type="button" className="sk-btn secondary" style={{ textAlign: "left" }} onClick={() => setInput(s)}>
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="sk-chat-log" style={{ padding: "0 1.5rem 1rem" }}>
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  display: "flex",
                  justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                  marginBottom: "1rem",
                }}
              >
                <div
                  style={{
                    maxWidth: "min(720px, 92%)",
                    borderRadius: 12,
                    padding: "0.75rem 1rem",
                    background: m.role === "user" ? "#1e293b" : "var(--surface2)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <div className="sk-label">{m.role === "user" ? "You" : "Assistant"}</div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
                  {m.role === "assistant" && confidenceById[m.id] && (
                    <div className="sk-row" style={{ marginTop: "0.5rem" }}>
                      <span
                        className="sk-badge"
                        style={{
                          ...confidenceStyle(confidenceById[m.id] ?? "low"),
                          borderWidth: 1,
                          borderStyle: "solid",
                        }}
                      >
                        Confidence: {confidenceById[m.id]}
                      </span>
                    </div>
                  )}
                  {m.role === "assistant" && (m.citations?.length ?? 0) > 0 && (
                    <div style={{ marginTop: "0.75rem" }}>
                      <div className="sk-label">Citations</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                        {m.citations.map((c, i) => (
                          <button
                            key={`${c.chunk_id}-${i}`}
                            type="button"
                            className="sk-btn secondary"
                            style={{ fontSize: "0.76rem", padding: "0.2rem 0.5rem", borderRadius: 999 }}
                            onClick={() => {
                              setSelectedCitation(c);
                            }}
                          >
                            📄 {c.document_filename}
                            {c.page_number != null ? ` · p.${c.page_number}` : ""}
                          </button>
                        ))}
                      </div>
                      <div className="sk-row" style={{ marginTop: "0.5rem" }}>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            className="sk-btn secondary"
                            style={{ padding: "0.22rem 0.45rem", fontSize: "0.75rem" }}
                            onClick={() => navigator.clipboard.writeText(m.content).catch(() => {})}
                          >
                            Copy
                          </button>
                          <button
                            type="button"
                            className="sk-btn secondary"
                            style={{
                              padding: "0.22rem 0.45rem",
                              fontSize: "0.75rem",
                              borderColor: feedbackByMsg[m.id] === "up" ? "var(--ok)" : undefined,
                            }}
                            onClick={() => setFeedbackByMsg((f) => ({ ...f, [m.id]: "up" }))}
                          >
                            👍
                          </button>
                          <button
                            type="button"
                            className="sk-btn secondary"
                            style={{
                              padding: "0.22rem 0.45rem",
                              fontSize: "0.75rem",
                              borderColor: feedbackByMsg[m.id] === "down" ? "var(--danger)" : undefined,
                            }}
                            onClick={() => setFeedbackByMsg((f) => ({ ...f, [m.id]: "down" }))}
                          >
                            👎
                          </button>
                        </div>
                        <span className="sk-muted" style={{ fontSize: "0.78rem" }}>
                          Scope: current workspace
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {streaming && streamText && (
              <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "1rem" }}>
                <div
                  style={{
                    maxWidth: "min(720px, 92%)",
                    borderRadius: 12,
                    padding: "0.75rem 1rem",
                    background: "var(--surface2)",
                    border: "1px dashed var(--border)",
                  }}
                >
                  <div className="sk-label">Assistant · streaming</div>
                  <div style={{ whiteSpace: "pre-wrap" }}>{streamText}</div>
                </div>
              </div>
            )}
          </div>
        </div>

        <ChatComposer
          value={input}
          onChange={setInput}
          onSubmit={() => void send()}
          disabled={streaming}
          workspaces={workspaces}
          workspaceId={workspaceId}
          onWorkspaceChange={onWorkspaceChange}
        />
      </div>
    </AppShell>
  );
}
