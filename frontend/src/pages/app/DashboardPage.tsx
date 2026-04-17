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
  feedback?: "up" | "down" | null;
};

type ChatUploadResponse = {
  document_id: string;
  filename: string;
  chunk_count: number;
};

type NotificationPrefs = {
  emailDigest: boolean;
  productUpdates: boolean;
  answerReadyAlerts: boolean;
};

const GENERATION_MODE_STORAGE_KEY = "skp_generation_meta_by_message_v1";
const CHAT_NOTIFICATION_PREFS_KEY = "skp_member_chat_notification_prefs_v1";
type GenerationDebugMeta = { mode: string; model?: string | null; confidence?: string | null };

function readNotificationPrefs(): NotificationPrefs {
  try {
    const raw = localStorage.getItem(CHAT_NOTIFICATION_PREFS_KEY);
    if (!raw) {
      return { emailDigest: true, productUpdates: false, answerReadyAlerts: true };
    }
    const parsed = JSON.parse(raw) as Partial<NotificationPrefs>;
    return {
      emailDigest: Boolean(parsed.emailDigest),
      productUpdates: Boolean(parsed.productUpdates),
      answerReadyAlerts: Boolean(parsed.answerReadyAlerts),
    };
  } catch {
    return { emailDigest: true, productUpdates: false, answerReadyAlerts: true };
  }
}

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
  if (mode === "workspace_stats") return "Workspace metadata";
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
  /** Member chat-first mode: hide conversation sidebar menu in embedded shell. */
  chatOnlyMode?: boolean;
  /** Controlled account settings modal open state (used by Home top-right avatar menu). */
  accountSettingsOpen?: boolean;
  /** Close callback for controlled account settings modal state. */
  onCloseAccountSettings?: () => void;
  onEmbeddedWorkspaceChange?: (workspaceId: string) => void;
};

