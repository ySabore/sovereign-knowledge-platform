/**
 * Client-side types for document RBAC (server enforces; use for UI hints).
 * Backend: `RBAC_MODE` simple | full, `DocumentPermission` rows in Postgres.
 */

export type RbacMode = "simple" | "full";

/** Mirrors API / seed payloads (snake_case). */
export type DocumentPermissionRow = {
  id: string;
  document_id: string;
  organization_id: string;
  user_id: string | null;
  can_read: boolean;
  source: string;
  external_id: string;
  created_at?: string;
  updated_at?: string;
};

export function rbacModeFromEnv(): RbacMode {
  const v = (import.meta.env.VITE_RBAC_MODE as string | undefined)?.trim().toLowerCase();
  return v === "full" ? "full" : "simple";
}

/** Whether the UI should explain per-document ACL (full mode). */
export function showPerDocumentAclHints(): boolean {
  return rbacModeFromEnv() === "full";
}
