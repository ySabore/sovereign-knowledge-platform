import type { Dispatch, FormEvent, SetStateAction } from "react";
import type {
  NavigationScope,
  Org,
  OrgChatProvider,
  OrgScreen,
  Panel,
  Workspace,
} from "./types";

export type UserSummary = {
  is_platform_owner?: boolean;
};

export type ApiClient = {
  get<T>(url: string): Promise<{ data: T }>;
};

export type OrgDetailViewProps = {
  org: Org;
  workspaces: Workspace[];
  loadingWs: boolean;
  onOpenSettings: () => void;
  onUploadClick: (ws: Workspace) => void;
  onWorkspaceCreated: (workspaceId?: string) => void;
  onGoToWorkspace: (workspaceId?: string) => void;
  onNavigateToWorkspaces: () => void;
  onNavigateToTeam: () => void;
  onNavigateToDocuments: () => void;
  onNavigateToConnectors: () => void;
};

export type AllWorkspacesPanelProps = {
  orgs: Org[];
  allWorkspaces: Workspace[];
  loadingWs: boolean;
  initialWsId?: string;
  isPlatformOwner: boolean;
  onWorkspaceDeleted: () => void | Promise<void>;
  onSelectedWorkspaceChange?: (workspaceId: string | null, workspaceName: string | null) => void;
  onLaunchChat: (workspaceId: string) => void;
  onNavigateToTeam: () => void;
  onNavigateToConnectors: () => void;
  onWorkspaceUpdated: (updated: Workspace) => void;
};

export type ChatsPanelProps = {
  allWorkspaces: Workspace[];
  initialWsId?: string;
  onOpenChat: (workspaceId: string) => void;
};

export type ConnectorsPanelProps = {
  orgs: Org[];
  workspaceScope: Workspace | null;
};

export type UploadModalProps = {
  ws: Workspace;
  onClose: () => void;
};

export type OrganizationsPanelProps = {
  user: UserSummary | null;
  orgs: Org[];
  selectedOrgId: string;
  isPlatformOwner: boolean;
  navigationScope: NavigationScope;
  orgScreen: OrgScreen;
  workspaces: Workspace[];
  loading: boolean;
  loadingWs: boolean;
  err: string | null;
  showCreateOrg: boolean;
  creating: boolean;
  newName: string;
  newSlug: string;
  newOrgChatProv: OrgChatProvider;
  newOrgChatModel: string;
  newOrgOllamaBase: string;
  setShowCreateOrg: Dispatch<SetStateAction<boolean>>;
  setNewName: Dispatch<SetStateAction<string>>;
  setNewSlug: Dispatch<SetStateAction<string>>;
  setNewOrgChatProv: Dispatch<SetStateAction<OrgChatProvider>>;
  setNewOrgChatModel: Dispatch<SetStateAction<string>>;
  setNewOrgOllamaBase: Dispatch<SetStateAction<string>>;
  setOrgScreen: Dispatch<SetStateAction<OrgScreen>>;
  setUploadWs: Dispatch<SetStateAction<Workspace | null>>;
  setWorkspaces: Dispatch<SetStateAction<Workspace[]>>;
  setAllWorkspaces: Dispatch<SetStateAction<Workspace[]>>;
  setJumpToWsId: Dispatch<SetStateAction<string | undefined>>;
  setWorkspacesReloadNonce: Dispatch<SetStateAction<number>>;
  setOrgs: Dispatch<SetStateAction<Org[]>>;
  setPanel: Dispatch<SetStateAction<Panel>>;
  createOrg: (e: FormEvent<HTMLFormElement>) => void | Promise<void>;
  enterOrganization: (id: string) => void;
  exitToPlatform: () => void;
  loadOrgs: () => Promise<void>;
  api: ApiClient;
  OrgDetailView: React.ComponentType<OrgDetailViewProps>;
};

export type HomePanelRouterProps = {
  panel: Panel;
  user: UserSummary | null;
  orgs: Org[];
  allWorkspaces: Workspace[];
  workspaceCountByOrg: Record<string, number>;
  loading: boolean;
  enterOrganization: (id: string) => void;
  setPanel: Dispatch<SetStateAction<Panel>>;
  selectedOrgId: string;
  navigate: (to: string) => void;
  showCreateOrg: boolean;
  setShowCreateOrg: Dispatch<SetStateAction<boolean>>;
  err: string | null;
  createOrg: (e: FormEvent<HTMLFormElement>) => void | Promise<void>;
  creating: boolean;
  newName: string;
  setNewName: Dispatch<SetStateAction<string>>;
  newSlug: string;
  setNewSlug: Dispatch<SetStateAction<string>>;
  newOrgChatProv: OrgChatProvider;
  setNewOrgChatProv: Dispatch<SetStateAction<OrgChatProvider>>;
  newOrgChatModel: string;
  setNewOrgChatModel: Dispatch<SetStateAction<string>>;
  newOrgOllamaBase: string;
  setNewOrgOllamaBase: Dispatch<SetStateAction<string>>;
  isPlatformOwner: boolean;
  navigationScope: NavigationScope;
  exitToPlatform: () => void;
  orgScreen: OrgScreen;
  setOrgScreen: Dispatch<SetStateAction<OrgScreen>>;
  workspaces: Workspace[];
  loadingWs: boolean;
  setUploadWs: Dispatch<SetStateAction<Workspace | null>>;
  api: ApiClient;
  AllWorkspacesPanel: React.ComponentType<AllWorkspacesPanelProps>;
  OrgDetailView: React.ComponentType<OrgDetailViewProps>;
  setWorkspaces: Dispatch<SetStateAction<Workspace[]>>;
  setAllWorkspaces: Dispatch<SetStateAction<Workspace[]>>;
  setJumpToWsId: Dispatch<SetStateAction<string | undefined>>;
  setWorkspacesReloadNonce: Dispatch<SetStateAction<number>>;
  loadOrgs: () => Promise<void>;
  setActiveWorkspaceContext: (workspaceId: string | null, workspaceName: string | null) => void;
  scopedWorkspaces: Workspace[];
  ctxWorkspaceId: string | null | undefined;
  jumpToWsId: string | undefined;
  chatWorkspaceId: string | null;
  setChatWorkspaceId: Dispatch<SetStateAction<string | null>>;
  brightMode: boolean;
  onEmbeddedChatWorkspaceChange: (id: string) => void;
  ChatsPanel: React.ComponentType<ChatsPanelProps>;
  jumpToChatWsId: string | undefined;
  ConnectorsPanel: React.ComponentType<ConnectorsPanelProps>;
  workspaceInContext: Workspace | null;
  BillingPanel: React.ComponentType;
  AuditPanel: React.ComponentType<{ orgs: Org[]; selectedOrgId: string; workspaceScopeIds?: string[] }>;
  workspaceScopeIds?: string[];
  canManageOrgSettings: boolean;
  canManageWorkspaceSettings: boolean;
  SettingsPanel: React.ComponentType<{
    orgs: Org[];
    selectedOrgId: string;
    onSelectOrg: (orgId: string) => void;
    onSavedOrg: (updated: Org) => void;
    onSavedWorkspace: (updated: Workspace) => void;
    onOrgDeleted: () => Promise<void> | void;
    isPlatformOwner: boolean;
    workspaces: Workspace[];
    canManageOrgSettings: boolean;
    canManageWorkspaceSettings: boolean;
  }>;
  uploadWs: Workspace | null;
  UploadModal: React.ComponentType<UploadModalProps>;
  setOrgs: Dispatch<SetStateAction<Org[]>>;
  setErr: Dispatch<SetStateAction<string | null>>;
};
