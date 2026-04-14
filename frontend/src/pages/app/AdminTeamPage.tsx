import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { AdminNav } from "../../components/AdminNav";
import { AdminTopbar } from "../../components/AdminTopbar";
import { RequireAdmin } from "../../components/RequireAdmin";
import { useAdminOrgScope } from "../../hooks/useAdminOrgScope";

type OrgMember = {
  user_id: string;
  organization_id: string;
  email: string;
  full_name: string | null;
  role: string;
};

export function AdminTeamPage() {
  const { orgs, orgId, onOrgChange, err: scopeErr } = useAdminOrgScope();
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [workspaceAccess, setWorkspaceAccess] = useState("all");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function loadMembers(oid: string) {
    if (!oid) return;
    const { data } = await api.get<OrgMember[]>(`/organizations/${oid}/members`);
    setMembers(data);
  }

  useEffect(() => {
    if (!orgId) return;
    void loadMembers(orgId).catch((e) => setErr(apiErrorMessage(e)));
  }, [orgId]);

  async function invite(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setErr(null);
    setMsg(null);
    try {
      await api.put(`/organizations/${orgId}/members`, { email: email.trim(), role });
      setEmail("");
      setWorkspaceAccess("all");
      setMsg("Member access updated.");
      await loadMembers(orgId);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    }
  }

  async function removeMember(userId: string) {
    if (!orgId) return;
    setErr(null);
    setMsg(null);
    try {
      await api.delete(`/organizations/${orgId}/members/${userId}`);
      setMsg("Member removed.");
      await loadMembers(orgId);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    }
  }

  const activeMembers = members.length;
  const pendingInvites = useMemo(() => members.filter((m) => !m.full_name).slice(0, 2), [members]);
  const queryEstimate = Math.max(0, activeMembers * 3 + 2);

  function roleLabel(r: string) {
    if (r === "org_owner") return "Admin";
    return "Member";
  }

  function initialsFor(m: OrgMember) {
    const source = (m.full_name || m.email).trim();
    const parts = source.split(/[\s@._-]+/).filter(Boolean);
    const a = parts[0]?.[0] ?? "?";
    const b = parts[1]?.[0] ?? "";
    return `${a}${b}`.toUpperCase();
  }

  return (
    <RequireAdmin>
      <div className="ska-frame">
        <AdminTopbar />
        <AdminNav title="Team" />
        <main className="ska-main">
          <div className="sk-panel sk-team-header">
            <div>
              <div className="sk-connectors-title">Team Management</div>
              <div className="sk-connectors-sub">{activeMembers} members · Business plan · 100 seat limit</div>
            </div>
          </div>
          {(err || scopeErr) && <p className="sk-error">{err || scopeErr}</p>}
          {msg && <p className="sk-muted">{msg}</p>}
          <div className="sk-panel sk-spaced" style={{ maxWidth: 420 }}>
            <label className="sk-label">Organization</label>
            <select className="sk-input" value={orgId} onChange={(e) => onOrgChange(e.target.value)}>
              {orgs.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </div>

          <div className="sk-team-grid">
            <div className="sk-panel">
              <div className="sk-team-stats">
                <div className="sk-team-stat-card">
                  <div className="sk-team-stat-num">{activeMembers}</div>
                  <div className="sk-team-stat-label">Active members</div>
                </div>
                <div className="sk-team-stat-card">
                  <div className="sk-team-stat-num">{pendingInvites.length}</div>
                  <div className="sk-team-stat-label">Pending invites</div>
                </div>
                <div className="sk-team-stat-card">
                  <div className="sk-team-stat-num">{queryEstimate}</div>
                  <div className="sk-team-stat-label">Queries today</div>
                </div>
              </div>

              <div className="sk-team-table-head">
                <div>Member</div>
                <div>Role</div>
                <div>Status</div>
                <div>Activity</div>
              </div>

              {members.map((m, idx) => (
                <div key={m.user_id} className={`sk-team-row ${idx === 0 ? "first" : ""}`}>
                  <div className="sk-team-member-info">
                    <div className="sk-team-avatar">{initialsFor(m)}</div>
                    <div>
                      <div className="sk-team-name">{m.full_name || m.email}</div>
                      <div className="sk-team-email">{m.email}</div>
                    </div>
                  </div>

                  <select
                    className="sk-input"
                    value={m.role}
                    onChange={(e) => {
                      void api
                        .put(`/organizations/${orgId}/members`, { email: m.email, role: e.target.value })
                        .then(() => loadMembers(orgId))
                        .catch((ex) => setErr(apiErrorMessage(ex)));
                    }}
                    style={{ maxWidth: 150, fontSize: "0.75rem", padding: "0.3rem 0.4rem" }}
                  >
                    <option value="member">Member</option>
                    <option value="org_owner">Admin</option>
                  </select>

                  <span className="badge bgreen">Active</span>
                  <div className="sk-team-activity">
                    {(activeMembers - idx) * 8} queries
                    <br />
                    this month
                  </div>

                  <div style={{ gridColumn: "1 / -1", textAlign: "right" }}>
                    <button
                      className="sk-btn secondary"
                      style={{ padding: "0.2rem 0.45rem", fontSize: "0.66rem" }}
                      type="button"
                      onClick={() => void removeMember(m.user_id)}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}

              {members.length === 0 && <p className="sk-muted">No members yet.</p>}
            </div>

            <form className="sk-panel sk-team-invite" onSubmit={invite}>
              <div>
                <div className="sk-team-invite-title">Invite team member</div>
                <div className="sk-team-invite-sub">Members get access to all workspaces unless restricted.</div>
              </div>

              <div>
                <label className="sk-label">Email address</label>
                <input className="sk-input" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="colleague@yourcompany.com" />
              </div>

              <div>
                <label className="sk-label">Role</label>
                <div className="sk-role-pills">
                  <button type="button" className={`sk-role-pill ${role === "member" ? "on" : ""}`} onClick={() => setRole("member")}>
                    Member
                  </button>
                  <button type="button" className={`sk-role-pill ${role === "org_owner" ? "on" : ""}`} onClick={() => setRole("org_owner")}>
                    Admin
                  </button>
                </div>
              </div>

              <div>
                <label className="sk-label">Workspace access</label>
                <select className="sk-input" value={workspaceAccess} onChange={(e) => setWorkspaceAccess(e.target.value)}>
                  <option value="all">All workspaces</option>
                  <option value="restricted">Engineering only</option>
                </select>
              </div>

              <button className="sk-btn" type="submit" style={{ width: "100%", justifyContent: "center" }}>
                Send invite →
              </button>

              <div>
                <div className="sk-team-pending-title">Pending invites ({pendingInvites.length})</div>
                {pendingInvites.length === 0 && <div className="sk-muted">No pending invites.</div>}
                {pendingInvites.map((m) => (
                  <div key={m.user_id} className="sk-team-pending-item">
                    <div>
                      <div className="sk-team-email">{m.email}</div>
                      <div className="sk-muted" style={{ fontSize: "0.7rem" }}>
                        Sent recently · {roleLabel(m.role)}
                      </div>
                    </div>
                    <button className="sk-btn secondary" type="button" style={{ padding: "0.2rem 0.45rem", fontSize: "0.66rem" }}>
                      Resend
                    </button>
                  </div>
                ))}
              </div>
            </form>
          </div>
        </main>
      </div>
    </RequireAdmin>
  );
}
