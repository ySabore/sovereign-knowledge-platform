import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useOrgShellUiOptional } from "../context/OrgShellThemeContext";

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

const T_DARK = {
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

const T_BRIGHT = {
  bg: "#f4f6fb",
  card: "#ffffff",
  border: "rgba(15,23,42,0.1)",
  text: "#0f172a",
  muted: "#475569",
  dim: "#64748b",
  green: "#059669",
  yellow: "#b45309",
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

type AccessViewer = {
  is_platform_owner: boolean;
  org_ids_as_owner: string[];
};

type WorkspaceRow = { id: string; name: string; organization_id: string };
type WorkspaceMemberRow = {
  user_id: string;
  workspace_id: string;
  email: string;
  full_name: string | null;
  role: string;
};

const WORKSPACE_ROLE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "No access" },
  { value: "member", label: "Member" },
  { value: "editor", label: "Editor" },
  { value: "workspace_admin", label: "Workspace admin" },
];

export function TeamManagementPanel({
  initialOrgId,
  scopedWorkspaceId,
  scopedWorkspaceName,
  viewer,
}: {
  initialOrgId?: string;
  /** When set, Team is opened from a workspace selection — org data still applies org-wide. */
  scopedWorkspaceId?: string | null;
  scopedWorkspaceName?: string | null;
  /** Signed-in user; used to show per-workspace access controls for org owners / platform owners only. */
  viewer?: AccessViewer | null;
}) {
  const shell = useOrgShellUiOptional();
  const T = shell?.brightMode ? T_BRIGHT : T_DARK;
  const [orgs, setOrgs] = useState<Org[]>([]);
  const [orgId, setOrgId] = useState("");
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [acceptToken, setAcceptToken] = useState("");
  const [acceptingInvite, setAcceptingInvite] = useState(false);
  const [invites, setInvites] = useState<OrgInvite[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceRow[]>([]);
  /** user_id -> workspace_id -> role (only rows returned by the API; missing = no access). */
  const [wsAccessByUser, setWsAccessByUser] = useState<Record<string, Record<string, string>>>({});
  const [loadingWsMatrix, setLoadingWsMatrix] = useState(false);
  const [wsMatrixBusyKey, setWsMatrixBusyKey] = useState<string | null>(null);

  const canAssignWorkspaceAccess = Boolean(
    viewer && orgId && (viewer.is_platform_owner || viewer.org_ids_as_owner.includes(orgId)),
  );

  const loadWorkspaceMatrix = useCallback(async () => {
    if (!orgId || !canAssignWorkspaceAccess) return;
    setLoadingWsMatrix(true);
    setErr(null);
    try {
      const { data: wss } = await api.get<WorkspaceRow[]>(`/workspaces/org/${orgId}`);
      setWorkspaces(wss);
      const next: Record<string, Record<string, string>> = {};
      await Promise.all(
        wss.map(async (w) => {
          const { data: mlist } = await api.get<WorkspaceMemberRow[]>(`/workspaces/${w.id}/members`);
          for (const row of mlist) {
            if (!next[row.user_id]) next[row.user_id] = {};
            next[row.user_id][w.id] = row.role;
          }
        }),
      );
      setWsAccessByUser(next);
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setLoadingWsMatrix(false);
    }
  }, [orgId, canAssignWorkspaceAccess]);

  useEffect(() => {
    if (!canAssignWorkspaceAccess) {
      setWorkspaces([]);
      setWsAccessByUser({});
      return;
    }
    void loadWorkspaceMatrix();
  }, [loadWorkspaceMatrix, members, canAssignWorkspaceAccess]);

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
        setOrgId((prev) => prev || r.data[0]?.id || "");
      })
      .catch((e) => setErr(apiErrorMessage(e)));
  }, []);

  useEffect(() => {
    if (!initialOrgId || !orgs.some((o) => o.id === initialOrgId)) return;
    setOrgId(initialOrgId);
  }, [initialOrgId, orgs]);

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

  async function acceptInviteToken(e?: { preventDefault?: () => void }) {
    e?.preventDefault?.();
    const token = acceptToken.trim();
    if (!token) return;
    setErr(null);
    setMsg(null);
    setAcceptingInvite(true);
    try {
      const { data } = await api.post<OrgMember>("/organizations/invites/accept", { token });
      setAcceptToken("");
      setMsg(`Invite accepted for ${data.email} in selected org.`);
      await loadMembers(data.organization_id);
      await loadInvites(data.organization_id);
      if (data.organization_id !== orgId) {
        setOrgId(data.organization_id);
      }
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setAcceptingInvite(false);
    }
  }

  async function setMemberWorkspaceRole(member: OrgMember, workspaceId: string, newRole: string) {
    const key = `${member.user_id}:${workspaceId}`;
    setWsMatrixBusyKey(key);
    setErr(null);
    setMsg(null);
    try {
      if (!newRole) {
        await api.delete(`/workspaces/${workspaceId}/members/${member.user_id}`);
      } else {
        await api.put(`/workspaces/${workspaceId}/members`, { email: member.email, role: newRole });
      }
      await loadWorkspaceMatrix();
      setMsg("Workspace access updated.");
    } catch (ex) {
      setErr(apiErrorMessage(ex));
    } finally {
      setWsMatrixBusyKey(null);
    }
  }

  const activeMembers = members.length;
  const orgAdmins = useMemo(() => members.filter((m) => m.role === "org_owner"), [members]);
  const orgMembersOnly = useMemo(() => members.filter((m) => m.role === "member"), [members]);
  const pendingInvites = useMemo(() => invites.filter((i) => i.status === "pending").slice(0, 4), [invites]);
  const queriesToday = Math.max(2, activeMembers * 3 + 2);

  return (
    <div style={{ background: T.bg, minHeight: "100%", padding: "14px 0 0", fontFamily: T.sans }}>
      <div style={{ padding: "0 10px 10px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ fontFamily: T.serif, color: T.text, fontSize: 30, lineHeight: 1.1 }}>Team Management</div>
        <div style={{ color: T.muted, fontSize: 12 }}>
          {activeMembers} members · Business plan · 100 seat limit
        </div>
        {scopedWorkspaceId && scopedWorkspaceName && (
          <div
            style={{
              marginTop: 10,
              padding: "10px 12px",
              borderRadius: 10,
              background: T.card,
              border: `1px solid ${T.border}`,
              color: T.muted,
              fontSize: 12,
              lineHeight: 1.45,
            }}
          >
            <span style={{ color: T.text, fontWeight: 600 }}>Workspace:</span> {scopedWorkspaceName} — Organization
            roles and invites apply to the whole org; use <strong style={{ color: T.text }}>Workspace access</strong>{" "}
            below to grant or remove access per workspace for organization members.
          </div>
        )}
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

          {canAssignWorkspaceAccess && (
            <div style={{ padding: "12px 8px 16px", borderTop: `1px solid ${T.border}` }}>
              <div style={{ color: T.text, fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Workspace access</div>
              <div style={{ color: T.muted, fontSize: 11, lineHeight: 1.5, marginBottom: 10 }}>
                For each <strong style={{ color: T.text }}>organization member</strong>, choose a role per workspace or{" "}
                <strong style={{ color: T.text }}>No access</strong>. Organization admins already have full access to
                every workspace.
                {orgAdmins.length > 0 && (
                  <span>
                    {" "}
                    Org admins: {orgAdmins.map((a) => a.full_name || a.email).join(", ")}.
                  </span>
                )}
              </div>
              {loadingWsMatrix && workspaces.length === 0 && (
                <div style={{ color: T.muted, fontSize: 12 }}>Loading workspaces…</div>
              )}
              {!loadingWsMatrix && workspaces.length === 0 && (
                <div style={{ color: T.muted, fontSize: 12 }}>Create a workspace first, then assign members here.</div>
              )}
              {workspaces.length > 0 && orgMembersOnly.length === 0 && (
                <div style={{ color: T.muted, fontSize: 12 }}>
                  No organization members yet. Invite people as <strong style={{ color: T.text }}>Member</strong> (not
                  Admin) to manage workspace-by-workspace access.
                </div>
              )}
              {workspaces.length > 0 && orgMembersOnly.length > 0 && (
                <div style={{ overflowX: "auto", border: `1px solid ${T.border}`, borderRadius: 10, background: T.card }}>
                  <table style={{ borderCollapse: "collapse", fontSize: 11, minWidth: 480 }}>
                    <thead>
                      <tr>
                        <th
                          style={{
                            textAlign: "left",
                            padding: "8px 10px",
                            borderBottom: `1px solid ${T.border}`,
                            color: T.dim,
                            fontWeight: 600,
                            position: "sticky",
                            left: 0,
                            background: T.card,
                            zIndex: 1,
                          }}
                        >
                          Member
                        </th>
                        {workspaces.map((w) => (
                          <th
                            key={w.id}
                            style={{
                              textAlign: "left",
                              padding: "8px 10px",
                              borderBottom: `1px solid ${T.border}`,
                              color: T.dim,
                              fontWeight: 600,
                              whiteSpace: "nowrap",
                              minWidth: 120,
                            }}
                          >
                            {w.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {orgMembersOnly.map((m) => (
                        <tr key={m.user_id}>
                          <td
                            style={{
                              padding: "6px 10px",
                              borderBottom: `1px solid ${T.border}`,
                              color: T.text,
                              position: "sticky",
                              left: 0,
                              background: T.card,
                              zIndex: 1,
                            }}
                          >
                            <div style={{ fontWeight: 600 }}>{m.full_name || m.email}</div>
                            <div style={{ color: T.muted, fontSize: 10 }}>{m.email}</div>
                          </td>
                          {workspaces.map((w) => {
                            const current = wsAccessByUser[m.user_id]?.[w.id] ?? "";
                            const busy = wsMatrixBusyKey === `${m.user_id}:${w.id}`;
                            return (
                              <td key={w.id} style={{ padding: "6px 8px", borderBottom: `1px solid ${T.border}` }}>
                                <select
                                  value={current}
                                  disabled={busy || loadingWsMatrix}
                                  onChange={(e) => {
                                    void setMemberWorkspaceRole(m, w.id, e.target.value);
                                  }}
                                  style={{
                                    width: "100%",
                                    minWidth: 108,
                                    background: T.bg,
                                    border: `1px solid ${T.border}`,
                                    color: T.text,
                                    borderRadius: 6,
                                    fontSize: 10,
                                    padding: "4px 5px",
                                  }}
                                >
                                  {WORKSPACE_ROLE_OPTIONS.map((opt) => (
                                    <option key={opt.value || "none"} value={opt.value}>
                                      {opt.label}
                                    </option>
                                  ))}
                                </select>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        <form onSubmit={invite} style={{ padding: 10 }}>
          <div style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 10, padding: 10 }}>
            <div style={{ color: T.text, fontSize: 20, fontFamily: T.serif }}>Invite team member</div>
            <div style={{ color: T.muted, fontSize: 12, marginTop: 3 }}>
              <strong style={{ color: T.text }}>Admin</strong> can manage the whole organization. <strong style={{ color: T.text }}>Member</strong>{" "}
              joins the org only—set per-workspace roles in <strong style={{ color: T.text }}>Workspace access</strong> (org
              admins only).
            </div>

            <div style={{ marginTop: 10 }}>
              <div style={{ color: T.dim, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>Email address</div>
              <input value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="colleague@yourcompany.com" style={{ width: "100%", background: T.bg, border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "8px 9px", fontSize: 12 }} />
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
              <select value={orgId} onChange={(e) => setOrgId(e.target.value)} style={{ width: "100%", background: T.bg, border: `1px solid ${T.border}`, color: T.text, borderRadius: 8, padding: "8px 9px", fontSize: 12 }}>
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

            <div style={{ marginTop: 12, borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
              <div style={{ color: T.text, fontSize: 12, fontWeight: 600 }}>Accept invite token (local/dev)</div>
              <div style={{ color: T.muted, fontSize: 10, marginTop: 4, lineHeight: 1.5 }}>
                Sign in as the invited email, then paste the token from invite/resend and submit.
              </div>
              <input
                value={acceptToken}
                onChange={(e) => setAcceptToken(e.target.value)}
                placeholder="Paste invite token"
                style={{
                  width: "100%",
                  marginTop: 8,
                  background: T.bg,
                  border: `1px solid ${T.border}`,
                  color: T.text,
                  borderRadius: 8,
                  padding: "8px 9px",
                  fontSize: 11,
                }}
              />
              <button
                type="button"
                disabled={!acceptToken.trim() || acceptingInvite}
                onClick={(e) => {
                  void acceptInviteToken(e);
                }}
                style={{
                  width: "100%",
                  marginTop: 8,
                  border: `1px solid ${T.border}`,
                  borderRadius: 8,
                  padding: "7px 10px",
                  background: "transparent",
                  color: T.text,
                  fontWeight: 600,
                  fontSize: 11,
                  cursor: acceptingInvite ? "not-allowed" : "pointer",
                  opacity: acceptingInvite ? 0.65 : 1,
                }}
              >
                {acceptingInvite ? "Accepting…" : "Accept invite token"}
              </button>
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
