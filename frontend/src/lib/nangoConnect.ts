import Nango from "@nangohq/frontend";

import { fetchPublicConfig } from "./publicConfig";

/** Nango Dashboard integration id (Provider unique key) for each catalog entry we support. */
export function catalogIdToNangoProviderKey(catalogId: string): string {
  const id = catalogId.trim();
  if (id === "google-drive" || id === "gdrive") return "google-drive";
  return id;
}

/**
 * OAuth via Nango when the API exposes `nango_public_key` and `NANGO_SECRET_KEY` is set server-side.
 * Otherwise returns a demo connection id (DB row only; sync needs real Nango + Google).
 */
export async function obtainConnectorConnectionId(catalogId: string): Promise<string> {
  const cfg = await fetchPublicConfig();
  const publicKey = (cfg.nango_public_key ?? "").trim();
  const host = (cfg.nango_host ?? "").trim() || "https://api.nango.dev";
  const live = Boolean(publicKey && cfg.features?.nango_connect);

  if (live) {
    const nango = new Nango({ host, publicKey });
    const providerKey = catalogIdToNangoProviderKey(catalogId);
    const result = await nango.auth(providerKey);
    const cid = (result.connectionId ?? "").trim();
    if (!cid) {
      throw new Error("Nango completed without a connection id");
    }
    return cid;
  }

  return `demo_${catalogId}_${Date.now()}`;
}
