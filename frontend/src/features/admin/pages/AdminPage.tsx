import { useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
export function AdminPage() {
  const { api } = useSession(); const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [users, setUsers] = useState<any[]>([]), [logs, setLogs] = useState<any[]>([]), [organizations, setOrganizations] = useState<any[]>([]), [links, setLinks] = useState<any[]>([]);
  useEffect(() => { void Promise.all([api.request(`${apiBaseUrl}/admin/metrics`), api.request(`${apiBaseUrl}/admin/users?limit=100`), api.request(`${apiBaseUrl}/admin/audit-logs?limit=100`), api.request(`${apiBaseUrl}/admin/organizations?limit=100`), api.request(`${apiBaseUrl}/admin/links?limit=100`)]).then(async ([a, u, l, o, k]) => {
    if (a.ok) setMetrics(await a.json()); const list = async (r: Response) => { if (!r.ok) return []; const b = await r.json(); return Array.isArray(b) ? b : (b.items ?? []); };
    setUsers(await list(u)); setLogs(await list(l)); setOrganizations(await list(o)); setLinks(await list(k));
  }); }, [api]);
  return <WorkspaceLayout title="Administration" description="Monitor platform activity and operational health."><section className="stats-grid">{Object.entries(metrics).map(([k, v]) => <article className="card stat" key={k}><span className="muted">Platform {k}</span><strong>{v}</strong></article>)}</section><section className="admin-grid">{[["Users", users.map(x => x.email)], ["Audit activity", logs.map(x => `${x.action} (${x.resource_type})`)], ["Organizations", organizations.map(x => x.name)], ["Links", links.map(x => x.short_code)]].map(([title, items]) => <article className="card" key={title as string}><h2>{title as string}</h2>{(items as string[]).map((x, i) => <div className="admin-row" key={i}>{x}</div>)}</article>)}</section></WorkspaceLayout>;
}
