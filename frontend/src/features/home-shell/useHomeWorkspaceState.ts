import { useCallback, useEffect, useMemo, useState } from "react";
import type { ApiClient } from "./contracts";
import type { Org, OrgScreen, Panel, Workspace } from "./types";

type UseHomeWorkspaceStateArgs = {
  orgs: Org[];
  selectedOrgId: string;
  userIsPlatformOwner: boolean;
  memberChatOnly: boolean;
  api: ApiClient;
  ctxWorkspaceId: string | null | undefined;
  ctxWorkspaceName: string | null | undefined;
  setActiveWorkspaceContext: (workspaceId: string | null, workspaceName: string | null) => void;
};

export function useHomeWorkspaceState({
  orgs,
  selectedOrgId,
  userIsPlatformOwner,
  memberChatOnly,
  api,
  ctxWorkspaceId,
  ctxWorkspaceName,
  setActiveWorkspaceContext,
}: UseHomeWorkspaceStateArgs) {
  const [panel, setPanel] = useState<Panel>(userIsPlatformOwner ? "platform" : memberChatOnly ? "chats" : "dashboard");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [allWorkspaces, setAllWorkspaces] = useState<Workspace[]>([]);
  const [workspaceCountByOrg, setWorkspaceCountByOrg] = useState<Record<string, number>>({});
  const [loadingWs, setLoadingWs] = useState(false);
  const [workspacesReloadNonce, setWorkspacesReloadNonce] = useState(0);
  const [jumpToWsId, setJumpToWsId] = useState<string | undefined>(undefined);
  const [orgScreen, setOrgScreen] = useState<OrgScreen>("overview");
  const [jumpToChatWsId, setJumpToChatWsId] = useState<string | undefined>(undefined);
  const [chatWorkspaceId, setChatWorkspaceId] = useState<string | null>(null);
  const [uploadWs, setUploadWs] = useState<Workspace | null>(null);

  const onEmbeddedChatWorkspaceChange = useCallback((id: string) => {
    setChatWorkspaceId(id);
  }, []);

  useEffect(() => {
    setOrgScreen("overview");
  }, [selectedOrgId]);

  useEffect(() => {
    if (panel !== "chats") {
      setJumpToChatWsId(undefined);
      setChatWorkspaceId(null);
    }
  }, [panel]);

  useEffect(() => {
    if (!chatWorkspaceId) return;
    const workspace =
      allWorkspaces.find((x) => x.id === chatWorkspaceId) ??
      workspaces.find((x) => x.id === chatWorkspaceId);
    setActiveWorkspaceContext(chatWorkspaceId, workspace?.name ?? null);
  }, [chatWorkspaceId, allWorkspaces, workspaces, setActiveWorkspaceContext]);

  useEffect(() => {
    if (panel === "platform" || panel === "orgs" || panel === "billing" || panel === "audit" || panel === "settings") {
      setActiveWorkspaceContext(null, null);
    }
  }, [panel, setActiveWorkspaceContext]);

  useEffect(() => {
    if (!ctxWorkspaceId || !selectedOrgId || loadingWs) return;
    const workspace =
      allWorkspaces.find((w) => w.id === ctxWorkspaceId) ??
      workspaces.find((w) => w.id === ctxWorkspaceId);
    if (!workspace || workspace.organization_id !== selectedOrgId) {
      setActiveWorkspaceContext(null, null);
    }
  }, [selectedOrgId, ctxWorkspaceId, allWorkspaces, workspaces, loadingWs, setActiveWorkspaceContext]);

  useEffect(() => {
    if (!orgs.length) {
      setAllWorkspaces([]);
      setWorkspaceCountByOrg({});
      return;
    }
    if (memberChatOnly) {
      let stale = false;
      void api
        .get<Workspace[]>("/workspaces/me")
        .then(({ data }) => {
          if (stale) return;
          setAllWorkspaces(data);
          const counts: Record<string, number> = {};
          for (const o of orgs) counts[o.id] = 0;
          for (const ws of data) counts[ws.organization_id] = (counts[ws.organization_id] ?? 0) + 1;
          setWorkspaceCountByOrg(counts);
        })
        .catch(() => {
          if (!stale) {
            setAllWorkspaces([]);
            setWorkspaceCountByOrg({});
          }
        });
      return () => {
        stale = true;
      };
    }
    let cancelled = false;
    void Promise.allSettled(
      orgs.map((o) =>
        api.get<Workspace[]>(`/workspaces/org/${o.id}`).then((r) => ({ id: o.id, list: r.data })),
      ),
    ).then((results) => {
      if (cancelled) return;
      const fulfilled = results.filter(
        (r): r is PromiseFulfilledResult<{ id: string; list: Workspace[] }> => r.status === "fulfilled",
      );
      const merged: Workspace[] = [];
      for (const { value } of fulfilled) {
        merged.push(...value.list);
      }
      setWorkspaceCountByOrg((prev) => {
        const next: Record<string, number> = {};
        for (const o of orgs) next[o.id] = prev[o.id] ?? 0;
        for (const { value } of fulfilled) next[value.id] = value.list.length;
        return next;
      });
      setAllWorkspaces(merged);
    });
    return () => {
      cancelled = true;
    };
  }, [api, orgs, workspacesReloadNonce, memberChatOnly]);

  useEffect(() => {
    if (!selectedOrgId) {
      setWorkspaces([]);
      setLoadingWs(false);
      return;
    }
    if (memberChatOnly) {
      let stale = false;
      setLoadingWs(true);
      api
        .get<Workspace[]>("/workspaces/me")
        .then(({ data }) => {
          if (stale) return;
          const scoped = data.filter((ws) => ws.organization_id === selectedOrgId);
          setWorkspaces(scoped);
          setAllWorkspaces(data);
          const counts: Record<string, number> = {};
          for (const o of orgs) counts[o.id] = 0;
          for (const ws of data) counts[ws.organization_id] = (counts[ws.organization_id] ?? 0) + 1;
          setWorkspaceCountByOrg(counts);
        })
        .catch(() => {
          if (!stale) setWorkspaces([]);
        })
        .finally(() => {
          if (!stale) setLoadingWs(false);
        });
      return () => {
        stale = true;
      };
    }
    let stale = false;
    setLoadingWs(true);
    setWorkspaces([]);
    api
      .get<Workspace[]>(`/workspaces/org/${selectedOrgId}`)
      .then(({ data }) => {
        if (!stale) setWorkspaces(data);
      })
      .catch(() => {
        if (!stale) setWorkspaces([]);
      })
      .finally(() => {
        if (!stale) setLoadingWs(false);
      });
    return () => {
      stale = true;
    };
  }, [api, selectedOrgId, memberChatOnly, orgs]);

  useEffect(() => {
    if (!selectedOrgId || loadingWs) return;
    setWorkspaceCountByOrg((prev) => ({ ...prev, [selectedOrgId]: workspaces.length }));
  }, [selectedOrgId, workspaces, loadingWs]);

  const scopedWorkspaces = useMemo(() => {
    if (!selectedOrgId) return [] as Workspace[];
    const fromBatch = allWorkspaces.filter((w) => w.organization_id === selectedOrgId);
    if (workspaces.length > 0) return workspaces;
    return fromBatch;
  }, [allWorkspaces, selectedOrgId, workspaces]);

  const workspaceInContext = useMemo((): Workspace | null => {
    if (!ctxWorkspaceId) return null;
    const workspace =
      allWorkspaces.find((x) => x.id === ctxWorkspaceId) ??
      workspaces.find((x) => x.id === ctxWorkspaceId);
    if (workspace) return workspace;
    if (selectedOrgId && ctxWorkspaceName) {
      return {
        id: ctxWorkspaceId,
        organization_id: selectedOrgId,
        name: ctxWorkspaceName,
        description: null,
      };
    }
    return null;
  }, [ctxWorkspaceId, ctxWorkspaceName, allWorkspaces, workspaces, selectedOrgId]);

  return {
    panel,
    setPanel,
    workspaces,
    setWorkspaces,
    allWorkspaces,
    setAllWorkspaces,
    workspaceCountByOrg,
    loadingWs,
    workspacesReloadNonce,
    setWorkspacesReloadNonce,
    jumpToWsId,
    setJumpToWsId,
    orgScreen,
    setOrgScreen,
    jumpToChatWsId,
    setJumpToChatWsId,
    chatWorkspaceId,
    setChatWorkspaceId,
    onEmbeddedChatWorkspaceChange,
    uploadWs,
    setUploadWs,
    scopedWorkspaces,
    workspaceInContext,
  };
}
