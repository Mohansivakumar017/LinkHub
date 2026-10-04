import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { useSelectedOrganization } from "../../../shared/session/organization";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";
type Org = { id: string; name: string; slug?: string };
type Member = { user_id: string; email: string; full_name?: string | null; role: string };
type AuditLog = { id: string; action: string; resource_type: string; resource_id?: string | null; created_at: string };

export function OrganizationsPage() {
  const { api } = useSession(); const [orgs, setOrgs] = useState<Org[]>([]);
  const { organizationId: org, selectOrganization } = useSelectedOrganization();
  const [members, setMembers] = useState<Member[]>([]), [name, setName] = useState(""), [email, setEmail] = useState("");
  const [inviteToken, setInviteToken] = useState(""), [acceptToken, setAcceptToken] = useState(""), [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true), [membersLoading, setMembersLoading] = useState(false), [error, setError] = useState("");
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]), [auditLoading, setAuditLoading] = useState(false);
  const [auditAction, setAuditAction] = useState(""), [auditResourceType, setAuditResourceType] = useState("");
  const [confirmation, setConfirmation] = useState<{ member: Member; action: "transfer" | "remove" } | null>(null);
  const [confirming, setConfirming] = useState(false);
  async function load() { setLoading(true); const r = await api.request(`${apiBaseUrl}/organizations`); if (r.ok) { setOrgs(await r.json()); setError(""); } else setError(await readApiErrorMessage(r, "Could not load organizations.")); setLoading(false); }
  async function loadAudit(id: string, action = auditAction, resourceType = auditResourceType) {
    if (!id) return setAuditLogs([]);
    setAuditLoading(true);
    const query = new URLSearchParams({ ...(action && { action }), ...(resourceType && { resource_type: resourceType }) });
    const r = await api.request(`${apiBaseUrl}/organizations/${id}/audit-logs?${query}`);
    if (r.ok) setAuditLogs((await r.json()).items); else setError(await readApiErrorMessage(r, "Could not load audit activity."));
    setAuditLoading(false);
  }
  async function select(id: string) {
    selectOrganization(id); setError(""); setAuditAction(""); setAuditResourceType("");
    if (!id) return setMembers([]), setAuditLogs([]);
    setMembersLoading(true);
    const [membersResponse] = await Promise.all([
      api.request(`${apiBaseUrl}/organizations/${id}/members`),
      loadAudit(id, "", ""),
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
  async function invite(e: FormEvent) { e.preventDefault(); setError(""); setMessage(""); const r = await api.request(`${apiBaseUrl}/organizations/${org}/invites`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, role: "member" }) }); if (!r.ok) return setError(await readApiErrorMessage(r, "Could not create invitation.")); const b = await r.json(); setInviteToken(b.invite_token); setEmail(""); setMessage("Invitation created. Copy and send the token to the invitee."); }
  async function accept(e: FormEvent) { e.preventDefault(); setError(""); setMessage(""); const token = acceptToken.trim(); if (!token) return setError("Paste an invitation token."); const r = await api.request(`${apiBaseUrl}/organizations/invites/accept`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ invite_token: token }) }); if (!r.ok) return setError(await readApiErrorMessage(r, "Could not accept invitation.")); setMessage("Invitation accepted."); setAcceptToken(""); await load(); }
  async function role(m: Member, value: string) { setError(""); setMessage(""); const r = await api.request(`${apiBaseUrl}/organizations/${org}/members/${m.user_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: value }) }); if (!r.ok) return setError(await readApiErrorMessage(r, "Could not update member role.")); setMessage("Member role updated."); await select(org); }
  async function transfer(m: Member) {
    setError(""); setMessage("");
    const r = await api.request(`${apiBaseUrl}/organizations/${org}/transfer-ownership`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_owner_user_id: m.user_id }) });
    if (!r.ok) { setError(await readApiErrorMessage(r, "Could not transfer ownership.")); return false; }
    setMessage("Organization ownership transferred.");
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
    const completed = confirmation.action === "transfer"
      ? await transfer(confirmation.member)
      : await remove(confirmation.member);
    setConfirming(false);
    if (completed) setConfirmation(null);
  }
  return <WorkspaceLayout title="Organizations & members" description="Manage organization membership, invitations, and roles." message={message}>
    {confirmation && <ConfirmDialog title={confirmation.action === "transfer" ? "Transfer ownership?" : "Remove member?"} message={confirmation.action === "transfer" ? `${confirmation.member.email} will become the organization owner.` : `${confirmation.member.email} will lose access to this organization.`} confirmLabel={confirmation.action === "transfer" ? "Transfer ownership" : "Remove member"} danger={confirmation.action === "remove"} busy={confirming} onCancel={() => setConfirmation(null)} onConfirm={() => void confirmAction()} />}
    {error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}
    <section className="toolbar organization-toolbar card"><label>Organization<select value={org} onChange={e => void selectOrganization(e.target.value)}><option value="">Select an organization</option>{orgs.map(o => <option value={o.id} key={o.id}>{o.name}</option>)}</select></label>{org && <div className="organization-context"><strong>{orgs.find(item => item.id === org)?.name}</strong><span>Organization ID</span><code>{org}</code></div>}<form className="create-form" onSubmit={create}><label>New organization<input placeholder="Organization name" value={name} onChange={e => setName(e.target.value)} required /></label><button>Create organization</button></form></section>
    {loading && <section className="card"><p className="muted">Loading organizations…</p></section>}
    {!loading && !orgs.length && <section className="card empty-state"><h2>No organizations yet</h2><p className="muted">Create your first organization to manage links and invite your team.</p></section>}
    <section className="card"><h2>Accept an invitation</h2><p className="muted">Sign in with the same email address that received the invitation, then paste the complete token.</p><form className="create-form" onSubmit={accept}><input placeholder="Invitation token" value={acceptToken} onChange={e => setAcceptToken(e.target.value)} required /><button>Accept invite</button></form></section>
    {org && <section className="card"><h2>Invite a member</h2><form className="create-form" onSubmit={invite}><input type="email" placeholder="Member email" value={email} onChange={e => setEmail(e.target.value)} required /><button>Send invite</button></form>{inviteToken && <p className="notice" role="status">Invitation created. Share this token with the invitee: <code>{inviteToken}</code></p>}<h2>Members</h2>{membersLoading ? <p className="muted">Loading members…</p> : !members.length ? <p className="muted">No members found for this organization.</p> : members.map(m => <div className="admin-row" key={m.user_id}><span>{m.full_name || m.email}</span><select value={m.role} onChange={e => void role(m, e.target.value)}><option value="member">member</option><option value="admin">admin</option><option value="owner">owner</option></select><button className="secondary" onClick={() => setConfirmation({ member: m, action: "transfer" })}>Transfer ownership</button><button className="danger" onClick={() => setConfirmation({ member: m, action: "remove" })}>Remove</button></div>)}</section>}
    {org && <section className="card"><div className="section-heading"><div><h2>Organization activity</h2><p className="muted">Recent organization-level changes visible to members.</p></div><button className="secondary" onClick={() => void loadAudit(org)}>Refresh</button></div><div className="filter-row"><label>Action<input value={auditAction} onChange={e => setAuditAction(e.target.value)} placeholder="organization.created" /></label><label>Resource type<select value={auditResourceType} onChange={e => setAuditResourceType(e.target.value)}><option value="">All</option><option value="organization">Organization</option></select></label><button className="secondary" onClick={() => void loadAudit(org)}>Apply filters</button></div>{auditLoading ? <p className="muted">Loading activity…</p> : !auditLogs.length ? <p className="muted">No organization activity found.</p> : <div className="audit-list">{auditLogs.map(log => <div className="admin-row" key={log.id}><span><strong>{log.action}</strong><small>{new Date(log.created_at).toLocaleString()}</small></span><code>{log.resource_type}</code></div>)}</div>}</section>}
  </WorkspaceLayout>;
}
