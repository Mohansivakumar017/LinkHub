import { FormEvent, useEffect, useState } from "react";

type LinkItem = {
  id: string;
  short_code: string;
  original_url: string;
  title?: string | null;
  custom_alias?: string | null;
  is_private: boolean;
  password_protected: boolean;
  is_archived: boolean;
};

type Organization = {
  id: string;
  name: string;
  slug: string;
  owner_user_id: string;
};

type Overview = {
  total_clicks: number;
  unique_clicks: number;
  range_days: number;
};

type Profile = {
  id: string;
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
type LinkAccessRequest = {
  link: LinkItem;
  password: string;
  error: string;
  targetWindow: Window | null;
  sameTab: boolean;
  submitting: boolean;
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
  const [linkAccess, setLinkAccess] = useState<LinkAccessRequest | null>(null);
  const [sharedLinkCode] = useState(
    () => new URLSearchParams(window.location.search).get("link") ?? "",
  );
  const [sharedLinkPassword, setSharedLinkPassword] = useState("");
  const [sharedLinkError, setSharedLinkError] = useState("");
  const [sharedLinkLoading, setSharedLinkLoading] = useState(false);
  const [sharedLinkRequiresPassword, setSharedLinkRequiresPassword] = useState(false);

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
    setEmail("");
    setPassword("");
    setFullName("");
    setProfileName("");
    setRecoveryToken("");
    setOrganizationId("");
    setOrganizations([]);
    setLinks([]);
    setMembers([]);
    setProfile(null);
    setApiKeys([]);
    setNewApiKey("");
    setInviteToken("");
    setAcceptInviteToken("");
    setTarget("");
    setLinkTitle("");
    setLinkAlias("");
    setLinkExpiresAt("");
    setLinkPassword("");
    setLinkClickLimit("");
    setLinkOneTime(false);
    setLinkPrivate(false);
    setSearch("");
    setSelectedLinks([]);
    setOverview(null);
    setTimeSeries([]);
    setBreakdown([]);
    setMessage("");
    setIsRegistering(false);
    setIsRecovering(false);
    setIsResetting(false);
    setIsVerifying(false);
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
    const currentMember = members.find((item) => item.user_id === profile?.id);
    if (currentMember?.role !== "owner") {
      setMessage("Only the organization owner can transfer ownership");
      return;
    }
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

  async function removeMember(member: OrganizationMember) {
    const currentMember = members.find((item) => item.user_id === profile?.id);
    const canRemove = currentMember?.role === "owner"
      || (currentMember?.role === "admin" && member.role === "member");
    if (!canRemove) {
      setMessage("You do not have permission to remove this member");
      return;
    }
    if (!window.confirm(`Remove ${member.email} from this organization? They will lose access to private links.`)) return;
    const response = await apiFetch(
      `${apiBase}/organizations/${organizationId}/members/${member.user_id}`,
      { method: "DELETE", headers: authHeaders },
    );
    setMessage(response.ok ? "Member removed" : "Could not remove member");
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

  async function copyText(value: string) {
    await navigator.clipboard.writeText(value);
    setMessage("Copied to clipboard");
  }

  async function copyLinkUrl(link: LinkItem) {
    const publicLinkUrl = new URL(
      `/?link=${encodeURIComponent(link.short_code)}`,
      window.location.origin,
    ).toString();
    await copyText(publicLinkUrl);
  }

  async function revokeApiKey(id: string) {
    const response = await apiFetch(`${apiBase}/api-keys/${id}`, {
      method: "DELETE",
      headers: authHeaders,
    });
    setMessage(response.ok ? "API key revoked" : "Could not revoke API key");
    if (response.ok) await loadApiKeys();
  }

  async function rotateApiKey(id: string) {
    const response = await apiFetch(`${apiBase}/api-keys/${id}/rotate`, {
      method: "POST",
      headers: authHeaders,
    });
    if (!response.ok) {
      setMessage("Could not rotate API key");
      return;
    }
    const body = await response.json() as { key: string };
    setNewApiKey(body.key);
    setMessage("API key rotated. Update your integration and copy the new key now.");
    await loadApiKeys();
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
      let detail = "Could not create link";
      try {
        const body = await response.json() as { detail?: string; error?: { message?: string } };
        detail = body.detail ?? body.error?.message ?? detail;
      } catch {
        // Some proxies return an empty/non-JSON error response.
      }
      setMessage(detail);
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

  async function openSharedLink(password?: string) {
    if (!sharedLinkCode) return;
    setSharedLinkLoading(true);
    setSharedLinkError("");
    const query = password
      ? `?password=${encodeURIComponent(password)}`
      : "";
    const response = await apiFetch(`${apiBase}/urls/resolve/${sharedLinkCode}${query}`, {
      headers: authHeaders,
    });
    if (!response.ok) {
      let detail = "Could not open link";
      try {
        const body = await response.json() as { detail?: string; error?: { message?: string } };
        detail = body.detail ?? body.error?.message ?? detail;
      } catch {
        // Keep the generic message when the response is not JSON.
      }
      if (response.status === 401 && detail === "link password required" && !password) {
        setSharedLinkRequiresPassword(true);
        setSharedLinkError("This link is password protected. Enter the password to continue.");
      } else if (response.status === 401 && detail === "private link requires authentication") {
        setSharedLinkError("Sign in to continue. This link is restricted to organization members.");
      } else {
        setSharedLinkError(detail);
      }
      setSharedLinkLoading(false);
      return;
    }
    const body = await response.json() as { original_url: string };
    window.location.assign(body.original_url);
    setSharedLinkLoading(false);
  }

  function openLink(link: LinkItem) {
    if (link.password_protected) {
      setLinkAccess({ link, password: "", error: "", targetWindow: null, sameTab: false, submitting: false });
      return;
    }
    const targetWindow = window.open("", "_blank");
    if (!targetWindow) {
      setMessage("Your browser blocked the new tab. Allow pop-ups for LinkHub and try again.");
      return;
    }
    targetWindow.opener = null;
    targetWindow.document.title = "Opening LinkHub link";
    targetWindow.document.body.textContent = "Checking link access...";
    void resolveAndNavigate(link, targetWindow);
  }

  async function resolveAndNavigate(link: LinkItem, targetWindow: Window, password?: string) {
    const query = password ? `?password=${encodeURIComponent(password)}` : "";
    const response = await apiFetch(`${apiBase}/urls/resolve/${link.short_code}${query}`, {
      headers: authHeaders,
    });
    if (!response.ok) {
      let detail = "Could not open link";
      try {
        const body = await response.json() as { detail?: string; error?: { message?: string } };
        detail = body.detail ?? body.error?.message ?? detail;
      } catch {
        // Some proxies return an empty/non-JSON error response.
      }
      targetWindow.document.title = "LinkHub access";
      targetWindow.document.body.textContent = detail;
      return;
    }
    const body = await response.json() as { original_url: string };
    targetWindow.location.assign(body.original_url);
  }

  async function submitLinkAccess(event: FormEvent) {
    event.preventDefault();
    if (!linkAccess) return;
    setLinkAccess((current) => current ? { ...current, submitting: true, error: "" } : current);
    const resolveLink = (password?: string) => {
      const query = password ? `?password=${encodeURIComponent(password)}` : "";
      return apiFetch(`${apiBase}/urls/resolve/${linkAccess.link.short_code}${query}`, {
        headers: authHeaders,
      });
    };
    const targetWindow = linkAccess.sameTab
      ? null
      : linkAccess.targetWindow ?? window.open("", "_blank");
    if (!linkAccess.sameTab && !targetWindow) {
      setLinkAccess((current) => current ? {
        ...current,
        error: "Your browser blocked the new tab. Allow pop-ups for LinkHub and try again.",
        submitting: false,
      } : current);
      return;
    }
    if (targetWindow) targetWindow.opener = null;
    const response = await resolveLink(linkAccess.password || undefined);
    if (!response.ok) {
      let detail = "Could not open link";
      try {
        const body = await response.json() as { detail?: string; error?: { message?: string } };
        detail = body.detail ?? body.error?.message ?? detail;
      } catch {
        // Some proxies return an empty/non-JSON error response.
      }
      if (response.status === 401 && detail === "link password required") {
        targetWindow?.close();
        setLinkAccess((current) => current ? {
          ...current,
          error: "Enter the password for this link.",
          submitting: false,
        } : current);
        return;
      }
      setLinkAccess((current) => current ? {
        ...current,
        error: detail,
        submitting: false,
      } : current);
      return;
    }
    const body = await response.json() as { original_url: string };
    if (linkAccess.sameTab) {
      window.location.assign(body.original_url);
    } else {
      targetWindow?.location.assign(body.original_url);
    }
    setLinkAccess(null);
  }

  if (!token && !sharedLinkCode) {
    return (
      <main className="centered">
        <section className="card auth-card">
          <p className="eyebrow">LINKHUB</p>
          <h1>{isVerifying ? "Verify your email" : isResetting ? "Choose a new password" : isRecovering ? "Reset your password" : isRegistering ? "Create your account" : "Smart links for teams"}</h1>
          <p className="muted">{isVerifying ? "Paste the verification token from your email." : isResetting ? "Paste the reset token and choose a new password." : isRecovering ? "Enter your email and we will send reset instructions." : isRegistering ? "Start managing links with your team." : "Sign in to manage links, analytics, and organizations."}</p>
          <form onSubmit={login} autoComplete="off">
          {(isVerifying || isResetting) && <input autoComplete="off" placeholder="Token" value={recoveryToken} onChange={(event) => setRecoveryToken(event.target.value)} required />}
          {isRegistering && !isRecovering && <input autoComplete="name" placeholder="Full name" value={fullName} onChange={(event) => setFullName(event.target.value)} required />}
          {(!isRecovering || isVerifying) && !isResetting && <input autoComplete="email" type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />}
          {(isResetting || (!isRecovering && !isVerifying)) && <input autoComplete={isResetting ? "new-password" : "current-password"} type="password" placeholder={isResetting ? "New password" : "Password"} value={password} onChange={(event) => setPassword(event.target.value)} required />}
          <button type="submit">{isVerifying ? "Verify email" : isResetting ? "Reset password" : isRecovering ? "Send reset email" : isRegistering ? "Create account" : "Sign in"}</button>
          </form>
          {!isRecovering && !isRegistering && !isVerifying && !isResetting && <button type="button" className="text-button" onClick={() => setIsRecovering(true)}>Forgot password?</button>}
          {!isRecovering && !isRegistering && !isVerifying && !isResetting && <button type="button" className="text-button" onClick={() => setIsVerifying(true)}>Verify email</button>}
          {isVerifying && <button type="button" className="text-button" onClick={() => void resendVerification()}>Resend verification email</button>}
          {isRecovering && !isResetting && <button type="button" className="text-button" onClick={() => { setIsRecovering(false); setIsResetting(true); setPassword(""); }}>I have a reset token</button>}
          <button type="button" className="secondary auth-switch" onClick={() => { setIsRecovering(false); setIsResetting(false); setIsVerifying(false); setRecoveryToken(""); setPassword(""); setIsRegistering((value) => !value); }}>
          {isRecovering || isVerifying || isResetting ? "Back to sign in" : isRegistering ? "Already have an account? Sign in" : "Need an account? Register"}
          </button>
          {message && <p className="notice">{message}</p>}
        </section>
      </main>
    );
  }

  if (sharedLinkCode) {
    return (
      <main className="centered">
        <section className="card auth-card shared-link-page">
          <p className="eyebrow">LINKHUB SHARED LINK</p>
          <h1>Open shared link</h1>
          <p className="muted">
            Link code: <strong>{sharedLinkCode}</strong>
          </p>
          {!token ? (
            <>
              <p className="muted">
                Public links can open without signing in. Organization-only links require
                an account that belongs to the organization.
              </p>
              <button
                type="button"
                onClick={() => void openSharedLink()}
                disabled={sharedLinkLoading}
              >
                {sharedLinkLoading ? "Checking link..." : "Open link"}
              </button>
              {sharedLinkRequiresPassword && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void openSharedLink(sharedLinkPassword);
                  }}
                >
                  <label>
                    Link password
                    <input
                      autoFocus
                      type="password"
                      autoComplete="off"
                      placeholder="Enter link password"
                      value={sharedLinkPassword}
                      onChange={(event) => setSharedLinkPassword(event.target.value)}
                      required
                    />
                  </label>
                  <button type="submit" disabled={sharedLinkLoading}>
                    {sharedLinkLoading ? "Checking access..." : "Open with password"}
                  </button>
                </form>
              )}
              <p className="muted share-login-hint">
                Need access to a private link? Sign in below, then this link will be
                checked again automatically.
              </p>
              <form onSubmit={login} autoComplete="off">
                <input
                  autoComplete="email"
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
                <input
                  autoComplete="current-password"
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <button type="submit">Sign in</button>
              </form>
            </>
          ) : (
            <>
              <p className="muted">
                You are signed in as {profile?.email ?? email}. Verify access before
                leaving LinkHub.
              </p>
              {sharedLinkRequiresPassword ? (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void openSharedLink(sharedLinkPassword);
                  }}
                >
                  <label>
                    Link password
                    <input
                      autoFocus
                      type="password"
                      autoComplete="off"
                      placeholder="Enter link password"
                      value={sharedLinkPassword}
                      onChange={(event) => setSharedLinkPassword(event.target.value)}
                      required
                    />
                  </label>
                  <button type="submit" disabled={sharedLinkLoading}>
                    {sharedLinkLoading ? "Checking access..." : "Open link"}
                  </button>
                </form>
              ) : (
                <button
                  type="button"
                  onClick={() => void openSharedLink()}
                  disabled={sharedLinkLoading}
                >
                  {sharedLinkLoading ? "Checking access..." : "Open link"}
                </button>
              )}
              <button type="button" className="secondary" onClick={logout}>
                Sign out
              </button>
            </>
          )}
          {sharedLinkError && <p className="notice">{sharedLinkError}</p>}
          {message && <p className="notice">{message}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      {linkAccess && (
        <div className="modal-backdrop" role="presentation">
          <section className="card access-dialog" role="dialog" aria-modal="true" aria-labelledby="link-access-title">
            <h2 id="link-access-title">Open link</h2>
            <p className="muted">This link requires access before it can be opened.</p>
            <form onSubmit={submitLinkAccess}>
              <label>Password (if required)
                <input
                  autoFocus
                  type="password"
                  autoComplete="current-password"
                  placeholder="Enter link password"
                  value={linkAccess.password}
                  onChange={(event) => setLinkAccess((current) => current ? { ...current, password: event.target.value } : current)}
                />
              </label>
              {linkAccess.error && <p className="notice">{linkAccess.error}</p>}
              <div className="dialog-actions">
                <button type="submit" disabled={linkAccess.submitting}>
                  {linkAccess.submitting ? "Checking..." : "Open in new tab"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    linkAccess.targetWindow?.close();
                    setLinkAccess(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
      {sharedLinkCode && (
        <section className="card shared-link-card">
          <h2>Shared Link</h2>
          <p className="muted">Link code: {sharedLinkCode}</p>
          <button type="button" onClick={() => void openSharedLink()}>Open shared link</button>
        </section>
      )}
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
        <select value={organizationId} onChange={(event) => {
          setOrganizationId(event.target.value);
          setLinks([]);
          setMembers([]);
          setOverview(null);
          setTimeSeries([]);
          setBreakdown([]);
        }}>
          <option value="">Select an organization</option>
          {organizations.map((organization) => (
            <option value={organization.id} key={organization.id}>{organization.name}</option>
          ))}
        </select>
        {organizationId && (
          <div className="selected-organization">
            <strong>{organizations.find((organization) => organization.id === organizationId)?.name}</strong>
            <span className="muted">Organization ID: {organizationId}</span>
            <button type="button" className="secondary" onClick={() => void copyText(organizationId)}>Copy ID</button>
          </div>
        )}
        <button className="secondary" onClick={() => void loadLinks()}>Load links</button>
        <input placeholder="Search links" value={search} onChange={(event) => setSearch(event.target.value)} />
        <label className="checkbox"><input type="checkbox" checked={showArchived} onChange={(event) => setShowArchived(event.target.checked)} /> Show archived</label>
        <form className="create-form" onSubmit={createOrganization}>
          <input placeholder="New organization name" value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} required />
          <button type="submit">Create organization</button>
        </form>
        <form className="create-form" onSubmit={createLink}>
          <div className="form-heading">
            <div>
              <h2>Create a link</h2>
              <p className="muted">Turn a long URL into a trackable, shareable link.</p>
            </div>
          </div>
          <label>Destination URL
            <input type="url" placeholder="https://example.com" value={target} onChange={(event) => setTarget(event.target.value)} required />
          </label>
          <label>Title
            <input placeholder="Optional name for this link" value={linkTitle} onChange={(event) => setLinkTitle(event.target.value)} />
          </label>
          <label>Custom alias
            <input placeholder="Optional alias, for example summer-sale" value={linkAlias} onChange={(event) => setLinkAlias(event.target.value)} />
          </label>
          <label>Expiration
            <input type="datetime-local" aria-label="Expiration date and time (optional)" value={linkExpiresAt} onChange={(event) => setLinkExpiresAt(event.target.value)} />
            <small className="field-help">Optional date and time when the link stops working.</small>
          </label>
          <label>Password protection
            <input type="password" minLength={8} placeholder="Optional password (8+ characters)" value={linkPassword} onChange={(event) => setLinkPassword(event.target.value)} />
          </label>
          <label>Click limit
            <input type="number" min={1} placeholder="Optional maximum clicks" value={linkClickLimit} onChange={(event) => setLinkClickLimit(event.target.value)} />
          </label>
          <label className="checkbox"><input type="checkbox" checked={linkOneTime} onChange={(event) => setLinkOneTime(event.target.checked)} /> Open only once</label>
          <label className="checkbox"><input type="checkbox" checked={linkPrivate} onChange={(event) => setLinkPrivate(event.target.checked)} /> Organization members only</label>
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
      {organizationId && overview && (
        <section className="stats-grid">
          <article className="card stat"><span className="muted">Clicks (30 days)</span><strong>{overview.total_clicks}</strong></article>
          <article className="card stat"><span className="muted">Unique visitors</span><strong>{overview.unique_clicks}</strong></article>
        </section>
      )}
      {organizationId && (timeSeries.length > 0 || breakdown.length > 0) && <section className="analytics-grid">
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
                  <button className="text-link" onClick={() => void openLink(link)}>Open</button>
                  <button className="secondary" onClick={() => void copyLinkUrl(link)}>Copy link</button>
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
        {inviteToken && (
          <div className="secret-output">
            <p className="api-key-output">Invite token: {inviteToken}</p>
            <button type="button" className="secondary" onClick={() => setInviteToken("")}>Hide token</button>
          </div>
        )}
        <form className="create-form" onSubmit={acceptInvite}>
          <input placeholder="Paste an invitation token" value={acceptInviteToken} onChange={(event) => setAcceptInviteToken(event.target.value)} required />
          <button className="secondary" type="submit">Accept invite</button>
        </form>
        <div className="admin-list">
          {members.map((member) => {
            const currentMember = members.find((item) => item.user_id === profile?.id);
            const canManageRoles = currentMember?.role === "owner";
            const canRemove = currentMember?.role === "owner"
              || (currentMember?.role === "admin" && member.role === "member");
            return (
            <div className="admin-row" key={member.user_id}>
              <span>{member.full_name || member.email}<small className="role-label">Role: {member.role}</small></span>
              {canManageRoles && member.role !== "owner" ?               <select value={member.role} onChange={(event) => void updateMemberRole(member, event.target.value)}>
                <option value="member">Member</option>
                <option value="admin">Admin</option>
              </select> : <span className="role-label">Managed by owner</span>}
              {canManageRoles && member.role !== "owner" && <button type="button" className="secondary" onClick={() => void transferOwnership(member)}>Transfer ownership</button>}
              {canRemove && member.role !== "owner" && <button type="button" className="danger" onClick={() => void removeMember(member)}>Remove</button>}
            </div>
            );
          })}
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
          <div className="section-heading">
            <h2>API keys</h2>
            <span>{apiKeys.filter((key) => key.is_active).length} active / {apiKeys.length} total</span>
          </div>
          <p className="muted">Use a key for scripts or integrations. Send it as <code>X-API-Key</code> to <code>/api/v1/urls/api/organizations/&lt;organization-id&gt;</code>.</p>
          <form className="settings-form" onSubmit={createApiKey}>
            <input value={apiKeyName} onChange={(event) => setApiKeyName(event.target.value)} placeholder="Key name" required />
            <button type="submit">Generate key</button>
          </form>
          {newApiKey && (
            <div className="secret-output">
              <p className="api-key-output">{newApiKey}</p>
              <button type="button" className="secondary" onClick={() => void navigator.clipboard.writeText(newApiKey)}>Copy</button>
              <button type="button" className="secondary" onClick={() => setNewApiKey("")}>Hide</button>
            </div>
          )}
          <div className="key-list">
            {apiKeys.map((key) => (
              <div className="key-row" key={key.id}>
                <span>{key.name} ({key.key_prefix}...) - {key.usage_count} uses {!key.is_active && <small className="role-label">Revoked</small>}</span>
                {key.is_active && <span className="key-actions"><button className="secondary" onClick={() => void rotateApiKey(key.id)}>Rotate</button><button className="secondary" onClick={() => void revokeApiKey(key.id)}>Revoke</button></span>}
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
