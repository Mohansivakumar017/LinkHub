import { ReactNode, useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { apiBaseUrl } from "../../shared/api/client";
import { useSession } from "../../shared/session/SessionProvider";
import { useSelectedOrganization } from "../../shared/session/organization";
import { readApiErrorMessage } from "../../shared/api/errors";
import { WorkspaceFeedback } from "../../shared/components/WorkspaceFeedback";

type Profile = { is_platform_admin: boolean; full_name?: string | null };
type Organization = { id: string; name: string };

export function WorkspaceLayout({ title, description, children, message }: { title: string; description: string; children: ReactNode; message?: string }) {
  const { api, clear } = useSession(); const navigate = useNavigate(); const [profile, setProfile] = useState<Profile | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [workspaceError, setWorkspaceError] = useState("");
  const { organizationId, selectOrganization } = useSelectedOrganization();

  useEffect(() => {
    void api.request(`${apiBaseUrl}/users/me`).then(async r => r.ok && setProfile(await r.json()));
    void api.request(`${apiBaseUrl}/organizations`).then(async r => {
      if (r.ok) {
        const items = await r.json() as Organization[];
        setOrganizations(items);
        setWorkspaceError("");
        if (organizationId && !items.some(item => item.id === organizationId)) {
          selectOrganization("");
        }
      } else setWorkspaceError(await readApiErrorMessage(r, "Could not load organizations."));
    });
  }, [api, organizationId]);

  async function logout() {
    const refresh = localStorage.getItem("linkhub_refresh_token");
    let signOutWarning = "";
    if (refresh) {
      try {
        const response = await fetch(`${apiBaseUrl}/auth/logout`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!response.ok) {
          signOutWarning = `You are signed out on this device, but server-side token revocation failed: ${await readApiErrorMessage(response, "request failed")}`;
        }
      } catch {
        signOutWarning = "You are signed out on this device, but LinkHub could not confirm server-side token revocation. Try again when the service is available.";
      }
    }
    clear();
    navigate("/auth", {
      replace: true,
      state: signOutWarning ? { signOutWarning } : null,
    });
  }
  return <main className="workspace-shell">
    <aside className="workspace-sidebar">
      <div className="workspace-brand"><span className="brand-mark-small">↗</span><div><strong>LinkHub</strong><small>Link operations platform</small></div></div>
      <label className="workspace-org-picker">Active organization
        <select value={organizationId} onChange={event => selectOrganization(event.target.value)}>
          <option value="">All organizations</option>
          {organizations.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}
        </select>
      </label>
      <nav className="workspace-nav" aria-label="Workspace navigation">
        <span className="workspace-nav-label">Workspace</span>
        <NavLink to="/workspace/links" end><span>↗</span> Links</NavLink>
        <NavLink to="/analytics"><span>◒</span> Analytics</NavLink>
        <span className="workspace-nav-label">Administration</span>
        <NavLink to="/organizations"><span>◎</span> Team & organizations</NavLink>
        <NavLink to="/api-keys"><span>⌘</span> API keys</NavLink>
        {profile?.is_platform_admin && <NavLink to="/admin"><span>▦</span> Platform admin</NavLink>}
        <span className="workspace-nav-label">Personal</span>
        <NavLink to="/profile"><span>◯</span> Profile</NavLink>
        <NavLink to="/settings"><span>⚙</span> Settings</NavLink>
      </nav>
      <div className="workspace-sidebar-footer"><div className="workspace-user"><span>{(profile?.full_name ?? "U").slice(0, 1).toUpperCase()}</span><div><strong>{profile?.full_name ?? "Workspace user"}</strong><small>Account settings</small></div></div><button className="sidebar-signout" onClick={() => void logout()}>Sign out</button></div>
    </aside>
    <section className="workspace-content">
      <header className="workspace-header"><div><p className="eyebrow">WORKSPACE</p><h1>{title}</h1><p className="muted">{description}</p></div><div className="workspace-header-context">{organizations.find(item => item.id === organizationId)?.name ?? "All organizations"}</div></header>
      {message && <WorkspaceFeedback kind="success" message={message} onDismiss={() => undefined} />}
      {workspaceError && <WorkspaceFeedback kind="error" message={workspaceError} onDismiss={() => setWorkspaceError("")} />}
      {children}
    </section>
  </main>;
}
