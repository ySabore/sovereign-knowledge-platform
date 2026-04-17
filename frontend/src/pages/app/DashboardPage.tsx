import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { ChatSourcesPanel } from "../../components/chat/ChatSourcesPanel";
import { useAuth } from "../../context/AuthContext";
import type { Citation, SseChatEvent } from "../../lib/chatSse";
import { streamChatSse } from "../../lib/chatSse";
import { ensureFreshClerkTokenIfNeeded } from "../../lib/clerkTokenBridge";
import {
  DEFAULT_CHAT_SUGGESTIONS,
  DEMO_WORKSPACE_CHAT_SUGGESTIONS,
} from "../../data/demoWorkspaceChatSuggestions";

type Ws = { id: string; name: string; organization_id: string };
type ChatSession = { id: string; workspace_id: string; title: string | null; updated_at: string };
type ChatMessage = {
  id: string;
  role: string;
  content: string;
  citations: Citation[];
};

const GENERATION_MODE_STORAGE_KEY = "skp_generation_meta_by_message_v1";
type GenerationDebugMeta = { mode: string; model?: string | null; confidence?: string | null };

function readGenerationModeStore(): Record<string, GenerationDebugMeta> {
  try {
    const raw = localStorage.getItem(GENERATION_MODE_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, string | GenerationDebugMeta>;
    if (!parsed || typeof parsed !== "object") return {};
    const normalized: Record<string, GenerationDebugMeta> = {};
    for (const [msgId, value] of Object.entries(parsed)) {
      if (typeof value === "string") {
        normalized[msgId] = { mode: value };
      } else if (value && typeof value === "object" && typeof value.mode === "string") {
        normalized[msgId] = {
          mode: value.mode,
          model: value.model ?? null,
          confidence:
            typeof value.confidence === "string" ? value.confidence : null,
        };
      }
    }
    return normalized;
  } catch {
    return {};
  }
}

function writeGenerationModeStore(next: Record<string, GenerationDebugMeta>): void {
  try {
    localStorage.setItem(GENERATION_MODE_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Ignore storage quota / private mode issues for debug-only data.
  }
}

function confidenceClass(level: string) {
  const l = level.toLowerCase();
  if (l === "high") return "skc-conf skc-conf-hi";
  if (l === "medium") return "skc-conf skc-conf-md";
  return "skc-conf skc-conf-lo";
}

function generationModeLabel(mode: string) {
  if (mode === "ollama") return "LLM: ollama";
  if (mode === "ollama_fallback_extractive") return "LLM fallback: extractive";
  if (mode === "openai") return "LLM: OpenAI";
  if (mode === "openai_fallback_extractive") return "OpenAI fallback: extractive";
  if (mode === "anthropic") return "LLM: Anthropic";
  if (mode === "anthropic_fallback_extractive") return "Anthropic fallback: extractive";
  if (mode === "extractive") return "Mode: extractive";
  if (mode === "no_evidence") return "Mode: no evidence";
  if (mode === "chitchat") return "Greeting (no document search)";
  return `Mode: ${mode.replaceAll("_", " ")}`;
}

function generationModeWithModelLabel(mode: string, model: string | undefined) {
  const base = generationModeLabel(mode);
  return model ? `${base} · ${model}` : base;
}

export type DashboardPageProps = {
  /** When set with embedded, drives workspace (platform shell on /organizations). */
  workspaceId?: string;
  /** Render inside HomePage main column; uses workspaceId prop instead of route params. */
  embedded?: boolean;
  /** Match platform bright mode when embedded under /home or /organizations. */
  embeddedBright?: boolean;
  onEmbeddedWorkspaceChange?: (workspaceId: string) => void;
};

export function DashboardPage({
  workspaceId: workspaceIdProp,
  embedded = false,
  embeddedBright = false,
  onEmbeddedWorkspaceChange,
}: DashboardPageProps = {}) {
  const { workspaceId: routeId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const { user, logout, token } = useAuth();

  const [workspaces, setWorkspaces] = useState<Ws[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [confidenceById, setConfidenceById] = useState<Record<string, string>>({});
  const [generationModeById, setGenerationModeById] = useState<Record<string, string>>({});
  const [generationModelById, setGenerationModelById] = useState<Record<string, string>>({});
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [feedbackByMsg, setFeedbackByMsg] = useState<Record<string, "up" | "down" | undefined>>({});
  /** Full-screen “Loading workspace” only on standalone `/dashboard`; embedded chat stays mounted so history + scroll aren’t torn down on every return. */
  const [loadingWs, setLoadingWs] = useState(() => !embedded);

  const messagesScrollRef = useRef<HTMLDivElement>(null);

  const workspaceId = embedded ? (workspaceIdProp ?? "") : (routeId ?? "");
  const workspaceIdRef = useRef(workspaceId);
  workspaceIdRef.current = workspaceId;
  /** First workspace fetch after `workspaceId` change may block UI; later refetches stay in-place (no full-screen flash). */
  const wsFetchShouldBlockRef = useRef(true);
  useEffect(() => {
    wsFetchShouldBlockRef.current = true;
  }, [workspaceId]);
  /** Parent may pass an inline callback — keep `loadWorkspaces` stable so it does not refetch on every parent render. */
  const onEmbeddedWorkspaceChangeRef = useRef(onEmbeddedWorkspaceChange);
  onEmbeddedWorkspaceChangeRef.current = onEmbeddedWorkspaceChange;

  const loadWorkspaces = useCallback(async () => {
    const blocking = wsFetchShouldBlockRef.current && !embedded;
    if (blocking) setLoadingWs(true);
    try {
      const { data: orgs } = await api.get<{ id: string }[]>("/organizations/me");
      const all: Ws[] = [];
      for (const o of orgs) {
        const { data: wss } = await api.get<Ws[]>(`/workspaces/org/${o.id}`);
        all.push(...wss);
      }
      setWorkspaces(all);
      const wid = workspaceIdRef.current;
      if (wid && !all.some((w) => w.id === wid) && all[0]) {
        if (embedded) {
          onEmbeddedWorkspaceChangeRef.current?.(all[0].id);
        } else {
          navigate(`/dashboard/${all[0].id}`, { replace: true });
        }
      }
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      if (blocking) {
        setLoadingWs(false);
        wsFetchShouldBlockRef.current = false;
      }
    }
  }, [workspaceId, navigate, embedded]);

  /**
   * `selectLatest`: true when (re)entering chat for a workspace — pick the most recently updated session (API order).
   * false when refreshing the sidebar after a send/create — keep the current selection.
   * Ignores stale responses if `workspaceId` changed while the request was in flight.
   */
  const loadSessions = useCallback(async (selectLatest = false) => {
    const wid = workspaceIdRef.current;
    if (!wid) return;
    const { data } = await api.get<ChatSession[]>(`/chat/workspaces/${wid}/sessions`);
    if (workspaceIdRef.current !== wid) return;
    setSessions(data);
    setActiveSessionId((prev) => {
      if (selectLatest) return data[0]?.id ?? null;
      return prev ?? data[0]?.id ?? null;
    });
  }, []);

  const deleteChatSession = useCallback(
    async (sessionId: string) => {
      if (!window.confirm("Delete this conversation?")) return;
      try {
        await api.delete(`/chat/sessions/${sessionId}`);
        await loadSessions(false);
        if (activeSessionId === sessionId) {
          setActiveSessionId(null);
          setMessages([]);
        }
      } catch (e) {
        setErr(apiErrorMessage(e));
      }
    },
    [loadSessions, activeSessionId],
  );

  const activeSessionIdRef = useRef<string | null>(activeSessionId);
  activeSessionIdRef.current = activeSessionId;

  const loadMessages = useCallback(async () => {
    const sid = activeSessionId;
    if (!sid) {
      setMessages([]);
      return;
    }
    const { data } = await api.get<{ messages: ChatMessage[] }>(`/chat/sessions/${sid}`);
    if (activeSessionIdRef.current !== sid) return;
    setMessages(data.messages);
    const persisted = readGenerationModeStore();
    const fromHistory: Record<string, string> = {};
    const modelFromHistory: Record<string, string> = {};
    const confidenceFromHistory: Record<string, string> = {};
    for (const msg of data.messages) {
      if (msg.role !== "assistant") continue;
      const meta = persisted[msg.id];
      if (meta?.mode) fromHistory[msg.id] = meta.mode;
      if (meta?.model) modelFromHistory[msg.id] = meta.model;
      if (meta?.confidence) confidenceFromHistory[msg.id] = meta.confidence;
    }
    if (Object.keys(fromHistory).length > 0) {
      setGenerationModeById((prev) => ({ ...prev, ...fromHistory }));
    }
    if (Object.keys(modelFromHistory).length > 0) {
      setGenerationModelById((prev) => ({ ...prev, ...modelFromHistory }));
    }
    if (Object.keys(confidenceFromHistory).length > 0) {
      setConfidenceById((prev) => ({ ...prev, ...confidenceFromHistory }));
    }
    const firstCitation = data.messages
      .slice()
      .reverse()
      .find((m) => m.role === "assistant" && m.citations.length > 0)?.citations?.[0];
    setSelectedCitation(firstCitation ?? null);
    setStreamText("");
    const sidKeep = sid;
    queueMicrotask(() => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const root = messagesScrollRef.current;
          if (root && activeSessionIdRef.current === sidKeep) {
            root.scrollTop = root.scrollHeight;
          }
        });
      });
    });
  }, [activeSessionId]);

  useEffect(() => {
    loadWorkspaces().catch((e) => setErr(apiErrorMessage(e)));
  }, [loadWorkspaces]);

  useEffect(() => {
    setActiveSessionId(null);
    setSessions([]);
    if (!workspaceId) return;
    loadSessions(true).catch((e) => setErr(apiErrorMessage(e)));
  }, [workspaceId, loadSessions]);

  useEffect(() => {
    loadMessages().catch((e) => setErr(apiErrorMessage(e)));
  }, [activeSessionId, loadMessages]);

  /**
   * Default the scroller to the latest message (bottom). `.skc-messages` is the scroll root (flex:1 + min-height:0).
   * Waits until standalone dashboard finishes workspace load so the scroll root exists after the loading screen.
   */
  useLayoutEffect(() => {
    if (!embedded && loadingWs) return;
    const el = messagesScrollRef.current;
    if (!el) return;
    const snap = () => {
      el.scrollTop = el.scrollHeight;
    };
    snap();
    requestAnimationFrame(() => {
      snap();
      requestAnimationFrame(snap);
    });
  }, [embedded, loadingWs, activeSessionId, messages, streaming, streamText]);

  /** Late layout (citations, fonts) can grow the thread after paint — one more snap when loading gate clears or thread size changes. */
  useEffect(() => {
    if (!embedded && loadingWs) return;
    if (messages.length === 0 && !streaming && !streamText) return;
    const el = messagesScrollRef.current;
    if (!el) return;
    const t = window.setTimeout(() => {
      el.scrollTop = el.scrollHeight;
    }, 0);
    return () => clearTimeout(t);
  }, [embedded, loadingWs, messages.length, activeSessionId, streaming, streamText]);

  const onWorkspaceChange = (id: string) => {
    if (embedded) {
      onEmbeddedWorkspaceChange?.(id);
    } else {
      navigate(`/dashboard/${id}`);
    }
    setActiveSessionId(null);
    setSessions([]);
    setMessages([]);
  };

  const ensureSession = async (): Promise<string> => {
    if (activeSessionId) return activeSessionId;
    const { data } = await api.post<ChatSession>(`/chat/workspaces/${workspaceId}/sessions`, { title: "Conversation" });
    setActiveSessionId(data.id);
    await loadSessions(false);
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
    await ensureFreshClerkTokenIfNeeded();
    const authToken = localStorage.getItem("skp_token") ?? token;

    let assistantContent = "";
    try {
      for await (const ev of streamChatSse(url, { session_id: sid, content: q, top_k: 5 }, authToken)) {
        const event = ev as SseChatEvent;
        if (event.type === "delta") {
          assistantContent += event.text;
          setStreamText(assistantContent);
        } else if (event.type === "done") {
          setConfidenceById((c) => ({ ...c, [event.assistant_message_id]: event.confidence }));
          const existing = readGenerationModeStore();
          const prevMeta = existing[event.assistant_message_id];
          writeGenerationModeStore({
            ...existing,
            [event.assistant_message_id]: {
              mode: event.generation_mode ?? prevMeta?.mode ?? "unknown",
              model: event.generation_model ?? prevMeta?.model ?? null,
              confidence: event.confidence ?? prevMeta?.confidence ?? null,
            },
          });
          if (event.generation_mode) {
            setGenerationModeById((m) => ({ ...m, [event.assistant_message_id]: event.generation_mode as string }));
          }
          if (event.generation_model) {
            setGenerationModelById((x) => ({ ...x, [event.assistant_message_id]: event.generation_model as string }));
          }
          if (event.citations?.[0]) {
            setSelectedCitation(event.citations[0]);
          }
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
      await loadSessions(false).catch(() => {});
    }
  };

  const latestAssistantCitations =
    messages
      .slice()
      .reverse()
      .find((m) => m.role === "assistant" && m.citations.length > 0)?.citations ?? [];

  function fmtWhen(iso: string) {
    const d = new Date(iso);
    return d.toLocaleString([], { hour: "2-digit", minute: "2-digit" });
  }

  const historyGroups = useMemo(() => {
    const today: ChatSession[] = [];
    const earlier: ChatSession[] = [];
    const now = new Date();
    sessions.forEach((s) => {
      const d = new Date(s.updated_at);
      const sameDay = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
      if (sameDay) today.push(s);
      else earlier.push(s);
    });
    return { today, earlier };
  }, [sessions]);

  const suggestedPrompts = useMemo(() => {
    const ws = workspaces.find((w) => w.id === workspaceId);
    if (!ws) return [...DEFAULT_CHAT_SUGGESTIONS];
    const demo = DEMO_WORKSPACE_CHAT_SUGGESTIONS[ws.name];
    return demo?.length ? [...demo] : [...DEFAULT_CHAT_SUGGESTIONS];
  }, [workspaces, workspaceId]);

  if (!workspaceId || (!embedded && loadingWs)) {
    return (
      <div
        className={`skc-frame${embedded ? " skc-frame--embedded" : ""}${embedded && embeddedBright ? " skc-frame--bright" : ""}`}
      >
        <main className="sk-main">
          <p className="sk-muted">Loading workspace…</p>
        </main>
      </div>
    );
  }

  const showEmpty = messages.length === 0 && !streaming;

  return (
    <div
      className={`skc-frame${embedded ? " skc-frame--embedded" : ""}${embedded && embeddedBright ? " skc-frame--bright" : ""}`}
    >
      {!embedded && (
        <div className="skc-topbar">
          <div className="skc-logo">
            <div className="skc-logo-icon">⬢</div>
            AI Knowledge
          </div>
          <select className="skc-workspace-select" value={workspaceId} onChange={(e) => onWorkspaceChange(e.target.value)}>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <div className="skc-topbar-right">
            <span className="sk-muted" style={{ fontSize: "0.75rem" }}>
              {latestAssistantCitations.length} cited
            </span>
            <span className="skc-pill skc-pill-ok">● Operational</span>
            <Link className="skc-avatar" to="/home">
              {user?.email?.slice(0, 2).toUpperCase() || "U"}
            </Link>
          </div>
        </div>
      )}

      <aside className="skc-history">
        <div className="skc-history-top">
          <button
            type="button"
            className="skc-new-chat"
            onClick={() => {
              setActiveSessionId(null);
              setMessages([]);
            }}
          >
            + New conversation
          </button>
        </div>
        <div className="skc-group-label">Today</div>
        <div className="skc-history-list">
          {historyGroups.today.map((s) => (
            <div key={s.id} className={`skc-history-item-row ${activeSessionId === s.id ? "on" : ""}`}>
              <button type="button" className="skc-history-item" onClick={() => setActiveSessionId(s.id)}>
                <div className="skc-history-q">{s.title || "Untitled conversation"}</div>
                <div className="skc-history-m">{fmtWhen(s.updated_at)}</div>
              </button>
              <button
                type="button"
                className="skc-history-del"
                title="Delete conversation"
                aria-label="Delete conversation"
                onClick={(e) => {
                  e.stopPropagation();
                  void deleteChatSession(s.id);
                }}
              >
                ×
              </button>
            </div>
          ))}
          {historyGroups.earlier.length > 0 && <div className="skc-group-label">Earlier</div>}
          {historyGroups.earlier.map((s) => (
            <div key={s.id} className={`skc-history-item-row ${activeSessionId === s.id ? "on" : ""}`}>
              <button type="button" className="skc-history-item" onClick={() => setActiveSessionId(s.id)}>
                <div className="skc-history-q">{s.title || "Untitled conversation"}</div>
                <div className="skc-history-m">{new Date(s.updated_at).toLocaleDateString()}</div>
              </button>
              <button
                type="button"
                className="skc-history-del"
                title="Delete conversation"
                aria-label="Delete conversation"
                onClick={(e) => {
                  e.stopPropagation();
                  void deleteChatSession(s.id);
                }}
              >
                ×
              </button>
            </div>
          ))}
        </div>
        {!embedded && (
          <div className="skc-history-bottom">
            <div className="sk-muted" style={{ fontSize: "0.75rem" }}>
              {user?.email}
            </div>
            <button className="sk-btn secondary" onClick={() => void logout()}>
              Sign out
            </button>
          </div>
        )}
      </aside>

      <main className="skc-main">
        <div className="skc-messages" ref={messagesScrollRef}>
          {err && <p className="sk-error">{err}</p>}
          {showEmpty && (
            <div className="skc-assistant">
              <div className="skc-assistant-avatar">⬢</div>
              <div className="skc-assistant-body">
                <div className="skc-assistant-text">
                  Ask anything about your organization’s knowledge base. Try one of these:
                  <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {suggestedPrompts.map((s) => (
                      <button key={s} className="skc-citation-pill" onClick={() => setInput(s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="skc-user-row">
                <div className="skc-user-bubble">{m.content}</div>
              </div>
            ) : (
              <div key={m.id} className="skc-assistant">
                <div className="skc-assistant-avatar">⬢</div>
                <div className="skc-assistant-body">
                  <div className="skc-assistant-text">
                    {m.content}
                    {m.citations.length > 0 && (
                      <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {m.citations.map((c, i) => (
                          <button key={`${c.chunk_id}-${i}`} className="skc-citation-pill" onClick={() => setSelectedCitation(c)}>
                            📄 {c.document_filename} {c.page_number != null ? `· p.${c.page_number}` : ""}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="skc-assistant-footer">
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      {confidenceById[m.id] && <div className={confidenceClass(confidenceById[m.id])}>{confidenceById[m.id]} confidence</div>}
                      {generationModeById[m.id] && (
                        <span className="skc-source-chip" title="Debug: answer generation mode">
                          {generationModeWithModelLabel(generationModeById[m.id], generationModelById[m.id])}
                        </span>
                      )}
                      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {Array.from(new Set(m.citations.map((c) => c.document_filename))).slice(0, 3).map((name) => (
                          <span key={name} className="skc-source-chip">
                            📄 {name}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 5 }}>
                      <button className="skc-icon-btn" onClick={() => navigator.clipboard.writeText(m.content).catch(() => {})}>
                        ⎘
                      </button>
                      <button
                        className={`skc-icon-btn ${feedbackByMsg[m.id] === "up" ? "on" : ""}`}
                        onClick={() => setFeedbackByMsg((f) => ({ ...f, [m.id]: "up" }))}
                      >
                        👍
                      </button>
                      <button
                        className={`skc-icon-btn ${feedbackByMsg[m.id] === "down" ? "on" : ""}`}
                        onClick={() => setFeedbackByMsg((f) => ({ ...f, [m.id]: "down" }))}
                      >
                        👎
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ),
          )}
          {streaming && streamText && (
            <div className="skc-assistant">
              <div className="skc-assistant-avatar">⬢</div>
              <div className="skc-assistant-body">
                <div className="skc-assistant-text">{streamText}</div>
              </div>
            </div>
          )}
        </div>

        <div className="skc-composer-wrap">
          <div className="skc-composer">
            <textarea
              className="skc-textarea"
              placeholder="Ask anything about your organization's knowledge…"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!streaming && input.trim()) void send();
                }
              }}
            />
            <div className="skc-composer-footer">
              <div style={{ display: "flex", gap: 6 }}>
                <div className="skc-hint-chip">Current workspace</div>
                <div className="skc-hint-chip">{sessions.length} chats</div>
              </div>
              <button className="skc-send-btn" disabled={streaming || !input.trim()} onClick={() => void send()}>
                ➤
              </button>
            </div>
          </div>
        </div>
      </main>
      <ChatSourcesPanel citations={latestAssistantCitations} selected={selectedCitation} onSelect={setSelectedCitation} />
    </div>
  );
}
