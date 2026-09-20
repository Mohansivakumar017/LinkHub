import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";

type LinkItem = {
  id: string; short_code: string; original_url: string; title?: string | null;
  custom_alias?: string | null; is_private: boolean; password_protected: boolean;
  is_archived: boolean; expires_at?: string | null; click_limit?: number | null;
};
type Org = { id: string; name: string };

export function LinksPage() {
  const { api } = useSession();
  const [orgs, setOrgs] = useState<Org[]>([]), [org, setOrg] = useState("");
  const selectedOrg = orgs.find(item => item.id === org);
  const [links, setLinks] = useState<LinkItem[]>([]), [target, setTarget] = useState("");
  const [title, setTitle] = useState(""), [alias, setAlias] = useState("");
  const [expires, setExpires] = useState(""), [password, setPassword] = useState("");
  const [clickLimit, setClickLimit] = useState(""), [oneTime, setOneTime] = useState(false);
  const [privateLink, setPrivateLink] = useState(false), [search, setSearch] = useState("");
  const [archived, setArchived] = useState(false), [selected, setSelected] = useState<string[]>([]);
  const [csv, setCsv] = useState(""), [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState(""), [error, setError] = useState("");
  const [loading, setLoading] = useState(false), [hasMore, setHasMore] = useState(false);
  useEffect(() => { void api.request(`${apiBaseUrl}/organizations`).then(async r => r.ok && setOrgs(await r.json())); }, [api]);
  async function load(append = false) {
    if (!org) return;
    setLoading(true); setError("");
    const q = new URLSearchParams({ limit: "50", offset: append ? String(links.length) : "0", descending: "true" });
    if (search.trim()) q.set("search", search.trim()); if (archived) q.set("archived", "true");
    const r = await api.request(`${apiBaseUrl}/urls/organizations/${org}?${q}`);
    if (r.ok) {
      const next = await r.json() as LinkItem[];
      setLinks(current => append ? [...current, ...next] : next);
      setHasMore(next.length === 50);
      if (!append) setSelected([]);
    } else {
      const body = await r.json().catch(() => ({})) as { detail?: string };
      setError(body.detail ?? "Could not load links");
    }
    setLoading(false);
  }
  async function create(e: FormEvent) {
    e.preventDefault(); if (!org) return setMessage("Select an organization first");
    const r = await api.request(`${apiBaseUrl}/urls`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: org, original_url: target, title: title || undefined, custom_alias: alias || undefined,
        expires_at: expires ? new Date(expires).toISOString() : undefined, password: password || undefined,
        click_limit: clickLimit ? Number(clickLimit) : undefined, one_time: oneTime, is_private: privateLink }) });
    if (!r.ok) return setMessage("Could not create link");
    setTarget(""); setTitle(""); setAlias(""); setExpires(""); setPassword(""); setClickLimit(""); setOneTime(false); setPrivateLink(false);
    setMessage("Link created"); await load();
  }
  async function importCsv(e: FormEvent) {
    e.preventDefault(); if (!org) return;
    const rows = csv.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
    const urls = rows[0]?.toLowerCase() === "original_url" ? rows.slice(1) : rows;
    const r = await api.request(`${apiBaseUrl}/urls/bulk/create`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: org, rows: urls.map(original_url => ({ original_url })) }) });
    if (!r.ok) return setMessage("Bulk import failed");
    const b = await r.json(); setCsv(""); setMessage(`Imported ${b.created.length} links${b.failed.length ? `; ${b.failed.length} failed` : ""}`); await load();
  }
  async function upload(e: FormEvent) {
    e.preventDefault(); if (!org || !file) return;
    const body = new FormData(); body.append("file", file);
    const r = await api.request(`${apiBaseUrl}/urls/bulk/upload?organization_id=${org}`, { method: "POST", body });
    if (!r.ok) return setMessage("CSV upload failed");
    const b = await r.json(); setFile(null); setMessage(`Uploaded ${b.created.length} links${b.failed.length ? `; ${b.failed.length} failed` : ""}`); await load();
  }
  async function action(path: string, method = "POST") { const r = await api.request(`${apiBaseUrl}${path}`, { method }); return r.ok; }
  async function edit(link: LinkItem) {
    const nextTitle = window.prompt("Link title", link.title ?? ""); if (nextTitle === null) return;
    const url = window.prompt("Destination URL", link.original_url); if (url === null) return;
    const r = await api.request(`${apiBaseUrl}/urls/${link.id}?organization_id=${org}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: nextTitle, original_url: url }) });
    setMessage(r.ok ? "Link updated" : "Could not update link"); if (r.ok) await load();
  }
  async function qr(link: LinkItem) {
    const r = await api.request(`${apiBaseUrl}/urls/${link.id}/qr?organization_id=${org}`); if (!r.ok) return setMessage("Could not download QR code");
    const a = document.createElement("a"); a.href = URL.createObjectURL(await r.blob()); a.download = `${link.short_code}.png`; a.click();
  }
  async function bulkDelete() { if (!org || !selected.length) return; const r = await api.request(`${apiBaseUrl}/urls/bulk/delete`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ organization_id: org, ids: selected }) }); setMessage(r.ok ? "Selected links deleted" : "Bulk delete failed"); if (r.ok) await load(); }
  async function toggle(link: LinkItem) { const ok = await action(`/urls/${link.id}/${link.is_archived ? "restore" : "archive"}?organization_id=${org}`); setMessage(ok ? (link.is_archived ? "Link restored" : "Link archived") : "Could not update link status"); if (ok) await load(); }
  async function remove(link: LinkItem) { if (!window.confirm(`Delete ${link.short_code}?`)) return; const ok = await action(`/urls/${link.id}?organization_id=${org}`, "DELETE"); setMessage(ok ? "Link deleted" : "Could not delete link"); if (ok) await load(); }
  async function duplicate(link: LinkItem) { const ok = await action(`/urls/${link.id}/duplicate?organization_id=${org}`); setMessage(ok ? "Link duplicated" : "Could not duplicate link"); if (ok) await load(); }
  async function copy(link: LinkItem) { await navigator.clipboard.writeText(new URL(`/?link=${encodeURIComponent(link.short_code)}`, window.location.origin).toString()); setMessage("Copied to clipboard"); }
  async function openLink(link: LinkItem) {
    const secret = link.password_protected ? window.prompt("Link password") : null;
    if (link.password_protected && secret === null) return;
    const query = secret ? `?password=${encodeURIComponent(secret)}` : "";
    const r = await api.request(`${apiBaseUrl}/urls/resolve/${encodeURIComponent(link.short_code)}${query}`);
    if (!r.ok) { const b = await r.json().catch(() => ({})); setMessage(typeof b.detail === "string" ? b.detail : "Could not open link"); return; }
    const b = await r.json(); window.open(b.original_url, "_blank", "noopener,noreferrer");
  }
  return <WorkspaceLayout title="Link workspace" description="Create, organize, and share trackable links." message={message}>
    <section className="toolbar card"><div className="organization-picker"><label>Organization<select value={org} onChange={e => { setOrg(e.target.value); setLinks([]); setHasMore(false); setError(""); }}><option value="">Select an organization</option>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>{selectedOrg && <div className="organization-context"><strong>{selectedOrg.name}</strong><span>Organization ID</span><code>{selectedOrg.id}</code></div>}</div><div className="link-toolbar-actions"><button className="secondary" onClick={() => void load()} disabled={!org || loading}>{loading ? "Loading…" : "Load links"}</button><label className="checkbox"><input type="checkbox" checked={archived} onChange={e => { setArchived(e.target.checked); setLinks([]); }} /> Show archived</label></div><label className="search-field">Search links<input placeholder="Search by title, alias, or URL" value={search} onChange={e => setSearch(e.target.value)} /></label></section>
    {error && <p className="auth-error" role="alert">{error}</p>}
    {!org && <section className="card empty-state"><h2>Select an organization</h2><p className="muted">Choose an organization above to view and manage its links.</p></section>}
    <section className="card"><h2>Create a link</h2><form className="create-form" onSubmit={create}><input placeholder="Long URL" value={target} onChange={e => setTarget(e.target.value)} required /><input placeholder="Title" value={title} onChange={e => setTitle(e.target.value)} /><input placeholder="Custom alias" value={alias} onChange={e => setAlias(e.target.value)} /><input type="datetime-local" value={expires} onChange={e => setExpires(e.target.value)} title="Expiration" /><input type="number" min="1" placeholder="Click limit" value={clickLimit} onChange={e => setClickLimit(e.target.value)} /><input type="password" placeholder="Optional password" value={password} onChange={e => setPassword(e.target.value)} /><label className="checkbox"><input type="checkbox" checked={oneTime} onChange={e => setOneTime(e.target.checked)} /> One-time</label><label className="checkbox"><input type="checkbox" checked={privateLink} onChange={e => setPrivateLink(e.target.checked)} /> Private</label><button type="submit" disabled={!org}>Create link</button></form></section>
    <section className="card"><h2>CSV import</h2><form className="create-form" onSubmit={importCsv}><textarea placeholder="One URL per line (or original_url CSV header)" value={csv} onChange={e => setCsv(e.target.value)} /><button disabled={!org}>Import text</button></form><form className="create-form" onSubmit={upload}><input type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] ?? null)} /><button disabled={!org || !file}>Upload CSV</button></form>{selected.length > 0 && <button className="danger" onClick={() => void bulkDelete()}>Delete selected ({selected.length})</button>}</section>
    <section className="card"><div className="section-heading"><div><h2>Links</h2><span>{links.length ? `${links.length} loaded` : "No links loaded"}</span></div>{selected.length > 0 && <button className="danger" onClick={() => void bulkDelete()}>Delete selected ({selected.length})</button>}</div>{loading && !links.length ? <p className="muted">Loading links…</p> : !loading && !links.length && org ? <p className="muted">No links match the current filters.</p> : links.map(l => <article className="link-row" key={l.id}><div className="link-main"><label><input type="checkbox" checked={selected.includes(l.id)} onChange={e => setSelected(s => e.target.checked ? [...s, l.id] : s.filter(id => id !== l.id))} /><strong>{l.title || l.short_code}</strong></label><a href={l.original_url} target="_blank" rel="noreferrer">{l.original_url}</a><span className="muted">{l.is_archived ? "Archived" : "Active"}{l.password_protected ? " · Protected" : ""}{l.is_private ? " · Private" : ""}</span></div><div className="link-actions"><button className="secondary" onClick={() => void openLink(l)}>Open</button><button className="secondary" onClick={() => void edit(l)}>Edit</button><button className="secondary" onClick={() => void toggle(l)}>{l.is_archived ? "Restore" : "Archive"}</button><button className="secondary" onClick={() => void duplicate(l)}>Duplicate</button><button className="secondary" onClick={() => void qr(l)}>QR</button><button className="secondary" onClick={() => void copy(l)}>Copy</button><button className="danger" onClick={() => void remove(l)}>Delete</button></div></article>)}{hasMore && <div className="load-more"><button className="secondary" onClick={() => void load(true)} disabled={loading}>{loading ? "Loading…" : "Load more links"}</button></div>}</section>
  </WorkspaceLayout>;
}
