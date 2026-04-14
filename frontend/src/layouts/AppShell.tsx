import type { ReactNode } from "react";

type Props = {
  sidebar: ReactNode;
  children: ReactNode;
  /** Optional third column (e.g. source inspector) */
  aside?: ReactNode;
};

/**
 * App-region layout: nav + main + optional aside (responsive stacks on small screens).
 */
export function AppShell({ sidebar, children, aside }: Props) {
  return (
    <div
      className="sk-app-shell"
      style={{
        display: "grid",
        gridTemplateColumns: aside ? "minmax(220px, 260px) minmax(0, 1fr) minmax(280px, 360px)" : "minmax(220px, 260px) minmax(0, 1fr)",
        minHeight: "100%",
        transition: "grid-template-columns 0.2s ease",
      }}
    >
      {sidebar}
      <section style={{ minWidth: 0, display: "flex", flexDirection: "column", height: "100%" }}>{children}</section>
      {aside}
    </div>
  );
}
