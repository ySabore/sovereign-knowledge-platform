import { useOrgShellTokens } from "../../context/OrgShellThemeContext";
import type { Panel } from "./types";
import type { NavGroup, NavItem } from "./useHomeNavState";

function SidebarNavItem({
  icon,
  label,
  active,
  badge,
  badgeVariant = "accent",
  onClick,
  disabled,
  title: titleAttr,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  badge?: number;
  badgeVariant?: "accent" | "danger";
  onClick: () => void;
  disabled?: boolean;
  title?: string;
}) {
  const C = useOrgShellTokens();
  const badgeBg = badgeVariant === "danger" ? C.red : C.accent;
  return (
    <button
      type="button"
      title={titleAttr}
      disabled={disabled}
      onClick={disabled ? undefined : onClick}
      style={{
        display: "flex", alignItems: "center", gap: 8, padding: "6px 13px",
        fontSize: 12, fontWeight: 500, color: active ? C.t1 : C.t2,
        cursor: disabled ? "not-allowed" : "pointer", border: "none", background: active ? "rgba(37,99,235,0.12)" : "transparent",
        borderRight: active ? `2px solid ${C.accent}` : "2px solid transparent",
        width: "100%", textAlign: "left", fontFamily: C.sans, transition: "all .12s",
        opacity: disabled ? 0.45 : 1,
      }}
    >
      <span style={{ opacity: active ? 1 : 0.7, flexShrink: 0 }}>{icon}</span>
      <span style={{ flex: 1 }}>{label}</span>
      {badge != null && (
        <span style={{
          fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 100,
          background: badgeBg, color: "white",
        }}>
          {badge}
        </span>
      )}
    </button>
  );
}

type HomeSidebarProps = {
  navGroups: NavGroup[];
  panel: Panel;
  onSelectNavItem: (item: NavItem) => void;
  user: { email?: string | null; is_platform_owner?: boolean } | null;
  initials: string;
  onLogout: () => void;
};

export function HomeSidebar({
  navGroups,
  panel,
  onSelectNavItem,
  user,
  initials,
  onLogout,
}: HomeSidebarProps) {
  const C = useOrgShellTokens();
  return (
    <aside style={{
      width: 210, flexShrink: 0, background: C.bg,
      borderRight: `1px solid ${C.hairline}`,
      display: "flex", flexDirection: "column", overflowY: "auto",
    }}>
      <div style={{
        padding: "14px 14px 14px", borderBottom: `1px solid ${C.hairline}`,
        display: "flex", alignItems: "center", gap: 8,
        fontSize: 13, fontWeight: 600, color: C.t1,
      }}>
        <div style={{
          width: 24, height: 24, background: C.accent, borderRadius: 5,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: `0 0 12px ${C.accentG}`,
        }}>
          <svg viewBox="0 0 18 18" style={{ width: 13, height: 13, fill: "white" }}>
            <path d="M9 1L2 5v8l7 4 7-4V5L9 1zm0 2.2l4.8 2.8L9 8.8 4.2 6 9 3.2zm-5.8 3.8l5 2.9v5.2L3.2 12V7zm6.8 8.1V9.9l5-2.9V12l-5 2.9z" />
          </svg>
        </div>
        Sovereign Knowledge
      </div>

      {navGroups.map((group) => (
        <div key={group.label}>
          <div style={{
            fontSize: 9, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase",
            color: C.t3, padding: "10px 14px 4px",
          }}>
            {group.label}
          </div>
          {group.items.map((item) => (
            <SidebarNavItem
              key={item.label}
              icon={item.icon}
              label={item.label}
              active={Boolean(item.id && item.id === panel)}
              badge={item.badge}
              badgeVariant={item.badgeVariant ?? "accent"}
              disabled={item.disabled}
              title={item.title}
              onClick={() => onSelectNavItem(item)}
            />
          ))}
        </div>
      ))}

      <div style={{ marginTop: "auto", padding: "12px 14px", borderTop: `1px solid ${C.hairline}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <div style={{
            width: 27, height: 27, borderRadius: "50%",
            background: "linear-gradient(135deg,#2563EB,#7C3AED)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 10, fontWeight: 700, color: "white", flexShrink: 0,
          }}>
            {initials}
          </div>
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: C.t1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 130 }}>
              {user?.email}
            </div>
            {user?.is_platform_owner && (
              <div style={{ fontSize: 9, color: C.green, fontFamily: C.mono }}>platform owner</div>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onLogout}
          style={{
            width: "100%", padding: "5px 10px", border: `1px solid ${C.bd}`,
            borderRadius: 6, background: "transparent", color: C.t2,
            fontSize: 11, fontFamily: C.sans, cursor: "pointer",
          }}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
