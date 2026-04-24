import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
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

function IconCopyAnswer() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function IconCheckSmall() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

type Ws = { id: string; name: string; organization_id: string };
type ChatSession = { id: string; workspace_id: string; title: string | null; updated_at: string; pinned: boolean };
type ChatMessage = {
  id: string;
  role: string;
  content: string;
  citations: Citation[];
  feedback?: "up" | "down" | null;
  /** From API / DB for assistant messages — shown in the answer meta row. */
  confidence?: string | null;
  generation_mode?: string | null;
  generation_model?: string | null;
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
const SOURCES_PANEL_PINNED_KEY = "skp_sources_panel_pinned_v1";

function readSourcesPanelPinned(): boolean {
  try {
    return localStorage.getItem(SOURCES_PANEL_PINNED_KEY) === "1";
  } catch {
    return false;
  }
}
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
  if (l === "low") return "skc-conf skc-conf-lo";
  return "skc-conf skc-conf-unk";
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

/** Sidebar account line: member chat shows a fixed label; others use coarse flags from `/auth/me`. */
function accountRoleSubtitle(
  u: {
    is_platform_owner: boolean;
    org_ids_as_owner: string[];
    org_ids_as_workspace_admin: string[];
  } | null,
  chatOnlyMode: boolean,
): string {
  if (chatOnlyMode) return "Member · Workspace access only";
  if (!u) return "Member · Workspace access only";
  if (u.is_platform_owner) return "Platform owner";
  if (u.org_ids_as_owner.length > 0) return "Organization admin";
  if (u.org_ids_as_workspace_admin.length > 0) return "Workspace admin";
  return "Member · Workspace access only";
}

async function downloadChatPdf(params: { title: string; workspaceName: string; messages: ChatMessage[] }): Promise<void> {
  if (!params.messages.length) return;
  const { jsPDF } = await import("jspdf");
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 42;
  const maxTextWidth = pageWidth - margin * 2;
  let y = margin;
  const title = (params.title || "Conversation export").trim();
  doc.setFont("helvetica", "bold");
  doc.setFontSize(15);
  doc.text(title, margin, y);
  y += 20;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(90);
  doc.text(`Workspace: ${params.workspaceName}`, margin, y);
  y += 16;
  doc.text(`Exported: ${new Date().toLocaleString()}`, margin, y);
  y += 20;
  doc.setTextColor(20);
  for (const msg of params.messages) {
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
  /** Slide-over sources detail; default closed so the thread uses full width. */
  const [sourcesDrawerOpen, setSourcesDrawerOpen] = useState(false);
  /** Keep sources as a third column (pinned rail) vs overlay drawer. */
  const [sourcesPinned, setSourcesPinned] = useState(readSourcesPanelPinned);
  const [feedbackByMsg, setFeedbackByMsg] = useState<Record<string, "up" | "down" | undefined>>({});
  const [feedbackBusyByMsg, setFeedbackBusyByMsg] = useState<Record<string, boolean>>({});
  const [feedbackSavedFlashByMsg, setFeedbackSavedFlashByMsg] = useState<Record<string, boolean>>({});
  const [copyAckByMsg, setCopyAckByMsg] = useState<Record<string, boolean>>({});
  const [showAccountSettingsLocal, setShowAccountSettingsLocal] = useState(false);
  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPrefs>(() => readNotificationPrefs());
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadNote, setUploadNote] = useState<string | null>(null);
  const [pdfBusyId, setPdfBusyId] = useState<string | null>(null);
  const [historyMenuAnchor, setHistoryMenuAnchor] = useState<{
    sessionId: string;
    top: number;
    right: number;
  } | null>(null);
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

  useEffect(() => {
    setHistoryMenuAnchor(null);
  }, [workspaceId]);
  /** Parent may pass an inline callback — keep `loadWorkspaces` stable so it does not refetch on every parent render. */
  const onEmbeddedWorkspaceChangeRef = useRef(onEmbeddedWorkspaceChange);
  onEmbeddedWorkspaceChangeRef.current = onEmbeddedWorkspaceChange;
  const orgIdsCacheRef = useRef<string[] | null>(null);

  useEffect(() => {
    // Ensure a new login/account switch refreshes org membership bootstrap once.
    orgIdsCacheRef.current = null;
  }, [user?.id]);

  useEffect(() => {
    localStorage.setItem(CHAT_NOTIFICATION_PREFS_KEY, JSON.stringify(notificationPrefs));
  }, [notificationPrefs]);

  useEffect(() => {
    try {
      localStorage.setItem(SOURCES_PANEL_PINNED_KEY, sourcesPinned ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [sourcesPinned]);

  useEffect(() => {
    if (historyMenuAnchor === null) return;
    const onDocMouseDown = (e: MouseEvent) => {
      const t = e.target as HTMLElement | null;
      if (t?.closest("[data-sk-history-menu]")) return;
      setHistoryMenuAnchor(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHistoryMenuAnchor(null);
    };
    const onScrollOrResize = () => setHistoryMenuAnchor(null);
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [historyMenuAnchor]);

  useEffect(() => {
    setSourcesDrawerOpen(false);
  }, [activeSessionId]);

  useEffect(() => {
    if (!sourcesDrawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSourcesDrawerOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [sourcesDrawerOpen]);

  const loadWorkspaces = useCallback(async () => {
    const blocking = wsFetchShouldBlockRef.current && !embedded;
    if (blocking) setLoadingWs(true);
    try {
      let orgIds = orgIdsCacheRef.current;
      if (!orgIds) {
        const { data: orgs } = await api.get<{ id: string }[]>("/organizations/me");
        orgIds = orgs.map((o) => o.id);
        orgIdsCacheRef.current = orgIds;
      }
      const all: Ws[] = [];
      for (const oid of orgIds) {
        const { data: wss } = await api.get<Ws[]>(`/workspaces/org/${oid}`);
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
      orgIdsCacheRef.current = null;
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
    setSessions(data.map((s) => ({ ...s, pinned: Boolean(s.pinned) })));
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
    const fromApiConf: Record<string, string> = {};
    const fromApiMode: Record<string, string> = {};
    const fromApiModel: Record<string, string> = {};
    for (const msg of data.messages) {
      if (msg.role !== "assistant") continue;
      const meta = persisted[msg.id];
      if (meta?.mode) fromHistory[msg.id] = meta.mode;
      if (meta?.model) modelFromHistory[msg.id] = meta.model;
      if (meta?.confidence) confidenceFromHistory[msg.id] = meta.confidence;
      if (msg.confidence) fromApiConf[msg.id] = msg.confidence;
      if (msg.generation_mode) fromApiMode[msg.id] = msg.generation_mode;
      if (msg.generation_model) fromApiModel[msg.id] = msg.generation_model;
    }
    setGenerationModeById((prev) => ({ ...prev, ...fromHistory, ...fromApiMode }));
    setGenerationModelById((prev) => ({ ...prev, ...modelFromHistory, ...fromApiModel }));
    setConfidenceById((prev) => ({ ...prev, ...confidenceFromHistory, ...fromApiConf }));
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
          setGenerationModeById((m) => ({
            ...m,
            [event.assistant_message_id]: (event.generation_mode as string) || "unknown",
          }));
          setGenerationModelById((x) => ({
            ...x,
            [event.assistant_message_id]: (event.generation_model as string) ?? "",
          }));
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
      setFeedbackSavedFlashByMsg((prev) => ({ ...prev, [messageId]: true }));
      window.setTimeout(() => {
        setFeedbackSavedFlashByMsg((prev) => {
          const n = { ...prev };
          delete n[messageId];
          return n;
        });
      }, 1400);
    } catch (e) {
      setErr(apiErrorMessage(e));
      await loadMessages().catch(() => {});
    } finally {
      setFeedbackBusyByMsg((prev) => ({ ...prev, [messageId]: false }));
    }
  };

  const copyAnswerToClipboard = useCallback((messageId: string, text: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopyAckByMsg((prev) => ({ ...prev, [messageId]: true }));
      window.setTimeout(() => {
        setCopyAckByMsg((prev) => {
          const n = { ...prev };
          delete n[messageId];
          return n;
        });
      }, 2000);
    }).catch(() => {
      setErr("Could not copy to clipboard.");
    });
  }, []);

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

  const exportSessionPdf = useCallback(
    async (sessionId: string) => {
      const wsName = workspaces.find((w) => w.id === workspaceId)?.name || "Current workspace";
      try {
        setPdfBusyId(sessionId);
        let msgs: ChatMessage[] = [];
        let title: string | null = sessions.find((x) => x.id === sessionId)?.title ?? null;
        if (activeSessionId === sessionId && messages.length > 0) {
          msgs = messages;
        } else {
          const { data } = await api.get<{ session: { title: string | null }; messages: ChatMessage[] }>(
            `/chat/sessions/${sessionId}`,
          );
          msgs = data.messages;
          title = data.session.title;
        }
        if (!msgs.length) {
          setErr("Nothing to export in this conversation yet.");
          return;
        }
        await downloadChatPdf({
          title: title || "Conversation export",
          workspaceName: wsName,
          messages: msgs,
        });
      } catch (e) {
        setErr(apiErrorMessage(e));
      } finally {
        setPdfBusyId(null);
      }
    },
    [activeSessionId, messages, sessions, workspaceId, workspaces],
  );

  const renameSession = useCallback(
    async (s: ChatSession) => {
      const next = window.prompt("Rename conversation", s.title || "");
      if (next === null) return;
      const trimmed = next.trim();
      try {
        await api.patch(`/chat/sessions/${s.id}`, { title: trimmed.length ? trimmed : null });
        await loadSessions(false);
      } catch (e) {
        setErr(apiErrorMessage(e));
      }
    },
    [loadSessions],
  );

  const togglePinSession = useCallback(
    async (s: ChatSession) => {
      try {
        await api.patch(`/chat/sessions/${s.id}`, { pinned: !s.pinned });
        await loadSessions(false);
      } catch (e) {
        setErr(apiErrorMessage(e));
      }
    },
    [loadSessions],
  );

  const latestAssistantCitations =
    messages
      .slice()
      .reverse()
      .find((m) => m.role === "assistant" && m.citations.length > 0)?.citations ?? [];

  const latestAnswerConfidence = useMemo(() => {
    const m = messages.slice().reverse().find((x) => x.role === "assistant");
    if (!m) return null;
    const raw = (confidenceById[m.id] ?? m.confidence ?? "").toString().trim();
    return raw || null;
  }, [messages, confidenceById]);

  const openCitationDetail = useCallback(
    (c: Citation) => {
      setSelectedCitation(c);
      if (!sourcesPinned) setSourcesDrawerOpen(true);
    },
    [sourcesPinned],
  );

  function fmtWhen(iso: string) {
    const d = new Date(iso);
    return d.toLocaleString([], { hour: "2-digit", minute: "2-digit" });
  }

  const historyGroups = useMemo(() => {
    const pinnedList: ChatSession[] = [];
    const today: ChatSession[] = [];
    const yesterday: ChatSession[] = [];
    const lastWeek: ChatSession[] = [];
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfYesterday = new Date(startOfToday);
    startOfYesterday.setDate(startOfYesterday.getDate() - 1);
    sessions.forEach((s) => {
      if (s.pinned) {
        pinnedList.push(s);
        return;
      }
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
        lastWeek.push(s);
      }
    });
    return { pinned: pinnedList, today, yesterday, lastWeek };
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

  const sessionRow = (s: ChatSession, timeLabel: string) => (
    <div key={s.id} className={`skc-history-item-row ${activeSessionId === s.id ? "on" : ""}`}>
      <button type="button" className="skc-history-item" onClick={() => setActiveSessionId(s.id)}>
        <div className="skc-history-q">{s.title || "Untitled conversation"}</div>
        <div className="skc-history-m">{timeLabel}</div>
      </button>
      <div className="skc-history-menu-root" data-sk-history-menu>
        <button
          type="button"
          className="skc-history-menu-trigger"
          title="More actions"
          aria-label="Conversation actions"
          aria-expanded={historyMenuAnchor?.sessionId === s.id}
          aria-haspopup="menu"
          onClick={(e) => {
            e.stopPropagation();
            const btn = e.currentTarget;
            const rect = btn.getBoundingClientRect();
            setHistoryMenuAnchor((prev) =>
              prev?.sessionId === s.id
                ? null
                : {
                    sessionId: s.id,
                    top: rect.bottom + 4,
                    right: window.innerWidth - rect.right,
                  },
            );
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <circle cx="12" cy="5" r="2" />
            <circle cx="12" cy="12" r="2" />
            <circle cx="12" cy="19" r="2" />
          </svg>
        </button>
        {historyMenuAnchor?.sessionId === s.id && (
          <div
            className="skc-history-menu-dropdown"
            style={{
              position: "fixed",
              top: historyMenuAnchor.top,
              right: historyMenuAnchor.right,
              zIndex: 100,
            }}
            role="menu"
            data-sk-history-menu
          >
            <button
              type="button"
              role="menuitem"
              className="skc-history-menu-item"
              onClick={(e) => {
                e.stopPropagation();
                setHistoryMenuAnchor(null);
                void togglePinSession(s);
              }}
            >
              {s.pinned ? "Unpin" : "Pin"}
            </button>
            <button
              type="button"
              role="menuitem"
              className="skc-history-menu-item"
              disabled={pdfBusyId === s.id}
              onClick={(e) => {
                e.stopPropagation();
                setHistoryMenuAnchor(null);
                void exportSessionPdf(s.id);
              }}
            >
              {pdfBusyId === s.id ? "Exporting PDF…" : "Export PDF"}
            </button>
            <button
              type="button"
              role="menuitem"
              className="skc-history-menu-item"
              onClick={(e) => {
                e.stopPropagation();
                setHistoryMenuAnchor(null);
                void renameSession(s);
              }}
            >
              Rename
            </button>
            <button
              type="button"
              role="menuitem"
              className="skc-history-menu-item skc-history-menu-item--danger"
              onClick={(e) => {
                e.stopPropagation();
                setHistoryMenuAnchor(null);
                void deleteChatSession(s.id);
              }}
            >
              Delete
            </button>
          </div>
        )}
      </div>
    </div>
  );

  function renderAssistantMessage(m: ChatMessage) {
    return (
      <div className="skc-assistant">
        <div className="skc-assistant-avatar">⬢</div>
        <div className="skc-assistant-body">
          <div className="skc-assistant-text">
            {m.content}
            {m.citations.length > 0 && (
              <div className="skc-inline-citations">
                {m.citations.map((c, i) => (
                  <button key={`${c.chunk_id}-${i}`} type="button" className="skc-citation-pill" onClick={() => openCitationDetail(c)}>
                    📄 {c.document_filename} {c.page_number != null ? `· p.${c.page_number}` : ""}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="skc-assistant-footer">
            <div className="skc-answer-meta">
              {(() => {
                const confRaw = (confidenceById[m.id] ?? m.confidence ?? "").toString().trim();
                const confLc = confRaw.toLowerCase();
                const confPretty = confRaw
                  ? confRaw.charAt(0).toUpperCase() + confRaw.slice(1).toLowerCase()
                  : "Unknown";
                const modeKey = generationModeById[m.id] ?? m.generation_mode ?? "unknown";
                const modelRaw = (generationModelById[m.id] ?? m.generation_model ?? "").toString().trim();
                return (
                  <>
                    <div className={confidenceClass(confLc || "unknown")}>{confPretty} confidence</div>
                    <span className="skc-source-chip" title="Answer generation mode and model">
                      {generationModeWithModelLabel(modeKey, modelRaw || undefined)}
                    </span>
                  </>
                );
              })()}
            </div>
            <div
              className={`skc-assistant-footer-actions${feedbackSavedFlashByMsg[m.id] ? " skc-assistant-footer-actions--saved" : ""}`}
            >
              <button
                type="button"
                className={`skc-icon-btn${copyAckByMsg[m.id] ? " skc-icon-btn--copied" : ""}`}
                disabled={Boolean(copyAckByMsg[m.id])}
                title={copyAckByMsg[m.id] ? "Copied to clipboard" : "Copy answer to clipboard"}
                aria-label={copyAckByMsg[m.id] ? "Copied" : "Copy answer to clipboard"}
                onClick={() => copyAnswerToClipboard(m.id, m.content)}
              >
                {copyAckByMsg[m.id] ? <IconCheckSmall /> : <IconCopyAnswer />}
              </button>
              <button
                type="button"
                className={`skc-icon-btn ${feedbackByMsg[m.id] === "up" ? "on" : ""}${feedbackBusyByMsg[m.id] ? " skc-icon-btn--busy" : ""}`}
                disabled={Boolean(feedbackBusyByMsg[m.id])}
                title={
                  feedbackBusyByMsg[m.id]
                    ? "Saving feedback…"
                    : feedbackByMsg[m.id] === "up"
                      ? "Remove helpful vote"
                      : "Mark as helpful"
                }
                aria-label={feedbackBusyByMsg[m.id] ? "Saving feedback" : feedbackByMsg[m.id] === "up" ? "Remove helpful vote" : "Mark as helpful"}
                aria-busy={Boolean(feedbackBusyByMsg[m.id])}
                aria-pressed={feedbackByMsg[m.id] === "up"}
                onClick={() => void setMessageFeedback(m.id, feedbackByMsg[m.id] === "up" ? null : "up")}
              >
                👍
              </button>
              <button
                type="button"
                className={`skc-icon-btn ${feedbackByMsg[m.id] === "down" ? "on" : ""}${feedbackBusyByMsg[m.id] ? " skc-icon-btn--busy" : ""}`}
                disabled={Boolean(feedbackBusyByMsg[m.id])}
                title={
                  feedbackBusyByMsg[m.id]
                    ? "Saving feedback…"
                    : feedbackByMsg[m.id] === "down"
                      ? "Remove not helpful vote"
                      : "Mark as not helpful"
                }
                aria-label={feedbackBusyByMsg[m.id] ? "Saving feedback" : feedbackByMsg[m.id] === "down" ? "Remove not helpful vote" : "Mark as not helpful"}
                aria-busy={Boolean(feedbackBusyByMsg[m.id])}
                aria-pressed={feedbackByMsg[m.id] === "down"}
                onClick={() => void setMessageFeedback(m.id, feedbackByMsg[m.id] === "down" ? null : "down")}
              >
                👎
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  function renderStreamingAssistant() {
    return (
      <div className="skc-assistant skc-assistant--streaming">
        <div className="skc-assistant-avatar">⬢</div>
        <div className="skc-assistant-body">
          <div className="skc-assistant-text">{streamText}</div>
        </div>
      </div>
    );
  }

  const turnBlocks: ReactNode[] = [];
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === "user") {
      const next = messages[i + 1];
      const asst = next?.role === "assistant" ? next : null;
      const streamHere = Boolean(streaming && streamText && !asst);
      turnBlocks.push(
        <div key={`turn-${m.id}`} className="skc-turn">
          <div className="skc-user-row">
            <div className="skc-user-bubble">{m.content}</div>
          </div>
          {asst ? renderAssistantMessage(asst) : null}
          {streamHere ? renderStreamingAssistant() : null}
        </div>,
      );
      if (asst) i += 1;
    } else {
      turnBlocks.push(
        <div key={`turn-${m.id}`} className="skc-turn skc-turn--orphan">
          {renderAssistantMessage(m)}
        </div>,
      );
    }
  }

  return (
    <div
      className={`skc-frame${embedded ? " skc-frame--embedded" : ""}${embedded && embeddedBright ? " skc-frame--bright" : ""}${!showHistoryMenu ? " skc-frame--chat-only" : ""}${sourcesPinned ? " skc-frame--sources-pinned" : ""}`}
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
          <div className="skc-history-list">
            {historyGroups.pinned.length > 0 && (
              <>
                <div className="skc-group-label">Pinned</div>
                {historyGroups.pinned.map((s) =>
                  sessionRow(
                    s,
                    new Date(s.updated_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }),
                  ),
                )}
              </>
            )}
            <div className="skc-group-label">Today</div>
            {historyGroups.today.map((s) => sessionRow(s, fmtWhen(s.updated_at)))}
            {historyGroups.yesterday.length > 0 && <div className="skc-group-label">Yesterday</div>}
            {historyGroups.yesterday.map((s) => sessionRow(s, new Date(s.updated_at).toLocaleDateString()))}
            {historyGroups.lastWeek.length > 0 && <div className="skc-group-label">Last week</div>}
            {historyGroups.lastWeek.map((s) => sessionRow(s, new Date(s.updated_at).toLocaleDateString()))}
          </div>
          <div className="skc-history-bottom">
            <div className="skc-group-label skc-group-label--section">Account</div>
            <div className="skc-account-card">
              <div className="skc-account-avatar">{user?.email?.slice(0, 2).toUpperCase() || "U"}</div>
              <div className="skc-account-meta">
                <div className="skc-account-email skc-account-email--primary">{user?.email || "…"}</div>
                <div className="skc-account-role">{accountRoleSubtitle(user, chatOnlyMode)}</div>
              </div>
            </div>
            {!chatOnlyMode && (
              <>
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
              </>
            )}
          </div>
        </aside>
      )}

      <main className="skc-main">
        <div className="skc-thread">
          <div className="skc-thread-surface">
            {chatOnlyMode && (
              <div className="skc-thread-trust" role="status">
                <span className="skc-sources-trust-banner skc-sources-trust-banner--compact" title="Answers use retrieved workspace documents only.">
                  ● Uses approved workspace knowledge only
                </span>
              </div>
            )}
            <div className="skc-messages" ref={messagesScrollRef}>
              {err && <p className="sk-error">{err}</p>}
              {showEmpty && (
                <div className="skc-assistant skc-assistant--welcome">
                  <div className="skc-assistant-avatar">⬢</div>
                  <div className="skc-assistant-body">
                    <div className="skc-assistant-text">
                      <div className="skc-welcome">
                        <div className="skc-welcome-eyebrow">{chatOnlyMode ? "MEMBER CHAT HOME" : "CHAT HOME"}</div>
                        <div className="skc-welcome-title">How can I help you today?</div>
                        <p className="skc-welcome-lede">
                          I can help you find answers, summarize documents, and pull together information from your workspace
                          faster. Every response is grounded in your organization’s approved knowledge.
                        </p>
                      </div>
                      <div className="skc-welcome-chips-label">Try one of these:</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {suggestedPrompts.map((s) => (
                          <button key={s} type="button" className="skc-citation-pill" onClick={() => setInput(s)}>
                            {s}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {turnBlocks}
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
                {chatOnlyMode && (
                  <div className="skc-composer-scope" aria-hidden>
                    <span className="skc-scope-pill">Workspace knowledge</span>
                  </div>
                )}
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
                  <div className="skc-composer-footer-left">
                    <div className="skc-hint-chip">{sessions.length} chats</div>
                    {latestAssistantCitations.length > 0 && !sourcesPinned && (
                      <button
                        type="button"
                        className="skc-hint-chip skc-hint-chip--action"
                        onClick={() => setSourcesDrawerOpen(true)}
                      >
                        Sources · {latestAssistantCitations.length}
                      </button>
                    )}
                    <button
                      type="button"
                      className="skc-composer-attach-btn"
                      disabled={uploadBusy}
                      aria-label={uploadBusy ? "Uploading files" : "Attach files"}
                      title={uploadBusy ? "Uploading…" : "Attach files"}
                      onClick={() => chatUploadInputRef.current?.click()}
                    >
                      <svg
                        className="skc-composer-attach-icon"
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden
                      >
                        <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                      </svg>
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
          </div>
        </div>
      </main>
      {sourcesPinned ? (
        <div className="skc-sources-dock">
          <ChatSourcesPanel
            citations={latestAssistantCitations}
            selected={selectedCitation}
            onSelect={(c) => setSelectedCitation(c)}
            answerConfidence={latestAnswerConfidence}
            variant="dock"
            onUnpin={() => setSourcesPinned(false)}
          />
        </div>
      ) : (
        <>
          <div
            className={`skc-sources-drawer-backdrop${sourcesDrawerOpen ? " skc-sources-drawer-backdrop--open" : ""}`}
            aria-hidden={!sourcesDrawerOpen}
            onClick={() => setSourcesDrawerOpen(false)}
          />
          <div className={`skc-sources-drawer${sourcesDrawerOpen ? " skc-sources-drawer--open" : ""}`} aria-hidden={!sourcesDrawerOpen}>
            <ChatSourcesPanel
              citations={latestAssistantCitations}
              selected={selectedCitation}
              onSelect={(c) => setSelectedCitation(c)}
              onClose={() => setSourcesDrawerOpen(false)}
              answerConfidence={latestAnswerConfidence}
              variant="drawer"
              onPin={() => {
                setSourcesPinned(true);
                setSourcesDrawerOpen(false);
              }}
            />
          </div>
        </>
      )}
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
