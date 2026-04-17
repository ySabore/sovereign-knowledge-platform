import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { isAxiosError } from "axios";

import { api, apiErrorMessage } from "../api/client";
import { SKP_AUTH_CHANGED_EVENT } from "../lib/authEvents";

export type UserMe = {
  id: string;
  email: string;
  full_name: string | null;
  is_platform_owner: boolean;
  org_ids_as_owner: string[];
  org_ids_as_workspace_admin: string[];
};

type AuthState = {
  token: string | null;
  user: UserMe | null;
  loading: boolean;
  /** Set when `/auth/me` fails after Clerk sign-in (e.g. missing email claim on session token). */
  sessionError: string | null;
  clearSessionError: () => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({
  children,
  onClearExternalAuth,
}: {
  children: ReactNode;
  /** e.g. Clerk `signOut()` when using Clerk as an auth provider */
  onClearExternalAuth?: () => void | Promise<void>;
}) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("skp_token"));
  const [user, setUser] = useState<UserMe | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  /** Latest profile (synced each render) so refreshMe can tell if 5xx is a transient blip vs first load. */
  const userRef = useRef<UserMe | null>(null);
  userRef.current = user;

  const clearSessionError = useCallback(() => setSessionError(null), []);

  /** Always read JWT from localStorage so Clerk OAuth (writes token outside React state) still loads `/auth/me`. */
  const refreshMe = useCallback(async () => {
    const t = localStorage.getItem("skp_token");
    setToken(t);
    if (!t) {
      setUser(null);
      setSessionError(null);
      setLoading(false);
      return;
    }
    const hadProfileAlready = userRef.current !== null;
    try {
      const { data } = await api.get<UserMe>("/auth/me");
      setUser({
        ...data,
        org_ids_as_owner: data.org_ids_as_owner ?? [],
        org_ids_as_workspace_admin: data.org_ids_as_workspace_admin ?? [],
      });
      setSessionError(null);
    } catch (e) {
      let msg: string | null = null;
      let status: number | undefined;
      if (isAxiosError(e)) {
        status = e.response?.status;
        const d = e.response?.data as { detail?: unknown } | undefined;
        if (typeof d?.detail === "string") msg = d.detail;
        if (!e.response) {
          if (hadProfileAlready) {
            setSessionError(null);
          } else {
            setSessionError(
              "Cannot reach the API (network or server down). Check your connection, then refresh the page.",
            );
          }
          return;
        }
      }
      const hardAuthFailure = status === 401 || status === 403;
      if (hardAuthFailure) {
        localStorage.removeItem("skp_token");
        setToken(null);
        setUser(null);
        setSessionError(
          msg ?? "Could not verify your session with the API.",
        );
        return;
      }
      // 5xx,429, etc.: keep signed-in UI if we already loaded a profile once (avoids banner flash on retry/hiccup).
      if (hadProfileAlready) {
        setUser((prev) => prev);
        setSessionError(null);
        return;
      }
      setUser(null);
      setSessionError(
        msg ?? "The API returned an error while loading your profile. Try again in a moment.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  useEffect(() => {
    const onChanged = () => {
      void refreshMe();
    };
    window.addEventListener(SKP_AUTH_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(SKP_AUTH_CHANGED_EVENT, onChanged);
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    const { data } = await api.post<{ access_token: string }>("/auth/login", { email, password });
    localStorage.setItem("skp_token", data.access_token);
    setToken(data.access_token);
    const me = await api.get<UserMe>("/auth/me");
    setUser({
      ...me.data,
      org_ids_as_owner: me.data.org_ids_as_owner ?? [],
      org_ids_as_workspace_admin: me.data.org_ids_as_workspace_admin ?? [],
    });
    setSessionError(null);
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem("skp_token");
    setToken(null);
    setUser(null);
    setSessionError(null);
    await onClearExternalAuth?.();
  }, [onClearExternalAuth]);

  const value = useMemo(
    () => ({ token, user, loading, sessionError, clearSessionError, login, logout, refreshMe }),
    [token, user, loading, sessionError, clearSessionError, login, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
