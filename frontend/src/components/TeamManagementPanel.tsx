import { FormEvent, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../api/client";

type Org = { id: string; name: string };
type OrgMember = {
  user_id: string;
  organization_id: string;
  email: string;
  full_name: string | null;
  role: string;
};
type OrgInvite = {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
};
type InviteIssueResponse = {
  invite: OrgInvite;
  invite_token: string;
};

const T = {
  bg: "#0b0f18",
  card: "#111826",
  border: "rgba(255,255,255,0.07)",
  text: "#ebf1ff",
  muted: "#8ea2c0",
  dim: "#4a5a75",
  green: "#14b87a",
  yellow: "#d2a43c",
  blue: "#2563eb",
  sans: '"DM Sans",sans-serif',
  serif: '"Instrument Serif",Georgia,serif',
};

function initialsFor(m: OrgMember) {
  const source = (m.full_name || m.email).trim();
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  const a = parts[0]?.[0] ?? "?";
  const b = parts[1]?.[0] ?? "";
  return `${a}${b}`.toUpperCase();
}

function roleLabel(role: string) {
  return role === "org_owner" ? "Admin" : "Member";
}

export function TeamManagementPanel() {
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState("");
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [invites, setInvites] = useState<OrgInvite[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function loadMembers(oid: string) {
    if (!oid) return;
    const { data } = await api.get<OrgMember[]>(`/organizations/${oid}/members`);
    setMembers(data);
  }
  async function loadInvites(oid: string) {
    if (!oid) return;
    const { data } = await api.get<OrgInvite[]>(`/organizations/${oid}/invites`);
    setInvites(data);
  }

  useEffect(() => {
    void api
      .get<Org[]>("/organizations/me")
      .then((r) => {
        setOrgs(r.data);
        if (r.data[0]) setOrgId((prev) => prev || r.data[0].id);
      })
      .catch((e) => setErr(apiErrorMessage(e)));
  }, []);

  useEffect(() => {
    if (!orgId) return;
    void loadMembers(orgId).catch((e) => setErr(apiErrorMessage(e)));
    void loadInvites(orgId).catch((e) => setErr(apiErrorMessage(e)));
  }, [orgId]);

  async function invite(e: FormEvent) {
    e.preventDefault();
    if (!orgId) return;
    setErr(null);
    setMsg(null);
    try {
      const { data } = await api.post<InviteIssueResponse>(`/organizations/${orgId}/invites`, { email: email.trim(), role });
      setEmail("");
      setMsg(`Invite created. Token (for testing): ${data.invite_token}`);
      await loadMembers(orgId);
      await loadInvites(orgId);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    }
  }

  async function resendInvite(inviteId: string) {
    if (!orgId) return;
    setErr(null);
    setMsg(null);
    try {
      const { data } = await api.post<InviteIssueResponse>(`/organizations/${orgId}/invites/${inviteId}/resend`);
      setMsg(`Invite resent. Token (for testing): ${data.invite_token}`);
      await loadInvites(orgId);
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
      await loadMembers(orgId);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    }
  }

  const activeMembers = members.length;
  const pendingInvites = useMemo(() => invites.filter((i) => i.status === "pending").slice(0, 4), [invites]);
  const queriesToday = Math.max(2, activeMembers * 3 + 2);

  return (
    <div style={{ background: T.bg, minHeight: "100%", padding: "14px 0 0", fontFamily: T.sans }}>
      <div style={{ padding: "0 10px 10px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ fontFamily: T.serif, color: T.text, fontSize: 30, lineHeight: 1.1 }}>Team Management</div>
        <div style={{ color: T.muted, fontSize: 12 }}>
          {activeMembers} members · Business plan · 100 seat limit
        </div>
      </div>

      {err && <div style={{ margin: "8px 10px", color: "#f87171", fontSize: 12 }}>{err}</div>}
      {msg && <div style={{ margin: "8px 10px", color: T.green, fontSize: 12 }}>{msg}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 260px", minHeight: 500 }}>
        <div style={{ borderRight: `1px solid ${T.border}` }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, padding: 8, borderBottom: `1px solid ${T.border}` }}>
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "10px 12px", textAlign: "center" }}>
              <div style={{ color: T.text, fontFamily: T.serif, fontSize: 30 }}>{activeMembers}</div>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>Active members</div>
            </div>
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "10px 12px", textAlign: "center" }}>
              <div style={{ color: T.text, fontFamily: T.serif, fontSize: 30 }}>{pendingInvites.length}</div>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>Pending invites</div>
            </div>
            <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: "10px 12px", textAlign: "center" }}>
              <div style={{ color: T.text, fontFamily: T.serif, fontSize: 30 }}>{queriesToday}</div>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>Queries today</div>
            </div>
          </div>

          <div style={{ padding: "0 8px 8px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1.6fr .7fr .6fr .5fr", color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", padding: "8px 6px", borderBottom: `1px solid ${T.border}` }}>
              <div>Members</div><div>Role</div><div>Status</div><div>Activity</div>
            </div>
            {members.map((m, idx) => (
              <div key={m.user_id} style={{ display: "grid", gridTemplateColumns: "1.6fr .7fr .6fr .5fr", alignItems: "center", padding: "8px 6px", borderBottom: `1px solid ${T.border}`, gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 22, height: 22, borderRadius: "50%", background: idx % 2 ? "#0ea5e9" : "#7c3aed", color: "white", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {initialsFor(m)}
                  </div>
                  <div>
                    <div style={{ color: T.text, fontSize: 12, fontWeight: 600 }}>{m.full_name || m.email}</div>
                    <div style={{ color: T.muted, fontSize: 11 }}>{m.email}</div>
                  </div>
                </div>
                <select
                  value={m.role}
                  onChange={(e) => {
                    void api.put(`/organizations/${orgId}/members`, { email: m.email, role: e.target.value }).then(() => loadMembers(orgId)).catch((ex) => setErr(apiErrorMessage(ex)));
                  }}
                  style={{ background: T.card, border: `1px solid ${T.border}`, color: T.text, borderRadius: 7, fontSize: 11, padding: "4px 6px" }}
                >
                  <option value="member">Member</option>
                  <option value="org_owner">Admin</option>
                </select>
                <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 10, borderRadius: 999, padding: "2px 8px", background: "rgba(20,184,122,0.15)", color: T.green, border: `1px solid rgba(20,184,122,.35)` }}>
                  Active
                </span>
                <div style={{ color: T.muted, fontSize: 11, textAlign: "right" }}>
                  {(activeMembers - idx) * 7} queries
                  <br />
                  <button onClick={() => void removeMember(m.user_id)} type="button" style={{ marginTop: 4, background: "transparent", border: `1px solid ${T.border}`, color: T.muted, borderRadius: 6, fontSize: 10, padding: "2px 6px", cursor: "pointer" }}>
                    Remove
                  </button>
                </div>
              </div>
            ))}
            {members.length === 0 && <div style={{ color: T.muted, padding: 12 }}>No members yet.</div>}
          </div>
        </div>

        <form onSubmit={invite} style={{ padding: 10 }}>
          <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: 10 }}>
            <div style={{ color: T.text, fontSize: 20, fontFamily: T.serif }}>Invite team member</div>
            <div style={{ color: T.muted, fontSize: 12, marginTop: 3 }}>Members get access to all workspaces unless restricted.</div>

            <div style={{ marginTop: 10 }}>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>Email address</div>
              <input value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="colleague@yourcompany.com" style={{ width: "100%", background: "#0f1726", border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "8px 9px", fontSize: 12 }} />
            </div>

            <div style={{ marginTop: 10 }}>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>Role</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                <button type="button" onClick={() => setRole("member")} style={{ borderRadius: 8, padding: "6px 8px", border: `1px solid ${role === "member" ? "rgba(37,99,235,.5)" : T.border}`, background: role === "member" ? "rgba(37,99,235,.15)" : "transparent", color: T.text, fontSize: 12 }}>Member</button>
                <button type="button" onClick={() => setRole("org_owner")} style={{ borderRadius: 8, padding: "6px 8px", border: `1px solid ${role === "org_owner" ? "rgba(37,99,235,.5)" : T.border}`, background: role === "org_owner" ? "rgba(37,99,235,.15)" : "transparent", color: T.text, fontSize: 12 }}>Admin</button>
              </div>
            </div>

            <div style={{ marginTop: 10 }}>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>Organization</div>
              <select value={orgId} onChange={(e) => setOrgId(e.target.value)} style={{ width: "100%", background: "#0f1726", border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "8px 9px", fontSize: 12 }}>
                {orgs.map((o) => (
                  <option key={o.id} value={o.id}>{o.name}</option>
                ))}
              </select>
            </div>

            <button type="submit" style={{ width: "100%", marginTop: 10, border: "none", borderRadius: 8, padding: "8px 10px", background: T.blue, color: "white", fontWeight: 700, fontSize: 12, cursor: "pointer" }}>
              Send invite →
            </button>

            <div style={{ marginTop: 12 }}>
              <div style={{ color: T.muted, fontSize: 12 }}>Pending invites ({pendingInvites.length})</div>
              {pendingInvites.map((m) => (
                <div key={m.id} style={{ marginTop: 8, border: `1px solid ${T.border}`, borderRadius: 8, padding: "7px 8px", display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <div>
                    <div style={{ color: T.text, fontSize: 11 }}>{m.email}</div>
                    <div style={{ color: T.muted, fontSize: 10 }}>Pending · {roleLabel(m.role)}</div>
                  </div>
                  <button onClick={() => void resendInvite(m.id)} type="button" style={{ border: `1px solid ${T.border}`, background: "transparent", color: T.muted, borderRadius: 6, fontSize: 10, padding: "2px 6px" }}>
                    Resend
                  </button>
                </div>
              ))}
            </div>
          </div>
        </form>
      </div>

      <style>{`
        @media (max-width: 980px) {
          .team-grid-responsive { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