export function DashboardPage({
  workspaceId: workspaceIdProp,
  embedded = false,
  embeddedBright = false,
  chatOnlyMode = false,
  accountSettingsOpen,
  onCloseAccountSettings,
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
  const [feedbackBusyByMsg, setFeedbackBusyByMsg] = useState<Record<string, boolean>>({});
  const [showAccountSettingsLocal, setShowAccountSettingsLocal] = useState(false);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPrefs>(() => readNotificationPrefs());
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadNote, setUploadNote] = useState<string | null>(null);
  const chatUploadInputRef = useRef<HTMLInputElement | null>(null);
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

  useEffect(() => {
    localStorage.setItem(CHAT_NOTIFICATION_PREFS_KEY, JSON.stringify(notificationPrefs));
  }, [notificationPrefs]);

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
    const feedbackFromHistory: Record<string, "up" | "down" | undefined> = {};
    for (const msg of data.messages) {
      if (msg.role !== "assistant") continue;
      if (msg.feedback === "up" || msg.feedback === "down") {
        feedbackFromHistory[msg.id] = msg.feedback;
      }
    }
    setFeedbackByMsg(feedbackFromHistory);
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
    const { data } = await api.post<ChatSession>(`/chat/workspaces/${workspaceId}/sessions`, {});
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

  const setMessageFeedback = async (messageId: string, next: "up" | "down" | null) => {
    if (feedbackBusyByMsg[messageId]) return;
    setFeedbackBusyByMsg((prev) => ({ ...prev, [messageId]: true }));
    const optimistic = next ?? undefined;
    setFeedbackByMsg((prev) => ({ ...prev, [messageId]: optimistic }));
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: next } : m)));
    try {
      const { data } = await api.put<ChatMessage>(`/chat/messages/${messageId}/feedback`, { feedback: next });
      const persisted = (data.feedback === "up" || data.feedback === "down") ? data.feedback : undefined;
      setFeedbackByMsg((prev) => ({ ...prev, [messageId]: persisted }));
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: data.feedback ?? null } : m)));
    } catch (e) {
      setErr(apiErrorMessage(e));
      await loadMessages().catch(() => {});
    } finally {
      setFeedbackBusyByMsg((prev) => ({ ...prev, [messageId]: false }));
    }
  };

  const uploadFilesFromChat = async (files: FileList | null) => {
    if (!files || files.length === 0 || !workspaceId || uploadBusy) return;
    setUploadBusy(true);
    setUploadNote(null);
    let success = 0;
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        await api.post<ChatUploadResponse>(`/chat/workspaces/${workspaceId}/upload`, form);
        success += 1;
      }
      setUploadNote(
        success === 1
          ? "1 file uploaded and indexed. You can ask questions about it now."
          : `${success} files uploaded and indexed.`,
      );
    } catch (e) {
      setErr(apiErrorMessage(e));
      setUploadNote(null);
    } finally {
      setUploadBusy(false);
      if (chatUploadInputRef.current) chatUploadInputRef.current.value = "";
      await loadMessages().catch(() => {});
    }
  };

  const exportConversationPdf = async () => {
    if (!messages.length) return;
    const { jsPDF } = await import("jspdf");
    const doc = new jsPDF({ unit: "pt", format: "a4" });
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margin = 42;
    const maxTextWidth = pageWidth - margin * 2;
    let y = margin;
    const activeSession = sessions.find((s) => s.id === activeSessionId);
    const title = (activeSession?.title || "Conversation export").trim();
    doc.setFont("helvetica", "bold");
    doc.setFontSize(15);
    doc.text(title, margin, y);
    y += 20;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(10);
    doc.setTextColor(90);
    doc.text(`Workspace: ${workspaces.find((w) => w.id === workspaceId)?.name || "Current workspace"}`, margin, y);
    y += 16;
    doc.text(`Exported: ${new Date().toLocaleString()}`, margin, y);
    y += 20;
    doc.setTextColor(20);
    for (const msg of messages) {
      const label = msg.role === "assistant" ? "Assistant" : msg.role === "user" ? "You" : msg.role;
      const header = `${label} • ${new Date().toLocaleString()}`;
      const wrappedHeader = doc.splitTextToSize(header, maxTextWidth);
      const wrappedBody = doc.splitTextToSize(msg.content || "", maxTextWidth);
      const blockHeight = (wrappedHeader.length + wrappedBody.length + 2) * 14;
      if (y + blockHeight > pageHeight - margin) {
        doc.addPage();
        y = margin;
      }
      doc.setFont("helvetica", "bold");
      doc.setFontSize(10);
      doc.text(wrappedHeader, margin, y);
      y += wrappedHeader.length * 14;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.text(wrappedBody, margin, y);
      y += wrappedBody.length * 14 + 10;
    }
    const fileSafe = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "chat-export";
    doc.save(`${fileSafe}.pdf`);
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
    const yesterday: ChatSession[] = [];
    const lastWeek: ChatSession[] = [];
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfYesterday = new Date(startOfToday);
    startOfYesterday.setDate(startOfYesterday.getDate() - 1);
    sessions.forEach((s) => {
      const d = new Date(s.updated_at);
      const sameDay = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
      const sameYesterday =
        d.getFullYear() === startOfYesterday.getFullYear()
        && d.getMonth() === startOfYesterday.getMonth()
        && d.getDate() === startOfYesterday.getDate();
      if (sameDay) {
        today.push(s);
      } else if (sameYesterday) {
        yesterday.push(s);
      } else {
        // Keep all older conversations discoverable under one enterprise-style bucket.
        lastWeek.push(s);
      }
    });
    return { today, yesterday, lastWeek };
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
  const showHistoryMenu = true;
  const showAccountSettings = accountSettingsOpen ?? showAccountSettingsLocal;
  const closeAccountSettings = () => {
    if (onCloseAccountSettings) {
      onCloseAccountSettings();
      return;
    }
    setShowAccountSettingsLocal(false);
  };

  return (
    <div
      className={`skc-frame${embedded ? " skc-frame--embedded" : ""}${embedded && embeddedBright ? " skc-frame--bright" : ""}${!showHistoryMenu ? " skc-frame--chat-only" : ""}`}
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

      {showHistoryMenu && (
        <aside className="skc-history">
          <div className="skc-history-top">
            <div className="skc-group-label skc-group-label--top">Chat</div>
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
          <div className="skc-group-label skc-group-label--section">History</div>
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
            {historyGroups.yesterday.length > 0 && <div className="skc-group-label">Yesterday</div>}
            {historyGroups.yesterday.map((s) => (
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
            {historyGroups.lastWeek.length > 0 && <div className="skc-group-label">Last week</div>}
            {historyGroups.lastWeek.map((s) => (
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
          {!chatOnlyMode && (
            <div className="skc-history-bottom">
              <div className="skc-group-label skc-group-label--section">Account</div>
              <div className="skc-account-card">
                <div className="skc-account-avatar">{user?.email?.slice(0, 2).toUpperCase() || "U"}</div>
                <div className="skc-account-meta">
                  <div className="skc-account-name">Workspace user</div>
                  <div className="skc-account-email">{user?.email || "signed in"}</div>
                </div>
              </div>
              <button
                type="button"
                className="skc-account-settings-btn"
                onClick={() => setShowAccountSettingsLocal(true)}
              >
                Profile & notifications
              </button>
              {!embedded && (
                <button className="sk-btn secondary" onClick={() => void logout()}>
                  Sign out
                </button>
              )}
            </div>
          )}
        </aside>
      )}

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
                        disabled={Boolean(feedbackBusyByMsg[m.id])}
                        onClick={() => void setMessageFeedback(m.id, feedbackByMsg[m.id] === "up" ? null : "up")}
                      >
                        👍
                      </button>
                      <button
                        className={`skc-icon-btn ${feedbackByMsg[m.id] === "down" ? "on" : ""}`}
                        disabled={Boolean(feedbackBusyByMsg[m.id])}
                        onClick={() => void setMessageFeedback(m.id, feedbackByMsg[m.id] === "down" ? null : "down")}
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
            <input
              ref={chatUploadInputRef}
              type="file"
              multiple
              style={{ display: "none" }}
              accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm,.pptx,.xlsx,.xls,.csv,.rtf,.eml,.msg,.epub,.mobi,.png,.jpg,.jpeg,.webp,.tif,.tiff"
              onChange={(e) => {
                void uploadFilesFromChat(e.target.files);
              }}
            />
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
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <div className="skc-hint-chip">Current workspace</div>
                <div className="skc-hint-chip">{sessions.length} chats</div>
                <button
                  type="button"
                  className="skc-hint-chip skc-hint-chip--action"
                  disabled={uploadBusy}
                  onClick={() => chatUploadInputRef.current?.click()}
                >
                  {uploadBusy ? "Uploading..." : "Upload file"}
                </button>
                <button
                  type="button"
                  className="skc-hint-chip skc-hint-chip--action"
                  onClick={() => void exportConversationPdf()}
                  disabled={messages.length === 0}
                >
                  Export PDF
                </button>
                <button
                  type="button"
                  className="skc-hint-chip skc-hint-chip--action"
                  onClick={() => {
                    setActiveSessionId(null);
                    setMessages([]);
                  }}
                >
                  New conversation
                </button>
              </div>
              <button className="skc-send-btn" disabled={streaming || !input.trim()} onClick={() => void send()}>
                ➤
              </button>
            </div>
            {uploadNote && (
              <div style={{ marginTop: 8, fontSize: "0.7rem", color: "var(--ok, #10b981)" }}>
                {uploadNote}
              </div>
            )}
          </div>
        </div>
      </main>
      <ChatSourcesPanel citations={latestAssistantCitations} selected={selectedCitation} onSelect={setSelectedCitation} />
      {showAccountSettings && (
        <div className="skc-modal-backdrop" role="presentation" onClick={closeAccountSettings}>
          <div className="skc-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="skc-modal-header">
              <div>
                <div className="skc-modal-title">Profile & notifications</div>
                <div className="skc-modal-subtitle">Member preferences for your chat workspace.</div>
              </div>
              <button type="button" className="skc-icon-btn" onClick={closeAccountSettings}>×</button>
            </div>
            <div className="skc-modal-section">
              <div className="skc-modal-label">Profile</div>
              <div className="skc-modal-value">
                <div><strong>Name:</strong> {user?.full_name || "Not set"}</div>
                <div><strong>Email:</strong> {user?.email || "Unknown"}</div>
              </div>
            </div>
            <div className="skc-modal-section">
              <div className="skc-modal-label">Notifications</div>
              <label className="skc-toggle-row">
                <input
                  type="checkbox"
                  checked={notificationPrefs.answerReadyAlerts}
                  onChange={(e) => setNotificationPrefs((p) => ({ ...p, answerReadyAlerts: e.target.checked }))}
                />
                Notify me when answer generation completes
              </label>
              <label className="skc-toggle-row">
                <input
                  type="checkbox"
                  checked={notificationPrefs.emailDigest}
                  onChange={(e) => setNotificationPrefs((p) => ({ ...p, emailDigest: e.target.checked }))}
                />
                Weekly email digest
              </label>
              <label className="skc-toggle-row">
                <input
                  type="checkbox"
                  checked={notificationPrefs.productUpdates}
                  onChange={(e) => setNotificationPrefs((p) => ({ ...p, productUpdates: e.target.checked }))}
                />
                Product updates and tips
              </label>
            </div>
            <div className="skc-modal-footer">
              <button type="button" className="sk-btn secondary" onClick={closeAccountSettings}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
