import type { ReactNode } from "react";
import { useOrgShellTokens } from "../../context/OrgShellThemeContext";

export function BackNavButton({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  const C = useOrgShellTokens();
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        marginBottom: 16,
        background: "none",
        border: "none",
        cursor: "pointer",
        fontSize: 12,
        color: C.accent,
        fontFamily: C.sans,
      }}
    >
      {children}
    </button>
  );
}
