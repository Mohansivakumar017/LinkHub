import { useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { useSelectedOrganization } from "../../../shared/session/organization";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";

type Org = { id: string; name: string };
type Row = { bucket?: string; value?: string; count: number };
type TopLink = {
  url_id: string;
  short_code: string;
  original_url: string;
  title?: string | null;
  is_deleted: boolean;
  clicks: number;
};

export function AnalyticsPage() {
  const { api } = useSession();
  const [orgs, setOrgs] = useState<Org[]>([]);
  const { organizationId: org, selectOrganization } = useSelectedOrganization();
  const [days, setDays] = useState("30");
  const [overview, setOverview] = useState<{
    total_clicks: number;
    unique_clicks: number;
    range_days: number;
  } | null>(null);
  const [series, setSeries] = useState<Row[]>([]);
  const [granularity, setGranularity] = useState("daily");
  const [breakdown, setBreakdown] = useState<Row[]>([]);
  const [topLinks, setTopLinks] = useState<TopLink[]>([]);
  const [dimension, setDimension] = useState("browser");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void api.request(`${apiBaseUrl}/organizations`).then(async (response) => {
      if (response.ok) setOrgs(await response.json() as Org[]);
      else setError(await readApiErrorMessage(response, "Could not load organizations."));
    });
  }, [api]);

  async function load() {
    if (!org) return;
    setLoading(true);
    setError("");
    const query = `days=${days}`;
    const base = `${apiBaseUrl}/analytics/organizations/${org}`;
    const [overviewResponse, seriesResponse, topResponse, breakdownResponse] =
      await Promise.all([
        api.request(`${base}/overview?${query}`),
        api.request(`${base}/timeseries?${query}&granularity=${granularity}`),
        api.request(`${base}/top-links?${query}&limit=10`),
        api.request(`${base}/breakdown?${query}&dimension=${dimension}&limit=20`),
      ]);
    const failures: string[] = [];
    if (overviewResponse.ok) setOverview(await overviewResponse.json());
    else failures.push(await readApiErrorMessage(overviewResponse, "overview"));
    if (seriesResponse.ok) setSeries(await seriesResponse.json());
    else failures.push(await readApiErrorMessage(seriesResponse, `${granularity} click history`));
    if (topResponse.ok) setTopLinks(await topResponse.json());
    else failures.push(await readApiErrorMessage(topResponse, "top links"));
    if (breakdownResponse.ok) setBreakdown(await breakdownResponse.json());
    else failures.push(await readApiErrorMessage(breakdownResponse, "traffic breakdown"));
    if (failures.length) setError(`Could not load ${failures.join(", ")}.`);
    setLoading(false);
  }

  useEffect(() => {
    if (org) void load();
  }, [org, days, dimension, granularity]);

  return (
    <WorkspaceLayout title="Analytics" description="Understand link performance and traffic sources.">
      <section className="toolbar card">
        <label>Organization
          <select value={org} onChange={(event) => selectOrganization(event.target.value)}>
            <option value="">Select an organization</option>
            {orgs.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label>Period
          <select value={days} onChange={(event) => setDays(event.target.value)}>
            <option value="7">Last 7 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
            <option value="365">Last year</option>
          </select>
        </label>
        <label>Breakdown
          <select value={dimension} onChange={(event) => setDimension(event.target.value)}>
            <option value="browser">Browser</option>
            <option value="country">Country</option>
            <option value="city">City</option>
            <option value="device">Device</option>
            <option value="os">Operating system</option>
            <option value="referrer">Referrer</option>
          </select>
        </label>
        <label>Time series
          <select value={granularity} onChange={(event) => setGranularity(event.target.value)}>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>
        <button onClick={() => void load()} disabled={!org || loading}>
          {loading ? "Loading…" : "Refresh analytics"}
        </button>
      </section>
      {error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}
      {!org && <section className="card empty-state"><h2>Select an organization</h2><p className="muted">Choose an organization to view its click performance.</p></section>}
      {org && loading && <section className="card"><p className="muted">Loading analytics…</p></section>}
      {overview && <section className="stats-grid">
        <article className="card stat"><span className="muted">Total clicks ({overview.range_days} days)</span><strong>{overview.total_clicks}</strong></article>
        <article className="card stat"><span className="muted">Unique visitors</span><strong>{overview.unique_clicks}</strong></article>
      </section>}
      {org && <section className="analytics-grid">
        <article className="card">
          <h2>{granularity[0].toUpperCase() + granularity.slice(1)} clicks</h2>
          {!loading && !series.length ? <p className="muted">No click data for this period.</p> : series.map((row, index) => <div className="admin-row" key={`${row.bucket}-${index}`}><span>{row.bucket}</span><strong>{row.count}</strong></div>)}
        </article>
        <article className="card">
          <h2>Top links</h2>
          {!loading && !topLinks.length ? <p className="muted">No top links for this period.</p> : topLinks.map((link) => <div className="admin-row" key={link.url_id}><span><strong>{link.title || link.short_code}</strong><small>{link.short_code}{link.is_deleted ? " · Deleted link history" : ""} · {link.original_url}</small></span><strong>{link.clicks}</strong></div>)}
        </article>
        <article className="card">
          <h2>{dimension}</h2>
          {!loading && !breakdown.length ? <p className="muted">No traffic breakdown data available.</p> : breakdown.map((row, index) => <div className="admin-row" key={`${row.value}-${index}`}><span>{row.value || "Unknown"}</span><strong>{row.count}</strong></div>)}
        </article>
      </section>}
    </WorkspaceLayout>
  );
}
