import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

type Org = { id: string; name: string; slug: string; status: string };
type Workspace = { id: string; organization_id: string; name: string; description: string | null };

export function HomePage() {
  const { user, logout } = useAuth();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const [newOrgName, setNewOrgName] = useState("");
  const [newOrgSlug, setNewOrgSlug] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    setErr(null);
    setLoading(true);
    try {
      const { data } = await api.get<Org[]>("/organizations/me");
      setOrgs(data);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function createOrg(e: FormEvent) {
    e.preventDefault();
    if (!user?.is_platform_owner) return;
    setCreating(true);
    setErr(null);
    try {
      await api.post<Org>("/organizations", { name: newOrgName.trim(), slug: newOrgSlug.trim().toLowerCase() });
      setNewOrgName("");
      setNewOrgSlug("");
      await load();
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="sk-layout">
      <aside className="sk-nav">
        <h1>Sovereign Knowledge</h1>
        <p className="sk-muted" style={{ fontSize: "0.85rem", marginBottom: "1.5rem" }}>
          Enterprise RAG
        </p>
        <nav className="sk-stack" style={{ marginBottom: "1rem", fontSize: "0.9rem" }}>
          <div>
            <span className="sk-label">Workspace</span>
            <Link to="/home" style={{ fontWeight: 600 }}>
              Organizations & workspaces
            </Link>
          </div>
          <div>
            <Link to="/onboarding">Onboarding</Link>
          </div>
          {(user?.is_platform_owner || (user?.org_ids_as_owner?.length ?? 0) > 0) && (
            <div>
              <span className="sk-label">Admin</span>
              <Link to="/admin">Overview</Link>
              {" · "}
              <Link to="/admin/connectors">Connectors</Link>
              {" · "}
              <Link to="/admin/documents">Documents</Link>
              {" · "}
              <Link to="/admin/team">Team</Link>
              {" · "}
              <Link to="/admin/billing">Billing</Link>
            </div>
          )}
        </nav>
        <p style={{ fontSize: "0.85rem", margin: 0 }}>
          {user?.email}
          {user?.is_platform_owner && (
            <span className="sk-mono" style={{ display: "block", color: "var(--ok)", marginTop: "0.25rem" }}>
              platform owner
            </span>
          )}
        </p>
        <button type="button" className="sk-btn secondary" style={{ marginTop: "1.5rem", width: "100%" }} onClick={() => void logout()}>
          Sign out
        </button>
      </aside>
      <main className="sk-main">
        <header className="sk-page-header">
          <h2 style={{ margin: 0 }}>Organizations</h2>
          <p className="sk-muted" style={{ margin: 0 }}>
            Create tenants, then create isolated workspaces for upload and grounded chat.
          </p>
        </header>
        {loading && <p className="sk-muted">Loading…</p>}
        {err && <p className="sk-error">{err}</p>}

        {!loading && user?.is_platform_owner && (
          <form className="sk-panel sk-spaced" onSubmit={createOrg}>
            <h3 style={{ marginTop: 0 }}>Create organization</h3>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "1fr 1fr auto", alignItems: "end" }}>
              <div>
                <label className="sk-label">Name</label>
                <input className="sk-input" value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} required />
              </div>
              <div>
                <label className="sk-label">Slug</label>
                <input className="sk-input" value={newOrgSlug} onChange={(e) => setNewOrgSlug(e.target.value)} required />
              </div>
              <button className="sk-btn" type="submit" disabled={creating}>
                Create
              </button>
            </div>
          </form>
        )}

        <div className="sk-stack">
          {orgs.map((o) => (
            <OrgRow key={o.id} org={o} onRefresh={load} />
          ))}
        </div>

        {!loading && orgs.length === 0 && (
          <p className="sk-muted">
            No organizations yet. {user?.is_platform_owner ? "Create one above." : "Ask your platform owner to add you to an organization."}
          </p>
        )}
      </main>
    </div>
  );
}

function OrgRow({ org, onRefresh }: { org: Org; onRefresh: () => void }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get<Workspace[]>(`/workspaces/org/${org.id}`);
        setWorkspaces(data);
      } catch (ex) {
        setErr(apiErrorMessage(ex));
      } finally {
        setLoading(false);
      }
    })();
  }, [org.id]);

  async function createWs(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api.post<Workspace>(`/workspaces/org/${org.id}`, {
        name: name.trim(),
        description: desc.trim() || null,
      });
      setName("");
      setDesc("");
      const { data } = await api.get<Workspace[]>(`/workspaces/org/${org.id}`);
      setWorkspaces(data);
      onRefresh();
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    }
  }

  return (
    <div className="sk-panel">
      <div className="sk-row">
        <h3 style={{ margin: 0 }}>{org.name}</h3>
        <span className="sk-badge sk-mono">{org.slug}</span>
      </div>
      {err && <p className="sk-error">{err}</p>}
      {loading && <p className="sk-muted">Loading workspaces…</p>}
      <ul style={{ listStyle: "none", padding: 0, margin: "0 0 1rem" }}>
        {workspaces.map((w) => (
          <li key={w.id} className="sk-list-item">
            <Link to={`/dashboard/${w.id}`} style={{ fontWeight: 600 }}>
              {w.name}
            </Link>
            {w.description && <span className="sk-muted"> — {w.description}</span>}
          </li>
        ))}
      </ul>
      <form onSubmit={createWs} style={{ borderTop: "1px solid var(--border)", paddingTop: "1rem" }}>
        <p className="sk-label" style={{ marginBottom: "0.5rem" }}>
          New workspace (org owner)
        </p>
        <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "1fr 1fr auto", alignItems: "end" }}>
          <div>
            <label className="sk-label">Name</label>
            <input className="sk-input" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div>
            <label className="sk-label">Description</label>
            <input className="sk-input" value={desc} onChange={(e) => setDesc(e.target.value)} />
          </div>
          <button className="sk-btn secondary" type="submit">
            Add workspace
          </button>
        </div>
      </form>
    </div>
  );
}
