import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { usePlatformNavigationOptional } from "../context/PlatformNavigationContext";

export function AdminTopbar() {
  const { user } = useAuth();
  const platformNav = usePlatformNavigationOptional();
  const orgContextActive =
    platformNav?.isPlatformOwner && platformNav.navigationScope === "organization" && platformNav.activeOrganizationId;

  return (
    <div className="ska-topbar">
      <div className="ska-logo">
        <div className="ska-logo-icon">⬢</div>
        AI Knowledge
      </div>
      <div className="ska-topbar-right">
        {orgContextActive && (
          <span className="badge bblue" title="Admin modules use this organization until you change it in the shell or org dropdown">
            Org context
          </span>
        )}
        <span className="badge bgreen">● Live</span>
        <Link to="/home" className="ska-avatar">
          {user?.email?.slice(0, 2).toUpperCase() || "U"}
        </Link>
      </div>
    </div>
  );
}
