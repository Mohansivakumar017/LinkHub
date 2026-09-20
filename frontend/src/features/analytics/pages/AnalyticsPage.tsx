import { useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
type Org = { id: string; name: string }; type Row = { bucket?: string; value?: string; count: number };
export function AnalyticsPage() {
  const { api } = useSession(); const [orgs, setOrgs] = useState<Org[]>([]), [org, setOrg] = useState("");
  const [overview, setOverview] = useState<{ total_clicks: number; unique_clicks: number; range_days: number } | null>(null);
  const [series, setSeries] = useState<Row[]>([]), [breakdown, setBreakdown] = useState<Row[]>([]), [dimension, setDimension] = useState("browser");
  const [loading, setLoading] = useState(false), [error, setError] = useState("");
  useEffect(() => { void api.request(`${apiBaseUrl}/organizations`).then(async r => r.ok && setOrgs(await r.json())); }, [api]);
  async function load() {
    if (!org) return; setLoading(true); setError(""); const q = `${apiBaseUrl}/analytics/organizations/${org}`;
    const [a, b, c] = await Promise.all([api.request(`${q}/overview?days=30`), api.request(`${q}/timeseries?days=30&granularity=daily`), api.request(`${q}/breakdown?days=30&dimension=${dimension}`)]);
    if (a.ok) setOverview(await a.json()); else setError("Could not load analytics overview");
    if (b.ok) setSeries(await b.json()); else setError("Could not load analytics timeseries");
    if (c.ok) setBreakdown(await c.json()); else setError("Could not load analytics breakdown");
    setLoading(false);
  }
  useEffect(() => { if (org) void load(); }, [org, dimension]);
  return <WorkspaceLayout title="Analytics" description="Understand link performance and traffic sources."><section className="toolbar card"><select value={org} onChange={e => setOrg(e.target.value)}><option value="">Select an organization</option>{orgs.map(o => <option value={o.id} key={o.id}>{o.name}</option>)}</select><select value={dimension} onChange={e => setDimension(e.target.value)}><option value="browser">Browser</option><option value="country">Country</option><option value="device">Device</option><option value="referrer">Referrer</option></select><button onClick={() => void load()} disabled={!org || loading}>{loading ? "Loading…" : "Refresh analytics"}</button></section>{error && <p className="auth-error" role="alert">{error}</p>}{!org && <section className="card empty-state"><h2>Select an organization</h2><p className="muted">Choose an organization to view its click performance.</p></section>}{org && loading && <section className="card"><p className="muted">Loading analytics…</p></section>}{overview && <section className="stats-grid"><article className="card stat"><span className="muted">Total clicks (30 days)</span><strong>{overview.total_clicks}</strong></article><article className="card stat"><span className="muted">Unique visitors</span><strong>{overview.unique_clicks}</strong></article></section>}<section className="analytics-grid"><article className="card"><h2>Daily clicks</h2>{!loading && !series.length ? <p className="muted">No click data for this period.</p> : series.map((r, i) => <div className="admin-row" key={i}><span>{r.bucket}</span><strong>{r.count}</strong></div>)}</article><article className="card"><h2>{dimension}</h2>{!loading && !breakdown.length ? <p className="muted">No traffic breakdown data available.</p> : breakdown.map((r, i) => <div className="admin-row" key={i}><span>{r.value}</span><strong>{r.count}</strong></div>)}</article></section></WorkspaceLayout>;
}
