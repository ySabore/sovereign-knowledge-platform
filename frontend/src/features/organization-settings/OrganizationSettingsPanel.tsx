import { type CSSProperties, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { fetchPublicConfig } from "../../lib/publicConfig";
import { useOrgShellTokens } from "../../context/OrgShellThemeContext";

type Org = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description?: string | null;
  preferred_chat_provider?: string | null;
  preferred_chat_model?: string | null;
  openai_api_key_configured?: boolean;
  anthropic_api_key_configured?: boolean;
  cohere_api_key_configured?: boolean;
  openai_api_base_url?: string | null;
  anthropic_api_base_url?: string | null;
  ollama_base_url?: string | null;
  retrieval_strategy?: string | null;
  use_hosted_rerank?: boolean;
  allowed_connector_ids?: string[] | null;
};
type ConnectorCatalogItem = { id: string; name: string; emoji: string; description: string };
type BillingPlanSummary = { plan: string; connectors_max: number };

type OrgChatProvider = "" | "extractive" | "ollama" | "openai" | "anthropic";
type OrgRetrievalStrategy = "" | "heuristic" | "hybrid" | "rerank";

function orgChatProviderFromApi(v: string | null | undefined): OrgChatProvider {
  if (v === "extractive" || v === "ollama" || v === "openai" || v === "anthropic") return v;
  return "";
}

function orgRetrievalStrategyFromApi(v: string | null | undefined): OrgRetrievalStrategy {
  if (v === "heuristic" || v === "hybrid" || v === "rerank") return v;
  return "";
}

