import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
type Org = { id: string; name: string; slug?: string };
type Member = { user_id: string; email: string; full_name?: string | null; role: string };

async function apiError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: string; error?: { message?: string } };
    return body.error?.message ?? body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export function OrganizationsPage() {
  const { api } = useSession(); const [orgs, setOrgs] = useState<Org[]>([]), [org, setOrg] = useState("");
  const [members, setMembers] = useState<Member[]>([]), [name, setName] = useState(""), [email, setEmail] = useState("");
  const [inviteToken, setInviteToken] = useState(""), [acceptToken, setAcceptToken] = useState(""), [message, setMessage] = useState("");
  async function load() { const r = await api.request(`${apiBaseUrl}/organizations`); if (r.ok) setOrgs(await r.json()); }
  async function select(id: string) { setOrg(id); if (!id) return setMembers([]); const r = await api.request(`${apiBaseUrl}/organizations/${id}/members`); if (r.ok) setMembers(await r.json()); else setMessage(await apiError(r, "Could not load organization members")); }
  useEffect(() => { void load(); }, []);
  async function create(e: FormEvent) { e.preventDefault(); const r = await api.request(`${apiBaseUrl}/organizations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }); setMessage(r.ok ? "Organization created" : "Could not create organization"); if (r.ok) { setName(""); await load(); } }
  async function invite(e: FormEvent) { e.preventDefault(); const r = await api.request(`${apiBaseUrl}/organizations/${org}/invites`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, role: "member" }) }); if (!r.ok) return setMessage(await apiError(r, "Could not create invitation")); const b = await r.json(); setInviteToken(b.invite_token); setEmail(""); setMessage("Invitation created. Send the token to the invitee."); }
  async function accept(e: FormEvent) { e.preventDefault(); const token = acceptToken.trim(); if (!token) return setMessage("Paste an invitation token."); const r = await api.request(`${apiBaseUrl}/organizations/invites/accept`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ invite_token: token }) }); setMessage(r.ok ? "Invitation accepted" : await apiError(r, "Could not accept invitation")); if (r.ok) { setAcceptToken(""); await load(); } }
  async function role(m: Member, value: string) { const r = await api.request(`${apiBaseUrl}/organizations/${org}/members/${m.user_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: value }) }); setMessage(r.ok ? "Member role updated" : "Could not update member role"); if (r.ok) await select(org); }
  async function transfer(m: Member) { if (!window.confirm(`Transfer ownership to ${m.email}?`)) return; const r = await api.request(`${apiBaseUrl}/organizations/${org}/transfer-ownership`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_owner_user_id: m.user_id }) }); setMessage(r.ok ? "Ownership transferred" : "Could not transfer ownership"); if (r.ok) await select(org); }
  async function remove(m: Member) { if (!window.confirm(`Remove ${m.email} from this organization?`)) return; const r = await api.request(`${apiBaseUrl}/organizations/${org}/members/${m.user_id}`, { method: "DELETE" }); setMessage(r.ok ? "Member removed" : "Could not remove member"); if (r.ok) await select(org); }
  return <WorkspaceLayout title="Organizations & members" description="Manage organization membership, invitations, and roles." message={message}>
    <section className="toolbar card"><select value={org} onChange={e => void select(e.target.value)}><option value="">Select an organization</option>{orgs.map(o => <option value={o.id} key={o.id}>{o.name}</option>)}</select><form className="create-form" onSubmit={create}><input placeholder="New organization name" value={name} onChange={e => setName(e.target.value)} required /><button>Create organization</button></form></section>
    <section className="card"><h2>Accept an invitation</h2><p className="muted">Sign in with the same email address that received the invitation, then paste the complete token.</p><form className="create-form" onSubmit={accept}><input placeholder="Invitation token" value={acceptToken} onChange={e => setAcceptToken(e.target.value)} required /><button>Accept invite</button></form></section>
    {org && <section className="card"><h2>Invite a member</h2><form className="create-form" onSubmit={invite}><input type="email" placeholder="Member email" value={email} onChange={e => setEmail(e.target.value)} required /><button>Send invite</button></form>{inviteToken && <p className="notice">Invite token: <code>{inviteToken}</code></p>}<h2>Members</h2>{members.map(m => <div className="admin-row" key={m.user_id}><span>{m.full_name || m.email}</span><select value={m.role} onChange={e => void role(m, e.target.value)}><option value="member">member</option><option value="admin">admin</option><option value="owner">owner</option></select><button className="secondary" onClick={() => void transfer(m)}>Transfer ownership</button><button className="danger" onClick={() => void remove(m)}>Remove</button></div>)}</section>}
  </WorkspaceLayout>;
}
