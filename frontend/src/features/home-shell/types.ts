export type Org = {
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

export type Workspace = {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
};

export type Panel =
  | "platform"
  | "dashboard"
  | "orgs"
  | "workspaces"
  | "chats"
  | "team"
  | "connectors"
  | "docs"
  | "analytics"
  | "billing"
  | "audit"
  | "settings";

export type OrgScreen = "overview" | "settings";
export type NavigationScope = "platform" | "organization";
export type OrgChatProvider = "" | "extractive" | "ollama" | "openai" | "anthropic";
