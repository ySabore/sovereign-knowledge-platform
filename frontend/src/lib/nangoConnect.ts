import Nango from "@nangohq/frontend";

import { api } from "../api/client";
import { fetchPublicConfig } from "./publicConfig";

/** Nango Dashboard integration id (Provider unique key) for each catalog entry we support. */
export function catalogIdToNangoProviderKey(catalogId: string): string {
  const id = catalogId.trim();
  if (id === "google-drive" || id === "gdrive") return "google-drive";
  return id;
}

/**
 * OAuth via Nango Connect Session token (current recommended auth flow).
 * Falls back to demo id when Nango is not configured on the API.
 */
export async function obtainConnectorConnectionId(catalogId: string, organizationId: string): Promise<string> {
  const cfg = await fetchPublicConfig();
  const host = (cfg.nango_host ?? "").trim() || "https://api.nango.dev";
  const live = Boolean(cfg.features?.nango_connect);

  if (live) {
    const providerKey = catalogIdToNangoProviderKey(catalogId);
    const { data } = await api.post<{ token: string }>("/connectors/connect-session", {
      integration_id: providerKey,
      organization_id: organizationId,
    });
    const token = (data.token ?? "").trim();
    if (!token) {
      throw new Error("Nango connect session token was empty");
    }
    const nango = new Nango({ host, connectSessionToken: token });
    let result: { connectionId?: string | null };
    try {
      result = await nango.auth(providerKey);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        message
          ? `Connector auth popup failed: ${message}`
          : "Connector auth popup failed. Allow popups for this site and try again.",
      );
    }
    const cid = (result.connectionId ?? "").trim();
    if (!cid) {
      throw new Error("Nango completed without a connection id");
    }
    return cid;
  }

  return `demo_${catalogId}_${Date.now()}`;
}
