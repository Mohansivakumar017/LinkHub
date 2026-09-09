import { FormEvent, useEffect, useState } from "react";

type LinkItem = {
  id: string;
  short_code: string;
  original_url: string;
  title?: string | null;
  custom_alias?: string | null;
  is_archived: boolean;
};

type Organization = {
  id: string;
  name: string;
  slug: string;
};

type Overview = {
  total_clicks: number;
  unique_clicks: number;
  range_days: number;
};

type Profile = {
  email: string;
  full_name?: string | null;
  avatar_url?: string | null;
  is_email_verified: boolean;
  is_platform_admin: boolean;
};

type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  last_used_at?: string | null;
  created_at: string;
  usage_count: number;
};

type AnalyticsRow = { bucket?: string; value?: string; count: number };
type OrganizationMember = { user_id: string; email: string; full_name: string; role: string };
type AdminOrganization = { id: string; name: string; slug: string; created_at: string };
type AdminLink = {
  id: string;
  short_code: string;
  organization_id: string;
  is_archived: boolean;
  is_deleted: boolean;
  created_at: string;
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const publicBase = apiBase.replace(/\/api\/v1$/, "");

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("linkhub_access_token") ?? "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [recoveryToken, setRecoveryToken] = useState("");
  const [adminMetrics, setAdminMetrics] = useState<Record<string, number> | null>(null);
  const [adminUsers, setAdminUsers] = useState<{ email: string; full_name?: string | null; is_active: boolean }[]>([]);
  const [adminLogs, setAdminLogs] = useState<{ action: string; resource_type: string; created_at: string }[]>([]);
  const [adminOrganizations, setAdminOrganizations] = useState<AdminOrganization[]>([]);
  const [adminLinks, setAdminLinks] = useState<AdminLink[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [links, setLinks] = useState<LinkItem[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [organizationName, setOrganizationName] = useState("");
  const [message, setMessage] = useState("");
  const [target, setTarget] = useState("");
  const [linkTitle, setLinkTitle] = useState("");
  const [linkAlias, setLinkAlias] = useState("");
  const [linkExpiresAt, setLinkExpiresAt] = useState("");
  const [linkPassword, setLinkPassword] = useState("");
  const [linkClickLimit, setLinkClickLimit] = useState("");
  const [linkOneTime, setLinkOneTime] = useState(false);
  const [linkPrivate, setLinkPrivate] = useState(false);
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileName, setProfileName] = useState("");
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeyName, setApiKeyName] = useState("");
  const [newApiKey, setNewApiKey] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [acceptInviteToken, setAcceptInviteToken] = useState("");
  const [selectedLinks, setSelectedLinks] = useState<string[]>([]);
  const [bulkCsv, setBulkCsv] = useState("");
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [timeSeries, setTimeSeries] = useState<AnalyticsRow[]>([]);
  const [breakdown, setBreakdown] = useState<AnalyticsRow[]>([]);
  const [breakdownDimension, setBreakdownDimension] = useState("browser");

  const authHeaders = { Authorization: `Bearer ${token}` };

  async function apiFetch(
    input: RequestInfo | URL,
    init: RequestInit = {},
  ): Promise<Response> {
    const accessToken = localStorage.getItem("linkhub_access_token") ?? token;
    const headers = new Headers(init.headers);
    if (accessToken) {
      headers.set("Authorization", `Bearer ${accessToken}`);
    }

    let response = await fetch(input, { ...init, headers });
    if (response.status !== 401) {
      return response;
    }

    const refreshToken = localStorage.getItem("linkhub_refresh_token");
    if (!refreshToken) {
      return response;
    }
    const refreshResponse = await fetch(`${apiBase}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!refreshResponse.ok) {
      localStorage.removeItem("linkhub_access_token");
      localStorage.removeItem("linkhub_refresh_token");
      setToken("");
      return response;
    }
    const refreshed = await refreshResponse.json() as {
      access_token: string;
      refresh_token: string;
    };
    localStorage.setItem("linkhub_access_token", refreshed.access_token);
    localStorage.setItem("linkhub_refresh_token", refreshed.refresh_token);
    setToken(refreshed.access_token);
    headers.set("Authorization", `Bearer ${refreshed.access_token}`);
    response = await fetch(input, { ...init, headers });
    return response;
  }

  async function loadOrganizations(accessToken = token) {
    const response = await apiFetch(`${apiBase}/organizations`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) {
      setMessage("Could not load organizations");
      return;
    }

    const items = (await response.json()) as Organization[];
    setOrganizations(items);
    if (!organizationId && items.length > 0) {
      setOrganizationId(items[0].id);
    }
  }

  async function loadProfile(): Promise<Profile | null> {
    const response = await apiFetch(`${apiBase}/users/me`);
    if (!response.ok) return null;
    const body = (await response.json()) as Profile;
    setProfile(body);
    setProfileName(body.full_name ?? "");
    return body;
  }

  async function loadApiKeys() {
    const response = await apiFetch(`${apiBase}/api-keys`);
    if (response.ok) {
      setApiKeys((await response.json()) as ApiKey[]);
    }

  }

  async function loadMembers(id = organizationId) {
    if (!id) return;
    const response = await apiFetch(`${apiBase}/organizations/${id}/members`);
    if (response.ok) setMembers((await response.json()) as OrganizationMember[]);
  }

  async function loadAdminMetrics() {
    const response = await apiFetch(`${apiBase}/admin/metrics`);
    if (response.ok) setAdminMetrics((await response.json()) as Record<string, number>);
    const usersResponse = await apiFetch(`${apiBase}/admin/users?limit=10`);
    if (usersResponse.ok) {
      const body = await usersResponse.json() as { items: typeof adminUsers };
      setAdminUsers(body.items);
    }
    const logsResponse = await apiFetch(`${apiBase}/admin/audit-logs?limit=10`);
    if (logsResponse.ok) {
      const body = await logsResponse.json() as { items: typeof adminLogs };
      setAdminLogs(body.items);
    }
    const organizationsResponse = await apiFetch(`${apiBase}/admin/organizations?limit=10`);
    if (organizationsResponse.ok) {
      const body = await organizationsResponse.json() as { items: AdminOrganization[] };
      setAdminOrganizations(body.items);
    }
    const linksResponse = await apiFetch(`${apiBase}/admin/links?limit=10`);
    if (linksResponse.ok) {
      const body = await linksResponse.json() as { items: AdminLink[] };
      setAdminLinks(body.items);
    }
  }

  async function login(event: FormEvent) {
    event.preventDefault();
    if (isVerifying) {
      const response = await fetch(`${apiBase}/auth/verify-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: recoveryToken }),
      });
      setMessage(response.ok ? "Email verified. You can sign in." : "Invalid or expired verification token");
      return;
    }
    if (isResetting) {
      const response = await fetch(`${apiBase}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: recoveryToken, new_password: password }),
      });
      if (response.ok) {
        setIsResetting(false);
        setIsRecovering(false);
        setRecoveryToken("");
        setPassword("");
        setMessage("Password reset. You can sign in.");
      } else {
        setMessage("Invalid or expired reset token");
      }
      return;
    }
    if (isRecovering) {
      const response = await fetch(`${apiBase}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setMessage(response.ok ? "If the account exists, a reset email was sent." : "Could not request password reset");
      return;
    }
    const response = await fetch(`${apiBase}/auth/${isRegistering ? "register" : "login"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    if (!response.ok) {
      setMessage(response.status === 403
        ? "Verify your email before signing in. Use the verification link or resend it."
        : "Login failed");
      return;
    }
    if (isRegistering) {
      setIsRegistering(false);
      setMessage("Account created. Sign in to continue.");
      return;
    }
    const body = await response.json();
    localStorage.setItem("linkhub_access_token", body.access_token);
    localStorage.setItem("linkhub_refresh_token", body.refresh_token);
    setToken(body.access_token);
    setMessage("Signed in");
    await loadOrganizations(body.access_token);
    const loadedProfile = await loadProfile();
    await loadApiKeys();
    if (loadedProfile?.is_platform_admin) await loadAdminMetrics();
  }

  async function resendVerification() {
    const response = await fetch(`${apiBase}/auth/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setMessage(response.ok ? "If the account exists and is unverified, a verification email was sent." : "Could not resend verification email");
  }

  async function logout() {
    const refreshToken = localStorage.getItem("linkhub_refresh_token");
    if (refreshToken) {
      await fetch(`${apiBase}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    }
    localStorage.removeItem("linkhub_access_token");
    localStorage.removeItem("linkhub_refresh_token");
    setToken("");
  }

  useEffect(() => {
    if (token) {
      void loadOrganizations(token);
      void (async () => {
        const loadedProfile = await loadProfile();
        if (loadedProfile?.is_platform_admin) await loadAdminMetrics();
      })();
      void loadApiKeys();
    }
  }, [token]);

  useEffect(() => {
    if (token && organizationId) {
      void loadMembers();
    }
  }, [token, organizationId]);

  async function updateMemberRole(member: OrganizationMember, role: string) {
    const response = await apiFetch(
      `${apiBase}/organizations/${organizationId}/members/${member.user_id}`,
      {
        method: "PATCH",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      },
    );
    setMessage(response.ok ? "Member role updated" : "Could not update member role");
    if (response.ok) await loadMembers();
  }

  async function transferOwnership(member: OrganizationMember) {
    if (!window.confirm(`Transfer ownership to ${member.email}?`)) return;
    const response = await apiFetch(
      `${apiBase}/organizations/${organizationId}/transfer-ownership`,
      {
        method: "POST",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ new_owner_user_id: member.user_id }),
      },
    );
    setMessage(response.ok ? "Ownership transferred" : "Could not transfer ownership");
    if (response.ok) await loadMembers();
  }

  async function updateProfile(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch(`${apiBase}/users/me`, {
      method: "PATCH",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: profileName }),
    });
    setMessage(response.ok ? "Profile updated" : "Could not update profile");
    if (response.ok) await loadProfile();
  }

  async function uploadAvatar(event: FormEvent) {
    event.preventDefault();
    if (!avatarFile) return;
    const form = new FormData();
    form.append("file", avatarFile);
    const response = await apiFetch(`${apiBase}/users/me/avatar`, {
      method: "POST",
      headers: authHeaders,
      body: form,
    });
    setMessage(response.ok ? "Avatar uploaded" : "Could not upload avatar");
    if (response.ok) {
      setAvatarFile(null);
      await loadProfile();
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch(`${apiBase}/users/me/change-password`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    if (!response.ok) {
      setMessage("Could not change password");
      return;
    }
    setCurrentPassword("");
    setNewPassword("");
    setMessage("Password changed. Sign in again with the new password.");
    await logout();
  }

  async function createApiKey(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch(`${apiBase}/api-keys`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ name: apiKeyName }),
    });
    if (!response.ok) {
      setMessage("Could not create API key");
      return;
    }
    const body = (await response.json()) as { key: string };
    setNewApiKey(body.key);
    setApiKeyName("");
    setMessage("API key created. Copy it now; it will not be shown again.");
    await loadApiKeys();
  }

  async function revokeApiKey(id: string) {
    const response = await apiFetch(`${apiBase}/api-keys/${id}`, {
      method: "DELETE",
      headers: authHeaders,
    });
    setMessage(response.ok ? "API key revoked" : "Could not revoke API key");
    if (response.ok) await loadApiKeys();
  }

  async function createOrganization(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch(`${apiBase}/organizations`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ name: organizationName }),
    });
    if (!response.ok) {
      setMessage("Could not create organization");
      return;
    }
    setOrganizationName("");
    setMessage("Organization created");
    await loadOrganizations();
  }

  async function loadLinks(dimension = breakdownDimension) {
    if (!organizationId) {
      setMessage("Enter an organization ID");
      return;
    }
    const params = new URLSearchParams({
      limit: "100",
      descending: "true",
    });
    if (search.trim()) {
      params.set("search", search.trim());
    }
    if (showArchived) {
      params.set("archived", "true");
    }
    const response = await apiFetch(`${apiBase}/urls/organizations/${organizationId}?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      setMessage("Could not load links");
      return;
    }
    setLinks(await response.json());
    setSelectedLinks([]);
    const analyticsResponse = await apiFetch(
      `${apiBase}/analytics/organizations/${organizationId}/overview?days=30`,
      { headers: authHeaders },
    );
    if (analyticsResponse.ok) {
      setOverview((await analyticsResponse.json()) as Overview);
    }
    const [seriesResponse, breakdownResponse] = await Promise.all([
      apiFetch(`${apiBase}/analytics/organizations/${organizationId}/timeseries?days=30&granularity=daily`, { headers: authHeaders }),
      apiFetch(`${apiBase}/analytics/organizations/${organizationId}/breakdown?days=30&dimension=${dimension}`, { headers: authHeaders }),
    ]);
    if (seriesResponse.ok) setTimeSeries((await seriesResponse.json()) as AnalyticsRow[]);
    if (breakdownResponse.ok) setBreakdown((await breakdownResponse.json()) as AnalyticsRow[]);
  }

  async function createLink(event: FormEvent) {
    event.preventDefault();
    if (!organizationId) {
      setMessage("Select an organization first");
      return;
    }
    const payload = {
      organization_id: organizationId,
      original_url: target,
      title: linkTitle || undefined,
      custom_alias: linkAlias || undefined,
      expires_at: linkExpiresAt ? new Date(linkExpiresAt).toISOString() : undefined,
      password: linkPassword || undefined,
      click_limit: linkClickLimit ? Number(linkClickLimit) : undefined,
      one_time: linkOneTime,
      is_private: linkPrivate,
    };
    const response = await apiFetch(`${apiBase}/urls`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      setMessage("Could not create link");
      return;
    }

    setTarget("");
    setLinkTitle("");
    setLinkAlias("");
    setLinkExpiresAt("");
    setLinkPassword("");
    setLinkClickLimit("");
    setLinkOneTime(false);
    setLinkPrivate(false);
    setMessage("Link created");
    await loadLinks();
  }

  async function editLink(link: LinkItem) {
      const title = window.prompt("Link title", link.title ?? "");
      if (title === null || !organizationId) return;
      const originalUrl = window.prompt("Destination URL", link.original_url);
      if (originalUrl === null) return;
      const response = await apiFetch(
        `${apiBase}/urls/${link.id}?organization_id=${organizationId}`,
        {
          method: "PATCH",
          headers: { ...authHeaders, "Content-Type": "application/json" },
          body: JSON.stringify({ title, original_url: originalUrl }),
        },
      );
      setMessage(response.ok ? "Link updated" : "Could not update link");
      if (response.ok) await loadLinks();
    }

  async function downloadQr(link: LinkItem) {
      const response = await apiFetch(
        `${apiBase}/urls/${link.id}/qr?organization_id=${organizationId}`,
      );
      if (!response.ok) {
        setMessage("Could not download QR code");
        return;
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${link.short_code}.png`;
      anchor.click();
      URL.revokeObjectURL(url);
  }

  async function importLinks(event: FormEvent) {
    event.preventDefault();
    if (!organizationId) return;
    const rows = bulkCsv.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const urls = rows[0]?.toLowerCase() === "original_url" ? rows.slice(1) : rows;
    const response = await apiFetch(`${apiBase}/urls/bulk/create`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: organizationId, rows: urls.map((original_url) => ({ original_url })) }),
    });
    if (!response.ok) {
      setMessage("Bulk import failed");
      return;
    }

    const body = await response.json() as { created: LinkItem[]; failed: { index: number; reason: string }[] };
    setBulkCsv("");
    setMessage(`Imported ${body.created.length} links${body.failed.length ? `; ${body.failed.length} failed` : ""}`);
    await loadLinks();
  }

  async function uploadLinksFile(event: FormEvent) {
    event.preventDefault();
    if (!organizationId || !bulkFile) return;
    const form = new FormData();
    form.append("file", bulkFile);
    const response = await apiFetch(
      `${apiBase}/urls/bulk/upload?organization_id=${organizationId}`,
      { method: "POST", headers: authHeaders, body: form },
    );
    if (!response.ok) {
      setMessage("CSV upload failed");
      return;
    }
    const body = await response.json() as { created: LinkItem[]; failed: { index: number; reason: string }[] };
    setBulkFile(null);
    setMessage(`Uploaded ${body.created.length} links${body.failed.length ? `; ${body.failed.length} failed` : ""}`);
    await loadLinks();
  }

  async function bulkDelete() {
    if (!organizationId || selectedLinks.length === 0) return;
    const response = await apiFetch(`${apiBase}/urls/bulk/delete`, {
      method: "DELETE",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: organizationId, ids: selectedLinks }),
    });
    setMessage(response.ok ? "Selected links deleted" : "Bulk delete failed");
    if (response.ok) await loadLinks();
  }

  async function toggleArchive(link: LinkItem) {
    if (!organizationId) return;
    const response = await apiFetch(
      `${apiBase}/urls/${link.id}/${link.is_archived ? "restore" : "archive"}?organization_id=${organizationId}`,
      { method: "POST", headers: authHeaders },
    );
    if (!response.ok) {
      setMessage("Could not update link status");
      return;
    }
    setMessage(link.is_archived ? "Link restored" : "Link archived");
    await loadLinks();
  }

  async function deleteLink(link: LinkItem) {
    if (!organizationId || !window.confirm(`Delete ${link.short_code}?`)) return;
    const response = await apiFetch(
      `${apiBase}/urls/${link.id}?organization_id=${organizationId}`,
      { method: "DELETE", headers: authHeaders },
    );
    setMessage(response.ok ? "Link deleted" : "Could not delete link");
    if (response.ok) await loadLinks();
  }

  async function duplicateLink(link: LinkItem) {
    if (!organizationId) return;
    const response = await apiFetch(
      `${apiBase}/urls/${link.id}/duplicate?organization_id=${organizationId}`,
      { method: "POST", headers: authHeaders },
    );
    setMessage(response.ok ? "Link duplicated" : "Could not duplicate link");
    if (response.ok) await loadLinks();
  }

  async function inviteMember(event: FormEvent) {
    event.preventDefault();
    if (!organizationId) return;
    const response = await apiFetch(`${apiBase}/organizations/${organizationId}/invites`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ email: inviteEmail, role: "member" }),
    });
    if (!response.ok) {
      setMessage("Could not create invitation");
      return;
    }
    const body = (await response.json()) as { invite_token: string };
    setInviteToken(body.invite_token);
    setInviteEmail("");
    setMessage("Invitation created. Send the token to the invitee.");
  }

  async function acceptInvite(event: FormEvent) {
    event.preventDefault();
    const response = await apiFetch(`${apiBase}/organizations/invites/accept`, {
      method: "POST",
      headers: { ...authHeaders, "Content-Type": "application/json" },
      body: JSON.stringify({ invite_token: acceptInviteToken }),
    });
    if (!response.ok) {
      setMessage("Could not accept invitation");
      return;
    }
    setAcceptInviteToken("");
    setMessage("Invitation accepted");
    await loadOrganizations();
  }

  if (!token) {
    return (
      <main className="centered">
        <section className="card auth-card">
          <p className="eyebrow">LINKHUB</p>
          <h1>{isVerifying ? "Verify your email" : isResetting ? "Choose a new password" : isRecovering ? "Reset your password" : isRegistering ? "Create your account" : "Smart links for teams"}</h1>
          <p className="muted">{isVerifying ? "Paste the verification token from your email." : isResetting ? "Paste the reset token and choose a new password." : isRecovering ? "Enter your email and we will send reset instructions." : isRegistering ? "Start managing links with your team." : "Sign in to manage links, analytics, and organizations."}</p>
          <form onSubmit={login}>
          {(isVerifying || isResetting) && <input placeholder="Token" value={recoveryToken} onChange={(event) => setRecoveryToken(event.target.value)} required />}
          {isRegistering && !isRecovering && <input placeholder="Full name" value={fullName} onChange={(event) => setFullName(event.target.value)} required />}
          {(!isRecovering || isVerifying) && !isResetting && <input type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />}
          {!isRecovering && !isVerifying && <input type="password" placeholder={isResetting ? "New password" : "Password"} value={password} onChange={(event) => setPassword(event.target.value)} required />}
          <button type="submit">{isVerifying ? "Verify email" : isResetting ? "Reset password" : isRecovering ? "Send reset email" : isRegistering ? "Create account" : "Sign in"}</button>
          </form>
          {!isRecovering && !isRegistering && !isVerifying && !isResetting && <button className="text-button" onClick={() => setIsRecovering(true)}>Forgot password?</button>}
          {!isRecovering && !isRegistering && !isVerifying && !isResetting && <button className="text-button" onClick={() => setIsVerifying(true)}>Verify email</button>}
          {isVerifying && <button type="button" className="text-button" onClick={() => void resendVerification()}>Resend verification email</button>}
          {isRecovering && !isResetting && <button className="text-button" onClick={() => setIsResetting(true)}>I have a reset token</button>}
          <button className="secondary auth-switch" onClick={() => { setIsRecovering(false); setIsResetting(false); setIsVerifying(false); setIsRegistering((value) => !value); }}>
          {isRecovering || isVerifying || isResetting ? "Back to sign in" : isRegistering ? "Already have an account? Sign in" : "Need an account? Register"}
          </button>
          {message && <p className="notice">{message}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">LINKHUB</p>
          <h1>Link workspace</h1>
        </div>
        <button className="secondary" onClick={logout}>Sign out</button>
      </header>
      {adminMetrics && <section className="stats-grid">
        {Object.entries(adminMetrics).map(([name, value]) => <article className="card stat" key={name}><span className="muted">Platform {name}</span><strong>{value}</strong></article>)}
      </section>}
      {adminMetrics && <section className="admin-grid">
        <article className="card">
          <h2>Recent users</h2>
          <div className="admin-list">{adminUsers.map((user) => <div className="admin-row" key={user.email}><span>{user.full_name || user.email}</span><span className="muted">{user.is_active ? "Active" : "Inactive"}</span></div>)}</div>
        </article>
        <article className="card">
          <h2>Recent audit activity</h2>
          <div className="admin-list">{adminLogs.map((log, index) => <div className="admin-row" key={`${log.created_at}-${index}`}><span>{log.action} ({log.resource_type})</span><span className="muted">{new Date(log.created_at).toLocaleDateString()}</span></div>)}</div>
        </article>
        <article className="card">
          <h2>Organizations</h2>
          <div className="admin-list">{adminOrganizations.map((organization) => (
            <div className="admin-row" key={organization.id}>
              <span>{organization.name}</span>
              <span className="muted">{organization.slug}</span>
            </div>
          ))}</div>
        </article>
        <article className="card">
          <h2>Links</h2>
          <div className="admin-list">{adminLinks.map((link) => (
            <div className="admin-row" key={link.id}>
              <span>{link.short_code}</span>
              <span className="muted">{link.is_deleted ? "Deleted" : link.is_archived ? "Archived" : "Active"}</span>
            </div>
          ))}</div>
        </article>
      </section>}
      <section className="toolbar card">
        <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
          <option value="">Select an organization</option>
          {organizations.map((organization) => (
            <option value={organization.id} key={organization.id}>{organization.name}</option>
          ))}
        </select>
        <button className="secondary" onClick={() => void loadLinks()}>Load links</button>
        <input placeholder="Search links" value={search} onChange={(event) => setSearch(event.target.value)} />
        <label className="checkbox"><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /> Show archived</label>
        <form className="create-form" onSubmit={createOrganization}>
          <input placeholder="New organization name" value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required />
          <button type="submit">Create organization</button>
        </form>
        <form className="create-form" onSubmit={createLink}>
          <input type="url" placeholder="https://example.com" value={target} onChange={(event) => setTarget(event.target.value)} required />
          <input placeholder="Title (optional)" value={linkTitle} onChange={(event) => setLinkTitle(event.target.value)} />
          <input placeholder="Custom alias (optional)" value={linkAlias} onChange={(event) => setLinkAlias(event.target.value)} />
          <input type="datetime-local" value={linkExpiresAt} onChange={(event) => setLinkExpiresAt(event.target.value)} />
          <input type="password" minLength={8} placeholder="Password (optional)" value={linkPassword} onChange={(event) => setLinkPassword(event.target.value)} />
          <input type="number" min={1} placeholder="Click limit (optional)" value={linkClickLimit} onChange={(event) => setLinkClickLimit(event.target.value)} />
          <label className="checkbox"><input type="checkbox" checked={linkOneTime} onChange={(event) => setLinkOneTime(event.target.checked)} /> One-time</label>
          <label className="checkbox"><input type="checkbox" checked={linkPrivate} onChange={(event) => setLinkPrivate(event.target.checked)} /> Private</label>
          <button type="submit">Create link</button>
        </form>
        <form className="create-form" onSubmit={importLinks}>
          <textarea placeholder="Paste one URL per line, or CSV with an original_url header" value={bulkCsv} onChange={(event) => setBulkCsv(event.target.value)} required />
          <button type="submit">Bulk import</button>
        </form>
        <form className="create-form" onSubmit={uploadLinksFile}>
          <input type="file" accept=".csv,text/csv" onChange={(event) => setBulkFile(event.target.files?.[0] ?? null)} required />
          <button type="submit">Upload CSV</button>
        </form>
        {selectedLinks.length > 0 && <button className="danger" onClick={bulkDelete}>Delete selected ({selectedLinks.length})</button>}
      </section>
      {message && <p className="notice">{message}</p>}
      {overview && (
        <section className="stats-grid">
          <article className="card stat"><span className="muted">Clicks (30 days)</span><strong>{overview.total_clicks}</strong></article>
          <article className="card stat"><span className="muted">Unique visitors</span><strong>{overview.unique_clicks}</strong></article>
        </section>
      )}
      {(timeSeries.length > 0 || breakdown.length > 0) && <section className="analytics-grid">
        <article className="card">
          <div className="section-heading"><h2>Daily clicks</h2><span>Last 30 days</span></div>
          <div className="bar-list">{timeSeries.map((row) => <div className="bar-row" key={row.bucket}><span>{row.bucket}</span><div className="bar-track"><div className="bar-fill" style={{ width: `${Math.min(100, (row.count / Math.max(...timeSeries.map((item) => item.count), 1)) * 100)}%` }} /></div><strong>{row.count}</strong></div>)}</div>
        </article>
        <article className="card">
          <div className="section-heading"><h2>Traffic breakdown</h2><select value={breakdownDimension} onChange={(event) => { setBreakdownDimension(event.target.value); void loadLinks(event.target.value); }}><option value="browser">Browser</option><option value="device">Device</option><option value="country">Country</option><option value="city">City</option><option value="referrer">Referrer</option><option value="os">OS</option></select></div>
          <div className="bar-list">{breakdown.map((row) => <div className="bar-row" key={row.value}><span>{row.value}</span><strong>{row.count}</strong></div>)}</div>
        </article>
      </section>}
      <section className="card">
        <div className="section-heading"><h2>Links</h2><span>{links.length} shown</span></div>
        {links.length === 0 ? <p className="muted">Load an organization to see its links.</p> : (
          <div className="link-list">
            {links.map((link) => (
              <article className="link-row" key={link.id}>
                <div className="link-summary"><input type="checkbox" checked={selectedLinks.includes(link.id)} onChange={(event) => setSelectedLinks((current) => event.target.checked ? [...current, link.id] : current.filter((id) => id !== link.id))} /><div><strong>{link.title || link.short_code}</strong><p>{link.original_url}</p></div></div>
                <div className="link-actions">
                  <a href={`${apiBase}/urls/r/${link.short_code}`} target="_blank" rel="noreferrer">Open</a>
                  <button className="secondary" onClick={() => void editLink(link)}>Edit</button>
                  <button className="secondary" onClick={() => void downloadQr(link)}>QR</button>
                  <button className="secondary" onClick={() => duplicateLink(link)}>Duplicate</button>
                  <button className="secondary" onClick={() => toggleArchive(link)}>{link.is_archived ? "Restore" : "Archive"}</button>
                  <button className="danger" onClick={() => deleteLink(link)}>Delete</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="card team-card">
        <div className="section-heading"><h2>Invite a teammate</h2><span>Organization access</span></div>
        <form className="create-form" onSubmit={inviteMember}>
          <input type="email" placeholder="teammate@example.com" value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} required />
          <button type="submit">Create invite</button>
        </form>
        {inviteToken && <p className="api-key-output">Invite token: {inviteToken}</p>}
        <form className="create-form" onSubmit={acceptInvite}>
          <input placeholder="Paste an invitation token" value={acceptInviteToken} onChange={(event) => setAcceptInviteToken(event.target.value)} required />
          <button className="secondary" type="submit">Accept invite</button>
        </form>
        <div className="admin-list">
          {members.map((member) => (
            <div className="admin-row" key={member.user_id}>
              <span>{member.full_name || member.email}</span>
              <select value={member.role} disabled={member.role === "owner"} onChange={(event) => void updateMemberRole(member, event.target.value)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
                <option value="owner">Owner</option>
              </select>
              {member.role !== "owner" && <button className="secondary" onClick={() => void transferOwnership(member)}>Transfer ownership</button>}
            </div>
          ))}
        </div>
      </section>
      <section className="settings-grid">
        <article className="card">
          <div className="section-heading"><h2>Profile</h2><span>{profile?.email}</span></div>
          {profile?.avatar_url && <img className="avatar-preview" src={`${publicBase}${profile.avatar_url}`} alt="Profile avatar" />}
          <form className="settings-form" onSubmit={updateProfile}>
            <input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Full name" />
            <button type="submit">Save profile</button>
          </form>
          <form className="settings-form" onSubmit={uploadAvatar}>
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setAvatarFile(event.target.files?.[0] ?? null)} />
            <button type="submit">Upload avatar</button>
          </form>
          <p className="muted">{profile?.is_email_verified ? "Email verified" : "Email verification pending"}</p>
        </article>
        <article className="card">
          <h2>Change password</h2>
          <form className="settings-form" onSubmit={changePassword}>
            <input type="password" minLength={8} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} placeholder="Current password" required />
            <input type="password" minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="New password" required />
            <button type="submit">Change password</button>
          </form>
        </article>
        <article className="card">
          <div className="section-heading"><h2>API keys</h2><span>{apiKeys.length} active/issued</span></div>
          <form className="settings-form" onSubmit={createApiKey}>
            <input value={apiKeyName} onChange={(event) => setApiKeyName(event.target.value)} placeholder="Key name" required />
            <button type="submit">Generate key</button>
          </form>
          {newApiKey && <p className="api-key-output">{newApiKey}</p>}
          <div className="key-list">
            {apiKeys.map((key) => (
              <div className="key-row" key={key.id}>
                <span>{key.name} ({key.key_prefix}...) · {key.usage_count} uses</span>
                {key.is_active && <button className="secondary" onClick={() => revokeApiKey(key.id)}>Revoke</button>}
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
