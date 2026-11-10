import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { useSelectedOrganization } from "../../../shared/session/organization";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";
import { useLocation } from "react-router-dom";
type Org = { id: string; name: string; slug?: string; role: "owner" | "admin" | "member" };
type Member = { user_id: string; email: string; full_name?: string | null; role: string };
type Invite = { id: string; invited_email: string; role: string; expires_at: string; created_at: string; is_expired: boolean };
type AuditLog = { id: string; action: string; resource_type: string; resource_id?: string | null; created_at: string };

export function OrganizationsPage() {
  const { api } = useSession(); const [orgs, setOrgs] = useState<Org[]>([]);
  const location = useLocation();
  const { organizationId: org, selectOrganization } = useSelectedOrganization();
  const currentRole = orgs.find(item => item.id === org)?.role;
  const [members, setMembers] = useState<Member[]>([]), [name, setName] = useState(""), [email, setEmail] = useState("");
  const [invites, setInvites] = useState<Invite[]>([]), [inviteRole, setInviteRole] = useState("member");
  const [canManageInvites, setCanManageInvites] = useState(false), [invitesLoading, setInvitesLoading] = useState(false);
  const [inviteToken, setInviteToken] = useState(""), [acceptToken, setAcceptToken] = useState(""), [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true), [membersLoading, setMembersLoading] = useState(false), [error, setError] = useState("");
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]), [auditLoading, setAuditLoading] = useState(false);
  const [auditAction, setAuditAction] = useState(""), [auditResourceType, setAuditResourceType] = useState("");
  const [confirmation, setConfirmation] = useState<{ member: Member; action: "transfer" | "remove" } | { invite: Invite; action: "revoke-invite" } | null>(null);
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    const invite = new URLSearchParams(location.search).get("invite");
    if (invite) setAcceptToken(invite);
  }, [location.search]);
  async function load() { setLoading(true); const r = await api.request(`${apiBaseUrl}/organizations`); if (r.ok) { setOrgs(await r.json()); setError(""); } else setError(await readApiErrorMessage(r, "Could not load organizations.")); setLoading(false); }
  async function loadAudit(id: string, action = auditAction, resourceType = auditResourceType) {
    if (!id) return setAuditLogs([]);
    setAuditLoading(true);
    const query = new URLSearchParams({ ...(action && { action }), ...(resourceType && { resource_type: resourceType }) });
    const r = await api.request(`${apiBaseUrl}/organizations/${id}/audit-logs?${query}`);
    if (r.ok) setAuditLogs((await r.json()).items); else setError(await readApiErrorMessage(r, "Could not load audit activity."));
    setAuditLoading(false);
  }
  async function loadInvites(id: string) {
    if (!id) { setInvites([]); setCanManageInvites(false); return; }
    setInvitesLoading(true);
    const response = await api.request(`${apiBaseUrl}/organizations/${id}/invites`);
    if (response.ok) {
      setInvites(await response.json());
      setCanManageInvites(true);
    } else if (response.status === 403) {
      setInvites([]);
      setCanManageInvites(false);
    } else {
      setError(await readApiErrorMessage(response, "Could not load invitations."));
    }
    setInvitesLoading(false);
  }
  async function select(id: string) {
    selectOrganization(id); setError(""); setAuditAction(""); setAuditResourceType("");
    setInviteToken("");
    if (orgs.find(item => item.id === id)?.role !== "owner") setInviteRole("member");
    if (!id) return setMembers([]), setAuditLogs([]), setInvites([]), setCanManageInvites(false);
    setMembersLoading(true);
    const [membersResponse] = await Promise.all([
      api.request(`${apiBaseUrl}/organizations/${id}/members`),
      loadAudit(id, "", ""),
      loadInvites(id),
    ]);
    if (membersResponse.ok) setMembers(await membersResponse.json()); else setError(await readApiErrorMessage(membersResponse, "Could not load organization members."));
    setMembersLoading(false);
  }
  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (org) {
      void select(org);
    } else {
      setMembers([]);
      setAuditLogs([]);
    }
  }, [org]);
  async function create(e: FormEvent) {
    e.preventDefault();
    setError(""); setMessage("");
    const r = await api.request(`${apiBaseUrl}/organizations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
    if (!r.ok) { setError(await readApiErrorMessage(r, "Could not create organization.")); return; }
    setMessage("Organization created.");
    if (r.ok) {
      const created = await r.json() as { id: string };
      setName("");
      selectOrganization(created.id);
      await load();
    }
  }
  async function invite(e: FormEvent) {
    e.preventDefault(); setError(""); setMessage("");
    const response = await api.request(`${apiBaseUrl}/organizations/${org}/invites`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, role: inviteRole }) });
    if (!response.ok) {
      setError(await readApiErrorMessage(response, "Could not send invitation. It may have been saved; check pending invitations and retry delivery."));
      await loadInvites(org);
      return;
    }
    const result = await response.json() as { invite_token: string };
    setInviteToken(result.invite_token);
    setEmail("");
    setMessage("Invitation created and sent by email. The token is available below as a manual fallback.");
    await loadInvites(org);
  }
  async function resendInvite(invite: Invite) {
    setError(""); setMessage("");
    const response = await api.request(`${apiBaseUrl}/organizations/${org}/invites/${invite.id}/resend`, { method: "POST" });
    if (!response.ok) {
      setError(await readApiErrorMessage(response, "Could not resend invitation. You can retry from the pending invitations list."));
      await loadInvites(org);
      return;
    }
    const result = await response.json() as { invite_token: string };
    setInviteToken(result.invite_token);
    setMessage(`Invitation resent to ${invite.invited_email}.`);
    await loadInvites(org);
  }
  async function revokeInvite(invite: Invite) {
    setError(""); setMessage("");
    const response = await api.request(`${apiBaseUrl}/organizations/${org}/invites/${invite.id}`, { method: "DELETE" });
    if (!response.ok) { setError(await readApiErrorMessage(response, "Could not revoke invitation.")); return false; }
    setMessage(`Invitation for ${invite.invited_email} revoked.`);
    await loadInvites(org);
    return true;
  }
  async function accept(e: FormEvent) { e.preventDefault(); setError(""); setMessage(""); const token = acceptToken.trim(); if (!token) return setError("Paste an invitation token."); const r = await api.request(`${apiBaseUrl}/organizations/invites/accept`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ invite_token: token }) }); if (!r.ok) return setError(await readApiErrorMessage(r, "Could not accept invitation.")); setMessage("Invitation accepted."); setAcceptToken(""); await load(); }
  async function role(m: Member, value: string) { setError(""); setMessage(""); const r = await api.request(`${apiBaseUrl}/organizations/${org}/members/${m.user_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: value }) }); if (!r.ok) return setError(await readApiErrorMessage(r, "Could not update member role.")); setMessage("Member role updated."); await select(org); }
  async function transfer(m: Member) {
    setError(""); setMessage("");
    const r = await api.request(`${apiBaseUrl}/organizations/${org}/transfer-ownership`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_owner_user_id: m.user_id }) });
    if (!r.ok) { setError(await readApiErrorMessage(r, "Could not transfer ownership.")); return false; }
    setMessage("Organization ownership transferred.");
    await load();
    await select(org);
    return true;
  }
  async function remove(m: Member) {
    setError(""); setMessage("");
    const r = await api.request(`${apiBaseUrl}/organizations/${org}/members/${m.user_id}`, { method: "DELETE" });
    if (!r.ok) { setError(await readApiErrorMessage(r, "Could not remove member.")); return false; }
    setMessage("Member removed.");
    await select(org);
    return true;
  }
  async function confirmAction() {
    if (!confirmation) return;
    setConfirming(true);
    const completed = confirmation.action === "revoke-invite"
      ? await revokeInvite(confirmation.invite)
      : confirmation.action === "transfer"
        ? await transfer(confirmation.member)
        : await remove(confirmation.member);
    setConfirming(false);
    if (completed) setConfirmation(null);
  }
  return <WorkspaceLayout title="Organizations & members" description="Manage organization membership, invitations, and roles." message={message}>
    {confirmation && <ConfirmDialog title={confirmation.action === "transfer" ? "Transfer ownership?" : confirmation.action === "remove" ? "Remove member?" : "Revoke invitation?"} message={"invite" in confirmation ? `${confirmation.invite.invited_email} will no longer be able to join using this invitation.` : confirmation.action === "transfer" ? `${confirmation.member.email} will become the organization owner.` : `${confirmation.member.email} will lose access to this organization.`} confirmLabel={confirmation.action === "transfer" ? "Transfer ownership" : confirmation.action === "remove" ? "Remove member" : "Revoke invitation"} danger={confirmation.action !== "transfer"} busy={confirming} onCancel={() => setConfirmation(null)} onConfirm={() => void confirmAction()} />}
    {error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}
    <section className="toolbar organization-toolbar card"><label>Organization<select value={org} onChange={e => void selectOrganization(e.target.value)}><option value="">Select an organization</option>{orgs.map(o => <option value={o.id} key={o.id}>{o.name}</option>)}</select></label>{org && <div className="organization-context"><strong>{orgs.find(item => item.id === org)?.name}</strong><span>Organization ID</span><code>{org}</code></div>}<form className="create-form" onSubmit={create}><label>New organization<input placeholder="Organization name" value={name} onChange={e => setName(e.target.value)} required /></label><button>Create organization</button></form></section>
    {loading && <section className="card"><p className="muted">Loading organizations…</p></section>}
    {!loading && !orgs.length && <section className="card empty-state"><h2>No organizations yet</h2><p className="muted">Create your first organization to manage links and invite your team.</p></section>}
    <section className="card"><h2>Accept an invitation</h2><p className="muted">Sign in with the same email address that received the invitation, then paste the complete token.</p><form className="create-form" onSubmit={accept}><input placeholder="Invitation token" value={acceptToken} onChange={e => setAcceptToken(e.target.value)} required /><button>Accept invite</button></form></section>
    {org && <section className="card">{canManageInvites && <><h2>Invite a member</h2><form className="create-form" onSubmit={invite}><input type="email" placeholder="Member email" value={email} onChange={e => setEmail(e.target.value)} required /><select aria-label="Invitation role" value={inviteRole} onChange={e => setInviteRole(e.target.value)}><option value="member">member</option>{currentRole === "owner" && <option value="admin">admin</option>}</select><button>Send invite</button></form>{invitesLoading ? <p className="muted">Loading invitations…</p> : <><h2>Pending invitations</h2>{!invites.length ? <p className="muted">No pending invitations.</p> : invites.map(invite => <div className="admin-row" key={invite.id}><span><strong>{invite.invited_email}</strong><small>{invite.role} · {invite.is_expired ? "Expired" : `Expires ${new Date(invite.expires_at).toLocaleString()}`}</small></span><button className="secondary" onClick={() => void resendInvite(invite)}>Resend</button><button className="danger" onClick={() => setConfirmation({ invite, action: "revoke-invite" })}>Revoke</button></div>)}</>}</>}{inviteToken && <p className="notice" role="status">Manual invite token: <code>{inviteToken}</code></p>}<h2>Members</h2>{membersLoading ? <p className="muted">Loading members…</p> : !members.length ? <p className="muted">No members found for this organization.</p> : members.map(m => <div className="admin-row" key={m.user_id}><span>{m.full_name || m.email}</span>{currentRole === "owner" && m.role !== "owner" ? <select aria-label={`Role for ${m.email}`} value={m.role} onChange={e => void role(m, e.target.value)}><option value="member">member</option><option value="admin">admin</option></select> : <span>{m.role}</span>}{currentRole === "owner" && m.role !== "owner" && <button className="secondary" onClick={() => setConfirmation({ member: m, action: "transfer" })}>Transfer ownership</button>}{(currentRole === "owner" && m.role !== "owner" || currentRole === "admin" && m.role === "member") && <button className="danger" onClick={() => setConfirmation({ member: m, action: "remove" })}>Remove</button>}</div>)}</section>}
    {org && <section className="card"><div className="section-heading"><div><h2>Organization activity</h2><p className="muted">Recent organization-level changes visible to members.</p></div><button className="secondary" onClick={() => void loadAudit(org)}>Refresh</button></div><div className="filter-row"><label>Action<input value={auditAction} onChange={e => setAuditAction(e.target.value)} placeholder="organization.created" /></label><label>Resource type<select value={auditResourceType} onChange={e => setAuditResourceType(e.target.value)}><option value="">All</option><option value="organization">Organization</option></select></label><button className="secondary" onClick={() => void loadAudit(org)}>Apply filters</button></div>{auditLoading ? <p className="muted">Loading activity…</p> : !auditLogs.length ? <p className="muted">No organization activity found.</p> : <div className="audit-list">{auditLogs.map(log => <div className="admin-row" key={log.id}><span><strong>{log.action}</strong><small>{new Date(log.created_at).toLocaleString()}</small></span><code>{log.resource_type}</code></div>)}</div>}</section>}
  </WorkspaceLayout>;
}
