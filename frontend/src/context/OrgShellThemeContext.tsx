import { createContext, useContext } from "react";

const STORAGE_KEY = "skp_org_bright_mode";

export type OrgShellTokens = {
  bg: string;
  bgS: string;
  bgE: string;
  bgCard: string;
  accent: string;
  accentH: string;
  accentG: string;
  gold: string;
  green: string;
  red: string;
  purple: string;
  t1: string;
  t2: string;
  t3: string;
  bd: string;
  bd2: string;
  hairline: string;
  rowHover: string;
  serif: string;
  sans: string;
  mono: string;
};

export const ORG_SHELL_TOKENS_DARK: OrgShellTokens = {
  bg: "#07090F",
  bgS: "#0C0F1A",
  bgE: "#111827",
  bgCard: "#0F1420",
  accent: "#2563EB",
  accentH: "#1d4fd8",
  accentG: "rgba(37,99,235,0.18)",
  gold: "#F59E0B",
  green: "#10B981",
  red: "#EF4444",
  purple: "#8B5CF6",
  t1: "#EEF2FF",
  t2: "#94A3B8",
  t3: "#3D4A5C",
  bd: "rgba(255,255,255,0.07)",
  bd2: "rgba(255,255,255,0.13)",
  hairline: "rgba(255,255,255,0.05)",
  rowHover: "rgba(255,255,255,0.03)",
  serif: '"Instrument Serif",Georgia,serif',
  sans: '"DM Sans",sans-serif',
  mono: '"JetBrains Mono",monospace',
};

export const ORG_SHELL_TOKENS_BRIGHT: OrgShellTokens = {
  bg: "#f4f6fb",
  bgS: "#eef1f8",
  bgE: "#ffffff",
  bgCard: "#ffffff",
  accent: "#2563EB",
  accentH: "#1d4fd8",
  accentG: "rgba(37,99,235,0.14)",
  gold: "#b45309",
  green: "#059669",
  red: "#dc2626",
  purple: "#7c3aed",
  t1: "#0f172a",
  t2: "#475569",
  t3: "#64748b",
  bd: "rgba(15,23,42,0.08)",
  bd2: "rgba(15,23,42,0.14)",
  hairline: "rgba(15,23,42,0.08)",
  rowHover: "rgba(15,23,42,0.05)",
  serif: '"Instrument Serif",Georgia,serif',
  sans: '"DM Sans",sans-serif',
  mono: '"JetBrains Mono",monospace',
};

export const OrgShellTokensContext = createContext<OrgShellTokens>(ORG_SHELL_TOKENS_DARK);

export function useOrgShellTokens(): OrgShellTokens {
  return useContext(OrgShellTokensContext);
}

export type OrgShellUiValue = {
  brightMode: boolean;
  setBrightMode: (v: boolean) => void;
  toggleBrightMode: () => void;
};

export const OrgShellUiContext = createContext<OrgShellUiValue | null>(null);

export function useOrgShellUiOptional(): OrgShellUiValue | null {
  return useContext(OrgShellUiContext);
}

export function readOrgBrightModeFromStorage(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function persistOrgBrightMode(bright: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, bright ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
}
