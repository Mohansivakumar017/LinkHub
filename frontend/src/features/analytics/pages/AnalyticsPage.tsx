import { useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
type Org = { id: string; name: string }; type Row = { bucket?: string; value?: string; count: number };
export function AnalyticsPage() {
  const { api } = useSession(); const [orgs, setOrgs] = useState<Org[]>([]), [org, setOrg] = useState("");
  const [overview, setOverview] = useState<{ total_clicks: number; unique_clicks: number; range_days: number } | null>(null);
  const [series, setSeries] = useState<Row[]>([]), [breakdown, setBreakdown] = useState<Row[]>([]), [dimension, setDimension] = useState("browser");
  useEffect(() => { void api.request(`${apiBaseUrl}/organizations`).then(async r => r.ok && setOrgs(await r.json())); }, [api]);
  async function load() {
    if (!org) return; const q = `${apiBaseUrl}/analytics/organizations/${org}`;
    const [a, b, c] = await Promise.all([api.request(`${q}/overview?days=30`), api.request(`${q}/timeseries?days=30&granularity=daily`), api.request(`${q}/breakdown?days=30&dimension=${dimension}`)]);
    if (a.ok) setOverview(await a.json()); if (b.ok) setSeries(await b.json()); if (c.ok) setBreakdown(await c.json());
  }
  useEffect(() => { if (org) void load(); }, [org, dimension]);
  return <WorkspaceLayout title="Analytics" description="Understand link performance and traffic sources."><section className="toolbar card"><select value={org} onChange={e => setOrg(e.target.value)}><option value="">Select an organization</option>{orgs.map(o => <option value={o.id} key={o.id}>{o.name}</option>)}</select><select value={dimension} onChange={e => setDimension(e.target.value)}><option value="browser">Browser</option><option value="country">Country</option><option value="device">Device</option><option value="referrer">Referrer</option></select><button onClick={() => void load()}>Refresh analytics</button></section>{overview && <section className="stats-grid"><article className="card stat"><span className="muted">Total clicks (30 days)</span><strong>{overview.total_clicks}</strong></article><article className="card stat"><span className="muted">Unique visitors</span><strong>{overview.unique_clicks}</strong></article></section>}<section className="analytics-grid"><article className="card"><h2>Daily clicks</h2>{series.map((r, i) => <div className="admin-row" key={i}><span>{r.bucket}</span><strong>{r.count}</strong></div>)}</article><article className="card"><h2>{dimension}</h2>{breakdown.map((r, i) => <div className="admin-row" key={i}><span>{r.value}</span><strong>{r.count}</strong></div>)}</article></section></WorkspaceLayout>;
}