function Btn({
  children, variant = "primary", onClick, disabled, style, htmlType = "button",
}: {
  children: React.ReactNode;
  variant?: "primary" | "ghost" | "danger";
  onClick?: () => void;
  disabled?: boolean;
  style?: React.CSSProperties;
  htmlType?: "button" | "submit";
}) {
  const C = useOrgShellTokens();
  const base: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", gap: 5, padding: "6px 13px",
    borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: C.sans, transition: "all .14s", opacity: disabled ? 0.5 : 1, border: "none",
  };
  const styles: Record<string, React.CSSProperties> = {
    primary: { background: C.accent, color: "white", boxShadow: `0 0 16px ${C.accentG}` },
    ghost: { background: "transparent", color: C.t2, border: `1px solid ${C.bd2}` },
    danger: { background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.25)" },
  };
  return (
    <button
      type={htmlType}
      style={{ ...base, ...styles[variant], ...style }}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

function Input({
  value, onChange, placeholder, required, disabled, style, type,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  style?: React.CSSProperties;
  type?: "text" | "password";
}) {
  const C = useOrgShellTokens();
  return (
    <input
      type={type ?? "text"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      style={{
        background: C.bgCard, border: `1px solid ${C.bd}`, borderRadius: 7,
        padding: "7px 10px", fontSize: 12, color: C.t1, fontFamily: C.sans,
        outline: "none", width: "100%", opacity: disabled ? 0.55 : 1, ...style,
      }}
    />
  );
}

function OrgSettingsCollapsible({
  title,
  subtitle,
  defaultOpen = true,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const C = useOrgShellTokens();
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div
      style={{
        background: C.bgCard,
        border: `1px solid ${C.bd}`,
        borderRadius: 14,
        overflow: "hidden",
        marginBottom: 10,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          padding: "14px 18px",
          background: open ? "rgba(37,99,235,0.06)" : "transparent",
          border: "none",
          cursor: "pointer",
          fontFamily: C.sans,
          textAlign: "left",
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: C.t1 }}>{title}</div>
          {subtitle ? <div style={{ fontSize: 11, color: C.t3, marginTop: 2 }}>{subtitle}</div> : null}
        </div>
        <span style={{ fontSize: 11, color: C.t2, flexShrink: 0 }}>{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div style={{ padding: "8px 18px 18px", borderTop: `1px solid ${C.bd}` }}>{children}</div>
      ) : null}
    </div>
  );
}

export function OrganizationSettingsPanel({
  org,
  onSaved,
  showDangerZone,
  onOrgDeleted,
  canManageCloudCredentials,
}: {
  org: Org;
  onSaved: (org: Org) => void;
  showDangerZone?: boolean;
  onOrgDeleted?: () => void | Promise<void>;
  canManageCloudCredentials?: boolean;
}) {
  const C = useOrgShellTokens();
  const [name, setName] = useState(org.name);
  const [status, setStatus] = useState(org.status);
  const [description, setDescription] = useState(org.description ?? "");
  const [chatProv, setChatProv] = useState<OrgChatProvider>(orgChatProviderFromApi(org.preferred_chat_provider));
  const [chatModel, setChatModel] = useState(org.preferred_chat_model ?? "");
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState(org.ollama_base_url ?? "");
  const [retrievalStrat, setRetrievalStrat] = useState<OrgRetrievalStrategy>(
    orgRetrievalStrategyFromApi(org.retrieval_strategy),
  );
  const [useHostedRerank, setUseHostedRerank] = useState(Boolean(org.use_hosted_rerank));
  const [cohereRerankAvailable, setCohereRerankAvailable] = useState(false);
  const [connectorCatalog, setConnectorCatalog] = useState<ConnectorCatalogItem[]>([]);
  const [allowedConnectorIds, setAllowedConnectorIds] = useState<string[]>(
    Array.isArray(org.allowed_connector_ids) ? org.allowed_connector_ids : [],
  );
  const [connectorMax, setConnectorMax] = useState<number | null>(null);
  const [connectorPlan, setConnectorPlan] = useState<string | null>(null);
  const [connectorLimitMsg, setConnectorLimitMsg] = useState<string | null>(null);
  const cohereRerankEffective = useMemo(
    () => cohereRerankAvailable || Boolean(org.cohere_api_key_configured),
    [cohereRerankAvailable, org.cohere_api_key_configured],
  );
  const [openaiKeyDraft, setOpenaiKeyDraft] = useState("");
  const [anthropicKeyDraft, setAnthropicKeyDraft] = useState("");
  const [cohereKeyDraft, setCohereKeyDraft] = useState("");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState(org.openai_api_base_url ?? "");
  const [anthropicBaseUrl, setAnthropicBaseUrl] = useState(org.anthropic_api_base_url ?? "");
  const [clearOpenaiKey, setClearOpenaiKey] = useState(false);
  const [clearAnthropicKey, setClearAnthropicKey] = useState(false);
  const [clearCohereKey, setClearCohereKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [delSlug, setDelSlug] = useState("");
  const [delBusy, setDelBusy] = useState(false);
  const [delErr, setDelErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchPublicConfig(true)
      .then((cfg) => {
        if (cancelled) return;
        const f = cfg.features as { cohere_rerank?: boolean } | undefined;
        setCohereRerankAvailable(Boolean(f?.cohere_rerank));
        const rawCatalog = Array.isArray(cfg.connector_catalog) ? cfg.connector_catalog : [];
        const normalizedCatalog = rawCatalog
          .map((item) => ({
            id: String(item.id || "").trim().toLowerCase(),
            name: String(item.name || "").trim(),
            emoji: String(item.emoji || "🔌"),
            description: String(item.description || ""),
          }))
          .filter((item) => item.id.length > 0 && item.name.length > 0);
        setConnectorCatalog(normalizedCatalog);
      })
      .catch(() => {
        if (!cancelled) {
          setCohereRerankAvailable(false);
          setConnectorCatalog([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void api
      .get<BillingPlanSummary>(`/organizations/${org.id}/billing/plan`)
      .then(({ data }) => {
        if (cancelled) return;
        setConnectorMax(Number.isFinite(data.connectors_max) ? Number(data.connectors_max) : null);
        setConnectorPlan(String(data.plan || "").trim().toLowerCase() || null);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setConnectorMax(null);
        setConnectorPlan(null);
      });
    return () => {
      cancelled = true;
    };
  }, [org.id]);

  useEffect(() => {
    setName(org.name);
    setStatus(org.status);
    setDescription(org.description ?? "");
    setChatProv(orgChatProviderFromApi(org.preferred_chat_provider));
    setChatModel(org.preferred_chat_model ?? "");
    setOllamaBaseUrl(org.ollama_base_url ?? "");
    setRetrievalStrat(orgRetrievalStrategyFromApi(org.retrieval_strategy));
    setUseHostedRerank(Boolean(org.use_hosted_rerank));
    setOpenaiBaseUrl(org.openai_api_base_url ?? "");
    setAnthropicBaseUrl(org.anthropic_api_base_url ?? "");
    setAllowedConnectorIds(Array.isArray(org.allowed_connector_ids) ? org.allowed_connector_ids : []);
    setConnectorLimitMsg(null);
    setOpenaiKeyDraft("");
    setAnthropicKeyDraft("");
    setCohereKeyDraft("");
    setClearOpenaiKey(false);
    setClearAnthropicKey(false);
    setClearCohereKey(false);
    setErr(null);
    setOk(null);
    setDelSlug("");
    setDelErr(null);
  }, [
    org.id,
    org.name,
    org.status,
    org.description,
    org.preferred_chat_provider,
    org.preferred_chat_model,
    org.ollama_base_url,
    org.retrieval_strategy,
    org.use_hosted_rerank,
    org.openai_api_base_url,
    org.anthropic_api_base_url,
    org.allowed_connector_ids,
    org.openai_api_key_configured,
    org.anthropic_api_key_configured,
    org.cohere_api_key_configured,
  ]);

  const selectStyle: CSSProperties = {
    width: "100%",
    background: C.bgE,
    border: `1px solid ${C.bd}`,
    borderRadius: 8,
    padding: "7px 10px",
    fontSize: 12,
    color: C.t1,
    fontFamily: C.sans,
    outline: "none",
    boxSizing: "border-box",
  };

  function resetForm() {
    setName(org.name);
    setStatus(org.status);
    setDescription(org.description ?? "");
    setChatProv(orgChatProviderFromApi(org.preferred_chat_provider));
    setChatModel(org.preferred_chat_model ?? "");
    setOllamaBaseUrl(org.ollama_base_url ?? "");
    setRetrievalStrat(orgRetrievalStrategyFromApi(org.retrieval_strategy));
    setUseHostedRerank(Boolean(org.use_hosted_rerank));
    setOpenaiBaseUrl(org.openai_api_base_url ?? "");
    setAnthropicBaseUrl(org.anthropic_api_base_url ?? "");
    setAllowedConnectorIds(Array.isArray(org.allowed_connector_ids) ? org.allowed_connector_ids : []);
    setConnectorLimitMsg(null);
    setOpenaiKeyDraft("");
    setAnthropicKeyDraft("");
    setCohereKeyDraft("");
    setClearOpenaiKey(false);
    setClearAnthropicKey(false);
    setClearCohereKey(false);
    setErr(null);
    setOk(null);
  }

  const hasChanges = useMemo(() => {
    const sameNormalized = (a: string | null | undefined, b: string | null | undefined) =>
      (a || "").trim() === (b || "").trim();
    const selectedNow = [...allowedConnectorIds].sort();
    const selectedOriginal = [...(Array.isArray(org.allowed_connector_ids) ? org.allowed_connector_ids : [])].sort();
    const connectorsChanged =
      selectedNow.length !== selectedOriginal.length ||
      selectedNow.some((id, idx) => id !== selectedOriginal[idx]);

    return (
      !sameNormalized(name, org.name) ||
      !sameNormalized(status.toLowerCase(), org.status) ||
      !sameNormalized(description, org.description || "") ||
      !sameNormalized(chatProv, org.preferred_chat_provider || "") ||
      !sameNormalized(chatModel, org.preferred_chat_model || "") ||
      !sameNormalized(ollamaBaseUrl, org.ollama_base_url || "") ||
      !sameNormalized(retrievalStrat, org.retrieval_strategy || "") ||
      Boolean(useHostedRerank) !== Boolean(org.use_hosted_rerank) ||
      !sameNormalized(openaiBaseUrl, org.openai_api_base_url || "") ||
      !sameNormalized(anthropicBaseUrl, org.anthropic_api_base_url || "") ||
      Boolean(openaiKeyDraft.trim()) ||
      Boolean(anthropicKeyDraft.trim()) ||
      Boolean(cohereKeyDraft.trim()) ||
      clearOpenaiKey ||
      clearAnthropicKey ||
      clearCohereKey ||
      connectorsChanged
    );
  }, [
    allowedConnectorIds,
    anthropicBaseUrl,
    anthropicKeyDraft,
    chatModel,
    chatProv,
    clearAnthropicKey,
    clearCohereKey,
    clearOpenaiKey,
    cohereKeyDraft,
    description,
    name,
    ollamaBaseUrl,
    openaiBaseUrl,
    openaiKeyDraft,
    org.allowed_connector_ids,
    org.anthropic_api_base_url,
    org.description,
    org.name,
    org.ollama_base_url,
    org.openai_api_base_url,
    org.preferred_chat_model,
    org.preferred_chat_provider,
    org.retrieval_strategy,
    org.status,
    org.use_hosted_rerank,
    retrievalStrat,
    status,
    useHostedRerank,
  ]);

  async function save() {
    setSaving(true);
    setErr(null);
    setOk(null);
    try {
      if (connectorMax !== null && allowedConnectorIds.length > connectorMax) {
        setErr(`Connector limit reached for ${connectorPlan || "current"} plan (${connectorMax}).`);
        setSaving(false);
        return;
      }
      const patch: Record<string, unknown> = {
        name: name.trim(),
        status: status.trim().toLowerCase(),
        description: description.trim() || null,
        preferred_chat_provider: chatProv === "" ? null : chatProv,
        preferred_chat_model: chatModel.trim() || null,
        ollama_base_url: ollamaBaseUrl.trim() || null,
        retrieval_strategy: retrievalStrat === "" ? null : retrievalStrat,
        use_hosted_rerank: useHostedRerank,
        allowed_connector_ids: allowedConnectorIds.length > 0 ? allowedConnectorIds : null,
      };
      if (canManageCloudCredentials) {
        if (clearOpenaiKey) patch.openai_api_key = null;
        else if (openaiKeyDraft.trim()) patch.openai_api_key = openaiKeyDraft.trim();
        if (clearAnthropicKey) patch.anthropic_api_key = null;
        else if (anthropicKeyDraft.trim()) patch.anthropic_api_key = anthropicKeyDraft.trim();
        if (clearCohereKey) patch.cohere_api_key = null;
        else if (cohereKeyDraft.trim()) patch.cohere_api_key = cohereKeyDraft.trim();
        patch.openai_api_base_url = openaiBaseUrl.trim() || null;
        patch.anthropic_api_base_url = anthropicBaseUrl.trim() || null;
      }

      const { data } = await api.patch<Org>(`/organizations/${org.id}`, patch);
      onSaved({ ...org, ...data });
      setOpenaiKeyDraft("");
      setAnthropicKeyDraft("");
      setCohereKeyDraft("");
      setClearOpenaiKey(false);
      setClearAnthropicKey(false);
      setClearCohereKey(false);
      setOk("Saved.");
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontFamily: C.serif, fontSize: 20, color: C.t1, marginBottom: 4 }}>Organization settings</div>
        <div style={{ fontSize: 12, color: C.t2 }}>
          Profile, description, and optional chat model overrides for this organization.
        </div>
      </div>

      <OrgSettingsCollapsible title="Profile" subtitle="Name, status, and URL slug" defaultOpen>
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Name
            </div>
            <Input value={name} onChange={setName} placeholder="Organization name" />
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Status
            </div>
            <select value={status} onChange={(e) => setStatus(e.target.value)} style={selectStyle}>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Slug
            </div>
            <div style={{ fontSize: 12, color: C.t2, fontFamily: C.mono }}>/{org.slug}</div>
            <div style={{ fontSize: 10, color: C.t3, marginTop: 4 }}>Slug is read-only. Contact support to change it.</div>
          </div>
        </div>
      </OrgSettingsCollapsible>

      <OrgSettingsCollapsible
        title="About this organization"
        subtitle="Mission, context, and who this org serves"
        defaultOpen={false}
      >
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
            Description
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the organization's purpose, teams, and how you use the knowledge base."
            rows={5}
            style={{
              width: "100%",
              background: C.bgE,
              border: `1px solid ${C.bd}`,
              borderRadius: 8,
              padding: "10px 12px",
              fontSize: 12,
              color: C.t1,
              fontFamily: C.sans,
              resize: "vertical",
              outline: "none",
              boxSizing: "border-box",
              lineHeight: 1.6,
            }}
          />
        </div>
      </OrgSettingsCollapsible>

      <OrgSettingsCollapsible
        title="Connector access"
        subtitle="Choose which platform connectors this organization can add to workspaces"
        defaultOpen={false}
      >
        {connectorMax !== null && (
          <div style={{ fontSize: 11, color: C.t2 }}>
            Plan limit: up to <strong style={{ color: C.t1 }}>{connectorMax}</strong> enabled connector
            {connectorMax === 1 ? "" : "s"}
            {connectorPlan ? <> on <strong style={{ color: C.t1 }}>{connectorPlan}</strong></> : null}.
          </div>
        )}
        <div style={{ fontSize: 11, color: C.t2 }}>
          Selected:{" "}
          <strong style={{ color: C.t1 }}>
            {allowedConnectorIds.length}/{connectorMax ?? connectorCatalog.length}
          </strong>
        </div>
        <div style={{ display: "grid", gap: 10 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: C.t2 }}>
            <input
              type="checkbox"
              checked={allowedConnectorIds.length === 0}
              disabled={connectorMax !== null && connectorCatalog.length > connectorMax}
              onChange={(e) => {
                if (e.target.checked) {
                  if (connectorMax !== null && connectorCatalog.length > connectorMax) {
                    setConnectorLimitMsg(
                      `Your plan allows up to ${connectorMax} connectors. Select up to ${connectorMax} from the list.`,
                    );
                    return;
                  }
                  setAllowedConnectorIds([]);
                  setConnectorLimitMsg(null);
                }
              }}
            />
            Allow all platform connectors
          </label>
          <div style={{ fontSize: 10, color: C.t3 }}>
            When this is off, org/workspace admins only see the selected connectors in the Add Connector modal.
          </div>
          {connectorLimitMsg ? (
            <div
              style={{
                border: "1px solid rgba(239,68,68,0.35)",
                background: "rgba(239,68,68,0.08)",
                color: "#fca5a5",
                borderRadius: 8,
                padding: "8px 10px",
                fontSize: 11,
                lineHeight: 1.45,
              }}
            >
              {connectorLimitMsg}
            </div>
          ) : null}
          {connectorCatalog.length === 0 ? (
            <div style={{ fontSize: 11, color: C.t3 }}>Connector catalog is unavailable right now.</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }}>
              {connectorCatalog.map((item) => {
                const checked = allowedConnectorIds.includes(item.id);
                return (
                  <label
                    key={item.id}
                    style={{
                      display: "flex",
                      gap: 8,
                      alignItems: "flex-start",
                      border: `1px solid ${C.bd}`,
                      background: C.bgE,
                      borderRadius: 10,
                      padding: "8px 10px",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => {
                        setAllowedConnectorIds((prev) => {
                          if (e.target.checked) {
                            if (connectorMax !== null && prev.length >= connectorMax) {
                              setConnectorLimitMsg(
                                `Plan limit reached (${connectorMax}). Upgrade plan or uncheck another connector.`,
                              );
                              return prev;
                            }
                            setConnectorLimitMsg(null);
                            return [...prev, item.id];
                          }
                          setConnectorLimitMsg(null);
                          return prev.filter((id) => id !== item.id);
                        });
                      }}
                    />
                    <span style={{ minWidth: 0 }}>
                      <span style={{ fontSize: 12, color: C.t1, fontWeight: 600 }}>
                        {item.emoji} {item.name}
                      </span>
                      <span style={{ display: "block", fontSize: 10, color: C.t3, marginTop: 2, lineHeight: 1.35 }}>
                        {item.description}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </OrgSettingsCollapsible>

      <OrgSettingsCollapsible
        title="Chat & LLM"
        subtitle="Self-hosted Ollama first; cloud providers need API keys (platform or per-org)"
        defaultOpen={false}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}>
          <div
            style={{
              fontSize: 11,
              color: C.t2,
              lineHeight: 1.55,
              padding: "12px 14px",
              borderRadius: 10,
              background: "rgba(34,197,94,0.06)",
              border: "1px solid rgba(34,197,94,0.2)",
            }}
          >
            <strong style={{ color: C.t1 }}>Local / GPU</strong>: set{" "}
            <span style={{ fontFamily: C.mono }}>ANSWER_GENERATION_PROVIDER=ollama</span> and matching{" "}
            <span style={{ fontFamily: C.mono }}>EMBEDDING_OLLAMA_BASE_URL</span> on the API host. Org override below can point
            this org at a different Ollama URL (e.g. <span style={{ fontFamily: C.mono }}>http://host.docker.internal:11434</span>
            ). Retrieval remains <strong>Postgres + pgvector</strong>.
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Answer provider
            </div>
            <select
              value={chatProv}
              onChange={(e) => setChatProv(e.target.value as OrgChatProvider)}
              style={selectStyle}
            >
              <option value="">Use platform default</option>
              <option value="ollama">Ollama (self-hosted LLM)</option>
              <option value="extractive">Extractive (quotes only, no LLM)</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Chat model override
            </div>
            <Input
              value={chatModel}
              onChange={setChatModel}
              placeholder={
                chatProv === "openai"
                  ? "e.g. gpt-4o-mini"
                  : chatProv === "anthropic"
                    ? "e.g. claude-3-5-haiku-20241022"
                    : "e.g. llama3.2, qwen3:32b"
              }
              disabled={chatProv === "extractive"}
            />
            <div style={{ fontSize: 10, color: C.t3, marginTop: 6, lineHeight: 1.45 }}>
              When the effective provider is Ollama, OpenAI, or Anthropic, this overrides the platform default model for that
              provider if set. Leave empty to use the server default (
              <span style={{ fontFamily: C.mono }}>ANSWER_GENERATION_MODEL</span>,{" "}
              <span style={{ fontFamily: C.mono }}>OPENAI_DEFAULT_CHAT_MODEL</span>, or{" "}
              <span style={{ fontFamily: C.mono }}>ANTHROPIC_DEFAULT_CHAT_MODEL</span>).
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Retrieval strategy (RAG)
            </div>
            <select
              value={retrievalStrat}
              onChange={(e) => setRetrievalStrat(e.target.value as OrgRetrievalStrategy)}
              style={selectStyle}
            >
              <option value="">Platform default (RETRIEVAL_STRATEGY_DEFAULT)</option>
              <option value="heuristic">Heuristic — pgvector + lexical rerank</option>
              <option value="hybrid">Hybrid — pgvector + keyword (FTS) + RRF</option>
              <option value="rerank">Rerank — pgvector + Cohere hosted rerank (fallback: lexical)</option>
            </select>
            <div style={{ fontSize: 10, color: C.t3, marginTop: 6, lineHeight: 1.45 }}>
              Hybrid improves keyword / number disambiguation (e.g. slide block labels). Requires DB migration adding{" "}
              <span style={{ fontFamily: C.mono }}>content_tsv</span> on chunks. Platform tuning:{" "}
              <span style={{ fontFamily: C.mono }}>RRF_K</span>, <span style={{ fontFamily: C.mono }}>RETRIEVAL_CANDIDATE_K</span>
              . Cohere rerank needs a platform <span style={{ fontFamily: C.mono }}>COHERE_API_KEY</span> or a per-org key (Cloud
              LLM credentials).
            </div>
            <label
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                marginTop: 10,
                cursor: retrievalStrat === "rerank" || !cohereRerankEffective ? "default" : "pointer",
                opacity: cohereRerankEffective ? 1 : 0.65,
              }}
            >
              <input
                type="checkbox"
                checked={retrievalStrat === "rerank" ? true : useHostedRerank}
                disabled={retrievalStrat === "rerank" || !cohereRerankEffective}
                onChange={(e) => setUseHostedRerank(e.target.checked)}
                style={{ marginTop: 2 }}
              />
              <span style={{ fontSize: 11, color: C.t2, lineHeight: 1.5 }}>
                <strong style={{ color: C.t1 }}>Cohere hosted rerank</strong> after heuristic or hybrid candidate retrieval
                (replaces lexical rerank for final ordering). Always on when retrieval strategy is &quot;Rerank&quot;.{" "}
                {!cohereRerankEffective ? (
                  <span style={{ color: C.t3 }}>
                    Not available: set <span style={{ fontFamily: C.mono }}>COHERE_API_KEY</span> or{" "}
                    <span style={{ fontFamily: C.mono }}>ORG_LLM_FERNET_KEY</span> and store a Cohere key below, then restart if
                    needed.
                  </span>
                ) : retrievalStrat === "rerank" ? (
                  <span style={{ color: C.t3 }}>Enabled by the Rerank strategy.</span>
                ) : null}
              </span>
            </label>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 6 }}>
              Ollama base URL (optional)
            </div>
            <Input
              value={ollamaBaseUrl}
              onChange={setOllamaBaseUrl}
              placeholder="e.g. http://127.0.0.1:11434 or http://host.docker.internal:11434"
              disabled={chatProv !== "ollama" && chatProv !== ""}
            />
            <div style={{ fontSize: 10, color: C.t3, marginTop: 6, lineHeight: 1.45 }}>
              Overrides <span style={{ fontFamily: C.mono }}>ANSWER_GENERATION_OLLAMA_BASE_URL</span> for chat generation when
              this org uses Ollama (or platform default is Ollama). The API process must reach this host. Leave empty to use the
              platform URL.
            </div>
          </div>
          <div
            style={{
              fontSize: 11,
              color: C.t2,
              lineHeight: 1.55,
              padding: "12px 14px",
              borderRadius: 10,
              background: "rgba(139,92,246,0.06)",
              border: "1px solid rgba(139,92,246,0.2)",
            }}
          >
            <strong style={{ color: C.t1 }}>OpenAI / Anthropic</strong>: requires a stored API key (platform owner → Cloud LLM
            credentials below) or platform env <span style={{ fontFamily: C.mono }}>OPENAI_API_KEY</span> /{" "}
            <span style={{ fontFamily: C.mono }}>ANTHROPIC_API_KEY</span>. Optional per-org API base URLs apply when set.{" "}
            <strong style={{ color: C.t1 }}>Cohere Rerank</strong>: optional per-org key in Cloud LLM credentials or platform{" "}
            <span style={{ fontFamily: C.mono }}>COHERE_API_KEY</span>.
          </div>
        </div>
      </OrgSettingsCollapsible>

      {canManageCloudCredentials ? (
        <OrgSettingsCollapsible
          title="Cloud LLM credentials"
          subtitle="Organization admins and platform owners — per-organization API keys and optional API bases"
          defaultOpen={false}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>
            <div style={{ fontSize: 11, color: C.t2, lineHeight: 1.55 }}>
              Store keys only when <span style={{ fontFamily: C.mono }}>ORG_LLM_FERNET_KEY</span> is set on the API. Keys are
              write-only; leave the password fields blank to keep the current stored key. Use "Remove stored key" to clear.
            </div>

            <div style={{ borderTop: `1px solid ${C.bd}`, paddingTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 8 }}>
                OpenAI
              </div>
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Key status:{" "}
                <strong style={{ color: C.t1 }}>
                  {clearOpenaiKey ? "will clear on save" : org.openai_api_key_configured ? "stored" : "none"}
                </strong>
              </div>
              <Input
                type="password"
                value={openaiKeyDraft}
                onChange={(v) => {
                  setOpenaiKeyDraft(v);
                  if (v.trim()) setClearOpenaiKey(false);
                }}
                placeholder="New API key (optional)"
              />
              <div style={{ marginTop: 8 }}>
                <Btn
                  variant="ghost"
                  disabled={saving || !org.openai_api_key_configured}
                  onClick={() => {
                    setClearOpenaiKey(true);
                    setOpenaiKeyDraft("");
                  }}
                >
                  Remove stored OpenAI key
                </Btn>
              </div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, margin: "12px 0 6px" }}>
                OpenAI API base URL
              </div>
              <Input
                value={openaiBaseUrl}
                onChange={setOpenaiBaseUrl}
                placeholder="https://api.openai.com/v1 (optional override)"
              />
            </div>

            <div style={{ borderTop: `1px solid ${C.bd}`, paddingTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 8 }}>
                Anthropic
              </div>
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Key status:{" "}
                <strong style={{ color: C.t1 }}>
                  {clearAnthropicKey ? "will clear on save" : org.anthropic_api_key_configured ? "stored" : "none"}
                </strong>
              </div>
              <Input
                type="password"
                value={anthropicKeyDraft}
                onChange={(v) => {
                  setAnthropicKeyDraft(v);
                  if (v.trim()) setClearAnthropicKey(false);
                }}
                placeholder="New API key (optional)"
              />
              <div style={{ marginTop: 8 }}>
                <Btn
                  variant="ghost"
                  disabled={saving || !org.anthropic_api_key_configured}
                  onClick={() => {
                    setClearAnthropicKey(true);
                    setAnthropicKeyDraft("");
                  }}
                >
                  Remove stored Anthropic key
                </Btn>
              </div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, margin: "12px 0 6px" }}>
                Anthropic API base URL
              </div>
              <Input
                value={anthropicBaseUrl}
                onChange={setAnthropicBaseUrl}
                placeholder="https://api.anthropic.com (optional override)"
              />
            </div>

            <div style={{ borderTop: `1px solid ${C.bd}`, paddingTop: 12 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.t3, marginBottom: 8 }}>
                Cohere (Rerank API)
              </div>
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8, lineHeight: 1.5 }}>
                Used for hosted rerank when retrieval uses <span style={{ fontFamily: C.mono }}>rerank</span> strategy or{" "}
                <span style={{ fontFamily: C.mono }}>Cohere hosted rerank</span> on heuristic/hybrid. Overrides platform{" "}
                <span style={{ fontFamily: C.mono }}>COHERE_API_KEY</span> when set. Model and timeouts still come from platform env.
              </div>
              <div style={{ fontSize: 11, color: C.t2, marginBottom: 8 }}>
                Key status:{" "}
                <strong style={{ color: C.t1 }}>
                  {clearCohereKey ? "will clear on save" : org.cohere_api_key_configured ? "stored" : "none"}
                </strong>
              </div>
              <Input
                type="password"
                value={cohereKeyDraft}
                onChange={(v) => {
                  setCohereKeyDraft(v);
                  if (v.trim()) setClearCohereKey(false);
                }}
                placeholder="New Cohere API key (optional)"
              />
              <div style={{ marginTop: 8 }}>
                <Btn
                  variant="ghost"
                  disabled={saving || !org.cohere_api_key_configured}
                  onClick={() => {
                    setClearCohereKey(true);
                    setCohereKeyDraft("");
                  }}
                >
                  Remove stored Cohere key
                </Btn>
              </div>
            </div>
          </div>
        </OrgSettingsCollapsible>
      ) : null}

      <div style={{ marginTop: 4 }}>
        {err ? <div style={{ fontSize: 11, color: C.red, marginBottom: 8 }}>✗ {err}</div> : null}
        {ok ? <div style={{ fontSize: 11, color: C.green, marginBottom: 8 }}>✓ {ok}</div> : null}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Btn variant="ghost" disabled={saving} onClick={resetForm}>
            Reset
          </Btn>
          <Btn variant="primary" disabled={saving || !name.trim() || !hasChanges} onClick={save}>
            {saving ? "Saving…" : "Save changes"}
          </Btn>
        </div>
      </div>

      {showDangerZone && onOrgDeleted && (
        <div
          style={{
            marginTop: 18,
            padding: "16px 18px",
            background: "rgba(239,68,68,0.06)",
            border: "1px solid rgba(239,68,68,0.28)",
            borderRadius: 14,
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: C.red, marginBottom: 8 }}>
            Danger zone
          </div>
          <div style={{ fontSize: 12, color: C.t2, lineHeight: 1.55, marginBottom: 12 }}>
            Delete this organization and all workspaces, indexed documents, chat history, and connectors. This cannot be undone.
          </div>
          <div style={{ fontSize: 10, fontWeight: 600, color: C.t3, marginBottom: 6 }}>
            Type slug <span style={{ fontFamily: C.mono, color: C.t1 }}>{org.slug}</span> to confirm
          </div>
          <Input value={delSlug} onChange={setDelSlug} placeholder={org.slug} style={{ maxWidth: 320, marginBottom: 10 }} />
          {delErr && <div style={{ fontSize: 11, color: C.red, marginBottom: 8 }}>{delErr}</div>}
          <Btn
            variant="ghost"
            disabled={delBusy}
            style={{ borderColor: "rgba(239,68,68,0.45)", color: C.red }}
            onClick={async () => {
              setDelErr(null);
              if (delSlug.trim().toLowerCase() !== org.slug.toLowerCase()) {
                setDelErr("Slug must match exactly.");
                return;
              }
              setDelBusy(true);
              try {
                await api.delete(`/organizations/${org.id}`, { params: { confirm_slug: delSlug.trim() } });
                setDelSlug("");
                await onOrgDeleted();
              } catch (e) {
                setDelErr(apiErrorMessage(e));
              } finally {
                setDelBusy(false);
              }
            }}
          >
            {delBusy ? "Deleting…" : "Delete organization"}
          </Btn>
        </div>
      )}
    </div>
  );
}
