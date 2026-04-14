import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useOutletContext } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { PlatformNavigationProvider } from "../context/PlatformNavigationContext";

/** Matches `/organizations/me` rows and HomePage `Org`. */
export type BootstrapOrg = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description?: string | null;
  preferred_chat_provider?: string | null;
  preferred_chat_model?: string | null;
  openai_api_key_configured?: boolean;
  anthropic_api_key_configured?: boolean;
  openai_api_base_url?: string | null;
  anthropic_api_base_url?: string | null;
};

export type OrgsOutletContext = {
  orgs: BootstrapOrg[];
  setOrgs: React.Dispatch<React.SetStateAction<BootstrapOrg[]>>;
  loadingOrgs: boolean;
  orgsError: string | null;
  reloadOrgs: () => Promise<void>;
};

/**
 * Loads org membership once for the session, provides global platform navigation (active org for platform owners),
 * and passes org list to child routes via Outlet context.
 */
export function ProtectedAppShell() {
  const [orgs, setOrgs] = useState<BootstrapOrg[]>([]);
  const [loadingOrgs, setLoadingOrgs] = useState(true);
  const [orgsError, setOrgsError] = useState<string | null>(null);

  const reloadOrgs = useCallback(async () => {
    setOrgsError(null);
    setLoadingOrgs(true);
    try {
      const { data } = await api.get<BootstrapOrg[]>("/organizations/me");
      setOrgs(data);
    } catch (e) {
      setOrgsError(apiErrorMessage(e));
      setOrgs([]);
    } finally {
      setLoadingOrgs(false);
    }
  }, []);

  useEffect(() => {
    void reloadOrgs();
  }, [reloadOrgs]);

  const orgIds = useMemo(() => orgs.map((o) => o.id), [orgs]);

  const outletCtx = useMemo<OrgsOutletContext>(
    () => ({ orgs, setOrgs, loadingOrgs, orgsError, reloadOrgs }),
    [orgs, loadingOrgs, orgsError, reloadOrgs],
  );

  return (
    <PlatformNavigationProvider orgIds={orgIds}>
      <Outlet context={outletCtx} />
    </PlatformNavigationProvider>
  );
}

export function useOrgsOutlet(): OrgsOutletContext {
  const ctx = useOutletContext<OrgsOutletContext | null>();
  if (!ctx) {
    throw new Error("useOrgsOutlet must be used within a route wrapped by ProtectedAppShell");
  }
  return ctx;
}
