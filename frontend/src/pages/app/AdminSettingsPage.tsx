import { FormEvent, useEffect, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAdminOrgScope } from "../../hooks/useAdminOrgScope";

type Org = { id: string; name: string; status: string; slug: string };

export function AdminSettingsPage() {
  const { orgs, orgId, onOrgChange, err: scopeErr, reloadOrgs } = useAdminOrgScope();
  const [name, setName] = useState("");
  const [status, setStatus] = useState("active");
  const [publicConfig, setPublicConfig] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<Record<string, unknown>>("/config/public")
      .then((r) => setPublicConfig(r.data))
      .catch(() => setPublicConfig(null));
  }, []);

  useEffect(() => {
    const current = orgs.find((o) => o.id === orgId);
    if (current) {
      setName(current.name);
      setStatus(current.status);
    }
  }, [orgId, orgs]);

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setErr(null);
    setMsg(null);
    try {
      await api.patch(`/organizations/${orgId}`, { name: name.trim(), status });
      setMsg("Organization settings saved.");
      await reloadOrgs();
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    }
  }

  return (
    <RequireAdmin>
      <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Settings" />
        <main className="ska-main">
          <h2 style={{ marginTop: 0 }}>Settings</h2>
          <p className="sk-muted">Organization profile and runtime/public configuration.</p>
          {(err || scopeErr) && <p className="sk-error">{err || scopeErr}</p>}
          {msg && <p className="sk-muted">{msg}</p>}
          <form className="sk-panel sk-spaced" onSubmit={save} style={{ maxWidth: 640 }}>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "1fr 1fr" }}>
              <div>
                <label className="sk-label">Organization</label>
                <select className="sk-input" value={orgId} onChange={(e) => onOrgChange(e.target.value)}>
                  {orgs.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="sk-label">Status</label>
                <select className="sk-input" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="active">active</option>
                  <option value="suspended">suspended</option>
                </select>
              </div>
            </div>
            <div style={{ marginTop: "0.75rem" }}>
              <label className="sk-label">Organization name</label>
              <input className="sk-input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div style={{ marginTop: "0.75rem" }}>
              <button className="sk-btn" type="submit">
                Save changes
              </button>
            </div>
          </form>
          <div className="sk-panel">
            <h3 style={{ marginTop: 0 }}>Runtime public config</h3>
            <pre className="sk-mono" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
              {JSON.stringify(publicConfig || {}, null, 2)}
            </pre>
          </div>
        </main>
      </div>
    </RequireAdmin>
  );
}
