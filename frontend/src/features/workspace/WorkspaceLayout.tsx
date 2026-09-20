import { ReactNode, useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { apiBaseUrl } from "../../shared/api/client";
import { useSession } from "../../shared/session/SessionProvider";

type Profile = { is_platform_admin: boolean; full_name?: string | null };
export function WorkspaceLayout({ title, description, children, message }: { title: string; description: string; children: ReactNode; message?: string }) {
  const { api, clear } = useSession(); const navigate = useNavigate(); const [profile, setProfile] = useState<Profile | null>(null);
  useEffect(() => { void api.request(`${apiBaseUrl}/users/me`).then(async r => r.ok && setProfile(await r.json())); }, [api]);
  async function logout() { const refresh = localStorage.getItem("linkhub_refresh_token"); if (refresh) await fetch(`${apiBaseUrl}/auth/logout`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }) }); clear(); navigate("/auth"); }
  return <main className="app-shell"><header className="topbar"><div><p className="eyebrow">LINKHUB</p><h1>{title}</h1></div><button className="secondary" onClick={() => void logout()}>Sign out</button></header><nav className="route-nav" aria-label="Workspace navigation"><NavLink to="/workspace/links" end>Links</NavLink><NavLink to="/organizations">Organizations</NavLink><NavLink to="/analytics">Analytics</NavLink><NavLink to="/profile">Profile</NavLink><NavLink to="/settings">Settings</NavLink><NavLink to="/api-keys">API keys</NavLink>{profile?.is_platform_admin && <NavLink to="/admin">Admin</NavLink>}</nav><section className="route-view-intro"><h2>{title}</h2><p className="muted">{description}</p></section>{message && <p className="notice">{message}</p>}{children}</main>;
}
