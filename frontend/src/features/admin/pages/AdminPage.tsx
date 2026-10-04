import { useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";

type AdminItem = Record<string, string | number | boolean | null>;
type AdminPage = { items: AdminItem[]; total: number; offset: number; limit: number };

function value(item: AdminItem, key: string) {
  return String(item[key] ?? "");
}

export function AdminPage() {
  const { api } = useSession();
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [users, setUsers] = useState<AdminItem[]>([]);
  const [logs, setLogs] = useState<AdminItem[]>([]);
  const [organizations, setOrganizations] = useState<AdminItem[]>([]);
  const [links, setLinks] = useState<AdminItem[]>([]);
  const [totals, setTotals] = useState({ users: 0, logs: 0, organizations: 0, links: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [auditAction, setAuditAction] = useState("");
  const [auditResource, setAuditResource] = useState("");
  const [deleteLinkId, setDeleteLinkId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const limit = 25;

  async function loadList(path: string, offset: number, filters = "") {
    const response = await api.request(`${apiBaseUrl}${path}?offset=${offset}&limit=${limit}${filters}`);
    if (!response.ok) throw new Error(await readApiErrorMessage(response, "Could not load administration data."));
    return await response.json() as AdminPage;
  }

  async function loadAll() {
    setLoading(true); setError("");
    try {
      const auditFilters = `${auditAction.trim() ? `&action=${encodeURIComponent(auditAction.trim())}` : ""}${auditResource ? `&resource_type=${encodeURIComponent(auditResource)}` : ""}`;
      const [metricResponse, userPage, logPage, organizationPage, linkPage] = await Promise.all([
        api.request(`${apiBaseUrl}/admin/metrics`),
        loadList("/admin/users", 0),
        loadList("/admin/audit-logs", 0, auditFilters),
        loadList("/admin/organizations", 0),
        loadList("/admin/links", 0),
      ]);
      if (!metricResponse.ok) throw new Error(await readApiErrorMessage(metricResponse, "Could not load platform metrics."));
      setMetrics(await metricResponse.json());
      setUsers(userPage.items); setLogs(logPage.items); setOrganizations(organizationPage.items); setLinks(linkPage.items);
      setTotals({ users: userPage.total, logs: logPage.total, organizations: organizationPage.total, links: linkPage.total });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load administration data");
    } finally {
      setLoading(false);
    }
  }

  async function updateUser(id: string, path: "active" | "platform-admin", value: boolean) {
    const response = await api.request(`${apiBaseUrl}/admin/users/${id}/${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(path === "active" ? { is_active: value } : { is_platform_admin: value }),
    });
    if (!response.ok) {
      setError(await readApiErrorMessage(response, "Could not update user access."));
      return;
    }
    setMessage(path === "active"
      ? value ? "User account activated." : "User account deactivated."
      : value ? "Platform administrator access granted." : "Platform administrator access revoked.");
    await loadAll();
  }

  async function restoreLink(id: string) {
    const response = await api.request(`${apiBaseUrl}/admin/links/${id}/restore`, { method: "PATCH" });
    if (!response.ok) {
      setError(await readApiErrorMessage(
        response,
        "Could not restore link. Its alias may already belong to another active link.",
      ));
      return;
    }
    setMessage("Link restored.");
    await loadAll();
  }

  async function hardDeleteLink(id: string): Promise<boolean> {
    const response = await api.request(`${apiBaseUrl}/admin/links/${id}`, { method: "DELETE" });
    if (!response.ok) {
      setError(await readApiErrorMessage(response, "Could not permanently delete link."));
      return false;
    }

      setMessage("Link permanently deleted.");
      await loadAll();
      return true;
    }

    async function confirmHardDelete() {
      if (!deleteLinkId) return;
      setDeleting(true);
      const deleted = await hardDeleteLink(deleteLinkId);
      setDeleting(false);
      if (deleted) setDeleteLinkId(null);
    }

  async function loadMore(kind: "users" | "logs" | "organizations" | "links") {
    try {
      const paths = { users: "/admin/users", logs: "/admin/audit-logs", organizations: "/admin/organizations", links: "/admin/links" };
      const filters = kind === "logs" ? `${auditAction.trim() ? `&action=${encodeURIComponent(auditAction.trim())}` : ""}${auditResource ? `&resource_type=${encodeURIComponent(auditResource)}` : ""}` : "";
      const page = await loadList(paths[kind], { users, logs, organizations, links }[kind].length, filters);
      const setters = { users: setUsers, logs: setLogs, organizations: setOrganizations, links: setLinks };
      setters[kind](current => [...current, ...page.items]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load more data");
    }

  }

  useEffect(() => { void loadAll(); }, [api]);

  function panel(title: string, kind: "users" | "logs" | "organizations" | "links", items: AdminItem[], field: string, empty: string) {
    const total = totals[kind];
       return <article className="card admin-panel"><div className="section-heading"><div><h2>{title}</h2><span>{total} total</span></div>{items.length < total && <button type="button" className="secondary" onClick={() => void loadMore(kind)}>Load more</button>}</div>{!items.length ? <p className="muted">{empty}</p> : <div className="admin-list">{items.map((item, index) => <div className="admin-row" key={`${kind}-${index}`}><div><span>{value(item, field)}</span>{kind === "logs" && <small>{value(item, "resource_type")}</small>}{kind === "users" && <small>{value(item, "is_active") === "true" ? "Active" : "Inactive"} · {value(item, "is_platform_admin") === "true" ? "Platform admin" : "User"}</small>}{kind === "links" && <small>{value(item, "is_deleted") === "true" ? "Deleted" : value(item, "is_archived") === "true" ? "Archived" : "Active"}</small>}</div>{kind === "users" && <div className="link-actions"><button type="button" className="secondary" onClick={() => void updateUser(value(item, "id"), "active", value(item, "is_active") !== "true")}>{value(item, "is_active") === "true" ? "Deactivate" : "Activate"}</button><button type="button" className="secondary" onClick={() => void updateUser(value(item, "id"), "platform-admin", value(item, "is_platform_admin") !== "true")}>{value(item, "is_platform_admin") === "true" ? "Revoke admin" : "Make admin"}</button></div>}{kind === "links" && value(item, "is_deleted") === "true" && <div className="link-actions"><button type="button" className="secondary" onClick={() => void restoreLink(value(item, "id"))}>Restore</button><button type="button" className="danger" onClick={() => setDeleteLinkId(value(item, "id"))}>Hard delete</button></div>}</div>)}</div>}</article>;
  }

  return <WorkspaceLayout title="Administration" description="Monitor platform activity and operational health." message={message}>{deleteLinkId && <ConfirmDialog title="Permanently delete link?" message="This removes the stored link record and cannot be undone." confirmLabel="Permanently delete" danger busy={deleting} onCancel={() => setDeleteLinkId(null)} onConfirm={() => void confirmHardDelete()} />}<div className="admin-toolbar"><div className="audit-filters"><input placeholder="Filter audit action" value={auditAction} onChange={event => setAuditAction(event.target.value)} /><select value={auditResource} onChange={event => setAuditResource(event.target.value)}><option value="">All resource types</option><option value="user">User</option><option value="organization">Organization</option><option value="url">Link</option><option value="api_key">API key</option></select><button type="button" className="secondary" onClick={() => void loadAll()} disabled={loading}>{loading ? "Loading…" : "Refresh data"}</button></div></div>{error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}{loading && !users.length ? <section className="card"><p className="muted">Loading administration data…</p></section> : <><section className="stats-grid">{Object.entries(metrics).map(([key, count]) => <article className="card stat" key={key}><span className="muted">Platform {key}</span><strong>{count}</strong></article>)}</section><section className="admin-grid">{panel("Users", "users", users, "email", "No users found.")}{panel("Audit activity", "logs", logs, "action", "No audit activity found.")}{panel("Organizations", "organizations", organizations, "name", "No organizations found.")}{panel("Links", "links", links, "short_code", "No links found.")}</section></>}</WorkspaceLayout>;
}
