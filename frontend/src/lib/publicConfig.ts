import { api } from "../api/client";

export type PublicConfig = {
  contact_sales_email?: string | null;
  rate_limit_redis_enabled?: boolean;
  nango_host?: string;
  nango_public_key?: string;
  nango_configured?: boolean;
  connector_catalog?: {
    id: string;
    name: string;
    emoji: string;
    description: string;
    backendReady: boolean;
  }[];
  features?: {
    nango_connect?: boolean;
    cohere_rerank?: boolean;
    stripe_billing?: boolean;
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
