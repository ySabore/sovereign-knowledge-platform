import { api } from "../api/client";

export type PublicConfig = {
  nango_host?: string;
  nango_public_key?: string;
  nango_configured?: boolean;
  features?: {
    nango_connect?: boolean;
  };
};

let cache: PublicConfig | null = null;

export async function fetchPublicConfig(force = false): Promise<PublicConfig> {
  if (!force && cache) return cache;
  const { data } = await api.get<PublicConfig>("/config/public");
  cache = data;
  return data;
}

export function clearPublicConfigCache(): void {
  cache = null;
}
