import { Link, useLocation } from "react-router-dom";

export function AdminNav({ title = "Admin" }: { title?: string }) {
  const loc = useLocation();
  const on = (path: string) => (loc.pathname === path ? " on" : "");
  return (
    <aside className="ska-sidebar">
      <div className="ska-title">{title}</div>
      <nav>
        <div className="ska-group">Overview</div>
        <Link className={`ska-item${on("/admin")}`} to="/admin">
          Dashboard
        </Link>
        <Link className={`ska-item${on("/admin/team")}`} to="/admin/team">
          Team <span className="ska-dot">●</span>
        </Link>

        <div className="ska-group">Knowledge</div>
        <Link className={`ska-item${on("/admin/documents")}`} to="/admin/documents">
          Documents
        </Link>
        <Link className={`ska-item${on("/admin/connectors")}`} to="/admin/connectors">
          Connectors
        </Link>

        <div className="ska-group">Enterprise</div>
        <Link className={`ska-item${on("/admin/billing")}`} to="/admin/billing">
          Billing
        </Link>
        <Link className={`ska-item${on("/admin/audit")}`} to="/admin/audit">
          Audit log
        </Link>
        <Link className={`ska-item${on("/admin/settings")}`} to="/admin/settings">
          Settings
        </Link>

        <Link className="ska-item" to="/home">
          ← App
        </Link>
      </nav>
    </aside>
  );
}
