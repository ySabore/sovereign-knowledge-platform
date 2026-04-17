import { useEffect, useState } from "react";
import type { ApiClient } from "./contracts";
import type { Panel, Workspace } from "./types";

type DocumentRow = { id: string };

type UseOrgKnowledgeGateArgs = {
  api: ApiClient;
  selectedOrgId: string;
  scopedWorkspaces: Workspace[];
  isPlatformOwner: boolean;
  panel: Panel;
  setPanel: (panel: Panel) => void;
};

export function useOrgKnowledgeGate({
  api,
  selectedOrgId,
  scopedWorkspaces,
  isPlatformOwner,
  panel,
  setPanel,
}: UseOrgKnowledgeGateArgs) {
  const [orgHasIndexedDocuments, setOrgHasIndexedDocuments] = useState<boolean | null>(null);

  useEffect(() => {
    if (!selectedOrgId || scopedWorkspaces.length === 0) {
      setOrgHasIndexedDocuments(null);
      return;
    }
    let cancelled = false;
    void Promise.allSettled(
      scopedWorkspaces.map((ws) =>
        api.get<DocumentRow[]>(`/documents/workspaces/${ws.id}`).then((r) => r.data.length),
      ),
    ).then((results) => {
      if (cancelled) return;
      const ok = results.filter(
        (r): r is PromiseFulfilledResult<number> => r.status === "fulfilled",
      );
      if (ok.length === 0) {
        setOrgHasIndexedDocuments(null);
        return;
      }
      setOrgHasIndexedDocuments(ok.some((r) => r.value > 0));
    });
    return () => {
      cancelled = true;
    };
  }, [api, selectedOrgId, scopedWorkspaces]);

  useEffect(() => {
    if (isPlatformOwner) return;
    if (orgHasIndexedDocuments !== false) return;
    if (panel !== "chats" && panel !== "team") return;
    if (!selectedOrgId) return;
    setPanel("docs");
  }, [orgHasIndexedDocuments, panel, selectedOrgId, isPlatformOwner, setPanel]);

  return { orgHasIndexedDocuments };
}
