import { Link } from "react-router-dom";

export function AdminNav({ title = "Admin" }: { title?: string }) {
  return (
    <aside className="sk-nav">
      <h1 style={{ fontSize: "1rem" }}>{title}</h1>
      <nav className="sk-stack" style={{ marginTop: "1rem", fontSize: "0.9rem" }}>
        <Link to="/admin">Overview</Link>
        <Link to="/admin/connectors">Connectors</Link>
        <Link to="/admin/documents">Documents</Link>
        <Link to="/admin/team">Team</Link>
        <Link to="/admin/billing">Billing</Link>
        <Link to="/admin/audit">Audit log</Link>
        <Link to="/admin/settings">Settings</Link>
        <Link to="/home">← App</Link>
      </nav>
    </aside>
  );
}
