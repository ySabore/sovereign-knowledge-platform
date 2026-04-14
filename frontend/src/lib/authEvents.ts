/** Fired when `skp_token` in localStorage changes (e.g. Clerk session after OAuth). */
export const SKP_AUTH_CHANGED_EVENT = "skp-auth-changed";

export function notifySkpAuthChanged(): void {
  window.dispatchEvent(new Event(SKP_AUTH_CHANGED_EVENT));
}
