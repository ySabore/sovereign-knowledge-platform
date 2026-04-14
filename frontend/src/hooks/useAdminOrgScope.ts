import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { usePlatformNavigation } from "../context/PlatformNavigationContext";

export type AdminOrg = { id: string; name: string; slug: string; status: string };

/**
 * Loads organizations for admin UIs and keeps the selected org aligned with global platform-owner context
 * (`enterOrganization` / persisted active org) so /admin/* and /home share one active organization.
 */
export function useAdminOrgScope() {
  const { user } = useAuth();
  const { activeOrganizationId, enterOrganization, isPlatformOwner } = usePlatformNavigation();
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [orgId, setOrgId] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const reloadOrgs = useCallback(async () => {
    try {
      const { data } = await api.get<AdminOrg[]>("/organizations/me");
      setOrgs(data);
      setErr(null);
    } catch (e) {
      setErr(apiErrorMessage(e));
    }
  }, []);

  useEffect(() => {
    void reloadOrgs();
  }, [reloadOrgs]);

  useEffect(() => {
    if (!orgs.length) return;

    if (isPlatformOwner) {
      if (activeOrganizationId && orgs.some((o) => o.id === activeOrganizationId)) {
        setOrgId(activeOrganizationId);
        return;
      }
      setOrgId((prev) => (prev && orgs.some((o) => o.id === prev) ? prev : orgs[0].id));
      return;
    }

    if (user?.org_ids_as_owner?.length) {
      const oid = user.org_ids_as_owner[0];
      if (oid && orgs.some((o) => o.id === oid)) {
        setOrgId(oid);
        return;
      }
    }

    setOrgId((prev) => (prev && orgs.some((o) => o.id === prev) ? prev : orgs[0].id));
  }, [orgs, isPlatformOwner, activeOrganizationId, user?.org_ids_as_owner]);

  const onOrgChange = useCallback(
    (nextId: string) => {
      setOrgId(nextId);
      if (isPlatformOwner && nextId) enterOrganization(nextId);
    },
    [isPlatformOwner, enterOrganization],
  );

  return { orgs, orgId, onOrgChange, err, reloadOrgs };
}
