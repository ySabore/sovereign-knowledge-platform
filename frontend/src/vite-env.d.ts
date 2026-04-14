/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_PROXY_TARGET?: string;
  /** When set, enables Clerk UI and sends Clerk session JWT to the API (backend needs CLERK_*). */
  readonly VITE_CLERK_PUBLISHABLE_KEY?: string;
  /** Optional UI hint: simple | full — must match backend `RBAC_MODE`. */
  readonly VITE_RBAC_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface ImportMetaEnv {
  readonly VITE_API_BASE: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
