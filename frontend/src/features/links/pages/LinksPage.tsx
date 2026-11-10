import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { useSelectedOrganization } from "../../../shared/session/organization";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { NavLink, useLocation } from "react-router-dom";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { describeSharedLinkFailure } from "../../shared-link/access";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";

type LinkItem = {
  id: string; short_code: string; original_url: string; title?: string | null;
  short_url?: string; qr_code_url?: string;
  custom_alias?: string | null; is_private: boolean; password_protected: boolean;
  is_archived: boolean; expires_at?: string | null; click_limit?: number | null;
};
type Org = { id: string; name: string };

function explainImportFailure(reason: string): string {
  if (reason === "alias already taken") {
    return "alias is already in use by an active link; choose a different alias or leave it blank to generate one";
  }
  return reason;
}

export function LinksPage() {
  const { api } = useSession();
  const { pathname } = useLocation();
  const page = pathname.endsWith("/create") ? "create" : pathname.endsWith("/import") ? "import" : "manage";
  const [orgs, setOrgs] = useState<Org[]>([]);
  const { organizationId: org, selectOrganization } = useSelectedOrganization();
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
  const [protectedLink, setProtectedLink] = useState<LinkItem | null>(null);
  const [linkPassword, setLinkPassword] = useState("");
  const [linkPasswordError, setLinkPasswordError] = useState("");
  const [openingLink, setOpeningLink] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<LinkItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [editTarget, setEditTarget] = useState<LinkItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editUrl, setEditUrl] = useState("");
  useEffect(() => { void api.request(`${apiBaseUrl}/organizations`).then(async r => {
    if (r.ok) setOrgs(await r.json());
    else setError(await readApiErrorMessage(r, "Could not load organizations."));
  }); }, [api]);
  async function load(append = false): Promise<boolean> {
    if (!org) {
      setError("Select an organization above to load and manage links.");
      return false;
    }
    setLoading(true); setError("");
    const q = new URLSearchParams({ limit: "50", offset: append ? String(links.length) : "0", descending: "true" });
    if (search.trim()) q.set("search", search.trim()); if (archived) q.set("archived", "true");
    const r = await api.request(`${apiBaseUrl}/urls/organizations/${org}?${q}`);
    if (r.ok) {
      const next = await r.json() as LinkItem[];
      setLinks(current => append ? [...current, ...next] : next);
      setHasMore(next.length === 50);
      if (!append) setSelected([]);
      setLoading(false);
      return true;
    } else {
      setError(await readApiErrorMessage(r, "Could not load links."));
    }
    setLoading(false);
    return false;
  }
  async function create(e: FormEvent) {
    e.preventDefault(); setError(""); setMessage("");
    if (!org) return setError("Select an organization before creating a link.");
    const r = await api.request(`${apiBaseUrl}/urls`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: org, original_url: target, title: title || undefined, custom_alias: alias || undefined,
        expires_at: expires ? new Date(expires).toISOString() : undefined, password: password || undefined,
        click_limit: clickLimit ? Number(clickLimit) : undefined, one_time: oneTime, is_private: privateLink }) });
    if (!r.ok) return setError(await readApiErrorMessage(r, "Could not create link."));
    setTarget(""); setTitle(""); setAlias(""); setExpires(""); setPassword(""); setClickLimit(""); setOneTime(false); setPrivateLink(false);
    setMessage("Link created"); await load();
  }
  async function importCsv(e: FormEvent) {
    e.preventDefault();
    setError(""); setMessage("");
    if (!org) return setError("Select an organization before importing links.");
    if (!csv.trim()) return setError("Paste CSV content before importing.");
    const content = csv.includes(",") || /^\s*original_url\s*$/im.test(csv.split(/\r?\n/, 1)[0] ?? "")
      ? csv
      : `original_url\n${csv}`;
    const body = new FormData();
    body.append("file", new Blob([content], { type: "text/csv" }), "pasted-links.csv");
    const r = await api.request(`${apiBaseUrl}/urls/bulk/upload?organization_id=${org}`, { method: "POST", body });
    if (!r.ok) {
      return setError(await readApiErrorMessage(r, "Could not import pasted links."));
    }
    const b = await r.json() as { created: LinkItem[]; failed: Array<{ index: number; reason: string }> };
    setCsv("");
    const refreshed = await load();
    if (b.failed.length) {
      setError(`Imported ${b.created.length} links; ${b.failed.length} row${b.failed.length === 1 ? "" : "s"} could not be imported: ${b.failed.map(item => `row ${item.index + 1}: ${explainImportFailure(item.reason)}`).join("; ")}${refreshed ? "" : " The link list also could not be refreshed."}`);
    } else {
      setMessage(`Imported ${b.created.length} links.`);
    }
  }
  async function upload(e: FormEvent) {
    e.preventDefault();
    setError(""); setMessage("");
    if (!org) return setError("Select an organization before uploading a CSV.");
    if (!file) return setError("Choose a CSV file before uploading.");
    const body = new FormData(); body.append("file", file);
    const r = await api.request(`${apiBaseUrl}/urls/bulk/upload?organization_id=${org}`, { method: "POST", body });
    if (!r.ok) {
      return setError(await readApiErrorMessage(r, "Could not upload this CSV."));
    }
    const b = await r.json() as { created: LinkItem[]; failed: Array<{ index: number; reason: string }> };
    setFile(null);
    const refreshed = await load();
    if (b.failed.length) {
      setError(`Uploaded ${b.created.length} links; ${b.failed.length} row${b.failed.length === 1 ? "" : "s"} could not be imported: ${b.failed.map(item => `row ${item.index + 1}: ${explainImportFailure(item.reason)}`).join("; ")}${refreshed ? "" : " The link list also could not be refreshed."}`);
    } else {
      setMessage(`Uploaded ${b.created.length} links.`);
    }
  }
  async function action(path: string, method = "POST") {
    const r = await api.request(`${apiBaseUrl}${path}`, { method });
    return r.ok ? null : await readApiErrorMessage(r, "The link action could not be completed.");
  }
  async function edit(link: LinkItem) {
    setEditTarget(link);
    setEditTitle(link.title ?? "");
    setEditUrl(link.original_url);
  }
  async function saveEdit(event: FormEvent) {
    event.preventDefault();
    if (!editTarget) return;
    const r = await api.request(`${apiBaseUrl}/urls/${editTarget.id}?organization_id=${org}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: editTitle, original_url: editUrl }) });
    if (r.ok) {
      setError("");
      setMessage("Link updated.");
    } else {
      setMessage("");
      setError(await readApiErrorMessage(r, "Could not update link."));
    }
    if (r.ok) {
      setEditTarget(null);
      await load();
    }
  }
  async function qr(link: LinkItem) {
    setError(""); setMessage("");
    if (!org) return setError("Select an organization before downloading a QR code.");
    const r = await api.request(
      link.qr_code_url || `${apiBaseUrl}/urls/${link.id}/qr?organization_id=${org}`,
    );
    if (!r.ok) return setError(await readApiErrorMessage(r, "Could not download the QR code."));
    const objectUrl = URL.createObjectURL(await r.blob());
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = `${link.short_code}.png`;
    a.click();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    setMessage("QR code downloaded.");
  }
  async function bulkDelete() {
    setError(""); setMessage("");
    if (!org) return setError("Select an organization before deleting links.");
    if (!selected.length) return setError("Select at least one link first.");
    setDeleting(true);
    try {
      const r = await api.request(`${apiBaseUrl}/urls/bulk/delete`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ organization_id: org, ids: selected }) });
      if (!r.ok) {
        setError(await readApiErrorMessage(r, "Could not delete the selected links."));
        return;
      }
      setMessage("Selected links deleted.");
      setConfirmBulkDelete(false);
      await load();
    } finally {
      setDeleting(false);
    }
  }
  async function toggle(link: LinkItem) {
    setError(""); setMessage("");
    if (!org) return setError("Select an organization before changing link status.");
    const failure = await action(`/urls/${link.id}/${link.is_archived ? "restore" : "archive"}?organization_id=${org}`);
    if (failure) return setError(failure);
    setMessage(link.is_archived ? "Link restored." : "Link archived.");
    await load();
  }
  async function remove(link: LinkItem) {
    setError(""); setMessage("");
    if (!org) {
      setError("Select an organization before deleting links.");
      return false;
    }
    const failure = await action(`/urls/${link.id}?organization_id=${org}`, "DELETE");
    if (failure) {
      setError(failure);
      return false;
    }
    setMessage("Link deleted.");
    await load();
    return true;
  }
  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    const deleted = await remove(deleteTarget);
    setDeleting(false);
    if (deleted) setDeleteTarget(null);
  }
  async function duplicate(link: LinkItem) {
    setError(""); setMessage("");
    if (!org) return setError("Select an organization before duplicating links.");
    const failure = await action(`/urls/${link.id}/duplicate?organization_id=${org}`);
    if (failure) return setError(failure);
    setMessage("Link duplicated.");
    await load();
  }
  async function copy(link: LinkItem) {
    setError(""); setMessage("");
    try {
      await navigator.clipboard.writeText(
        link.short_url
          || new URL(`/?link=${encodeURIComponent(link.short_code)}`, window.location.origin).toString(),
      );
      setMessage("Share link copied to clipboard.");
    } catch {
      setError("Could not copy the share link. Check browser clipboard permissions and try again.");
    }
  }
  function openDestinationWindow(): Window | null {
    const popup = window.open("about:blank", "_blank");
    if (!popup) return null;
    popup.opener = null;
    const referrerPolicy = popup.document.createElement("meta");
    referrerPolicy.name = "referrer";
    referrerPolicy.content = "no-referrer";
    popup.document.head.append(referrerPolicy);
    popup.document.title = "Opening link…";
    return popup;
  }
  async function resolveLink(link: LinkItem, secret: string, destinationWindow: Window) {
    setOpeningLink(true);
    setLinkPasswordError("");
    const headers: HeadersInit = secret ? { "X-Link-Password": secret } : {};
    const r = await api.request(
      `${apiBaseUrl}/urls/resolve/${encodeURIComponent(link.short_code)}`,
      { cache: "no-store", headers },
    );
    if (!r.ok) {
      const body = await r.clone().json().catch(() => ({})) as { detail?: string; error?: { message?: string } };
      const detail = body.error?.message ?? body.detail ?? "";
      const failure = describeSharedLinkFailure(r.status, detail, r.headers.get("Retry-After")).message;
      destinationWindow.close();
      if (protectedLink) {
        setLinkPasswordError(failure);
      } else {
        setMessage("");
        setError(failure);
      }
      setOpeningLink(false);
      return;
    }
    const body = await r.json() as { original_url: string };
    setProtectedLink(null);
    setLinkPassword("");
    setOpeningLink(false);
    try {
      const destination = new URL(body.original_url);
      if (!["http:", "https:"].includes(destination.protocol)) {
        destinationWindow.close();
        setError("The link destination is not safe to open.");
        setOpeningLink(false);
        return;
      }
      destinationWindow.location.replace(destination.href);
      setError("");
      setMessage("Link opened in a new tab.");
    } catch {
      destinationWindow.close();
      setMessage("");
      setError("The destination could not be opened. Check your browser settings and try again.");
    }
  }
  function openLink(link: LinkItem) {
    if (link.password_protected) {
      setError("");
      setMessage("");
      setLinkPassword("");
      setLinkPasswordError("");
      setProtectedLink(link);
      return;
    }
    const destinationWindow = openDestinationWindow();
    if (!destinationWindow) {
      setMessage("");
      setError("Your browser blocked the new tab. Allow pop-ups for LinkHub and try again.");
      return;
    }
    void resolveLink(link, "", destinationWindow);
  }
  return <WorkspaceLayout title="Link workspace" description="Create, organize, and share trackable links.">
    {protectedLink && <div className="modal-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !openingLink) setProtectedLink(null); }}>
      <section className="card access-dialog" role="dialog" aria-modal="true" aria-labelledby="dashboard-password-title">
        <p className="eyebrow">PROTECTED LINK</p>
        <h2 id="dashboard-password-title">Enter link password</h2>
        <p className="muted">This link requires its password before the destination can be opened.</p>
        <form onSubmit={event => {
          event.preventDefault();
          const destinationWindow = openDestinationWindow();
          if (!destinationWindow) {
            setLinkPasswordError("Your browser blocked the new tab. Allow pop-ups for LinkHub and try again.");
            return;
          }
          void resolveLink(protectedLink, linkPassword, destinationWindow);
        }}>
          <label htmlFor="dashboard-link-password">Link password</label>
          <input id="dashboard-link-password" type="password" value={linkPassword} onChange={event => { setLinkPassword(event.target.value); setLinkPasswordError(""); }} autoFocus required aria-describedby="dashboard-password-help" />
          {linkPasswordError && <p className="auth-error" role="alert">{linkPasswordError}</p>}
          <p id="dashboard-password-help" className="field-help">The password is sent securely and is never stored in the browser.</p>
          <div className="dialog-actions">
            <button type="button" className="secondary" onClick={() => setProtectedLink(null)} disabled={openingLink}>Cancel</button>
            <button type="submit" disabled={openingLink}>{openingLink ? "Checking password…" : "Open link"}</button>
          </div>
        </form>
      </section>
    </div>}
    {deleteTarget && <ConfirmDialog title="Delete link?" message={`Delete ${deleteTarget.short_code}? The link will be removed from the workspace and its code becomes available for reuse. If reused, existing bookmarks and QR codes for this code will open the replacement link.`} confirmLabel="Delete link" danger busy={deleting} onCancel={() => setDeleteTarget(null)} onConfirm={() => void confirmDelete()} />}
    {confirmBulkDelete && <ConfirmDialog title="Delete selected links?" message={`Delete ${selected.length} selected links? Their codes become available for reuse. If reused, existing bookmarks and QR codes for those codes will open replacement links.`} confirmLabel="Delete selected links" danger busy={deleting} onCancel={() => setConfirmBulkDelete(false)} onConfirm={() => void bulkDelete()} />}
    {editTarget && <div className="modal-backdrop" role="presentation"><section className="card access-dialog" role="dialog" aria-modal="true" aria-labelledby="edit-link-title"><h2 id="edit-link-title">Edit link</h2><form className="create-form" onSubmit={saveEdit}><label>Title<input value={editTitle} onChange={event => setEditTitle(event.target.value)} maxLength={255} /></label><label>Destination URL<input type="url" value={editUrl} onChange={event => setEditUrl(event.target.value)} required /></label><div className="dialog-actions"><button type="button" className="secondary" onClick={() => setEditTarget(null)}>Cancel</button><button type="submit">Save changes</button></div></form></section></div>}
    <section className="toolbar card link-org-toolbar"><div className="organization-picker"><label>Organization<select value={org} onChange={e => { selectOrganization(e.target.value); setLinks([]); setHasMore(false); setError(""); }}><option value="">Select an organization</option>{orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>{selectedOrg && <div className="organization-context"><strong>{selectedOrg.name}</strong><span>Organization ID</span><code>{selectedOrg.id}</code></div>}</div></section>
    {error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}
    {message && <WorkspaceFeedback kind="success" message={message} onDismiss={() => setMessage("")} />}
    {!org && <section className="card empty-state"><h2>Select an organization</h2><p className="muted">Choose an organization above to view and manage its links.</p></section>}
    <nav className="link-page-tabs" aria-label="Link management">
      <NavLink to="/workspace/links" end>Manage links</NavLink>
      <NavLink to="/workspace/links/create">Create link</NavLink>
      <NavLink to="/workspace/links/import">Import CSV</NavLink>
    </nav>
    {page === "create" && <section className="card link-create-page">
      <p className="eyebrow">NEW LINK</p><h2>Create a link</h2>
      <p className="muted">Enter a destination, then optionally customize how this link behaves.</p>
      <form className="link-create-form" onSubmit={create}>
        <label className="link-destination-field">Destination URL<input type="url" placeholder="https://example.com/page" value={target} onChange={e => setTarget(e.target.value)} required /></label>
        <div className="link-create-options">
          <label>Title<input placeholder="e.g. Spring campaign" value={title} onChange={e => setTitle(e.target.value)} /></label>
          <label>Custom alias<input placeholder="e.g. spring-sale" value={alias} onChange={e => setAlias(e.target.value)} /></label>
          <label>Expiration date<input type="datetime-local" value={expires} onChange={e => setExpires(e.target.value)} /></label>
          <label>Click limit<input type="number" min="1" placeholder="No limit" value={clickLimit} onChange={e => setClickLimit(e.target.value)} /></label>
          <label>Password protection<input type="password" placeholder="Optional password" value={password} onChange={e => setPassword(e.target.value)} /></label>
        </div>
        <div className="link-access-options">
          <label className="checkbox"><input type="checkbox" checked={oneTime} onChange={e => setOneTime(e.target.checked)} /> One-time link</label>
          <label className="checkbox"><input type="checkbox" checked={privateLink} onChange={e => setPrivateLink(e.target.checked)} /> Organization members only</label>
        </div>
        <button type="submit" disabled={!org}>Create link</button>
      </form>
    </section>}
    {page === "import" && <section className="link-import-page">
      <header className="link-import-heading"><p className="eyebrow">BULK CREATE</p><h2>Import links from CSV</h2><p className="muted">Paste rows or choose a CSV file. The file must include an <code>original_url</code> column. Up to 1,000 links can be imported at a time.</p></header>
      <section className="card link-import-method"><h3>Paste CSV or URLs</h3><p className="muted">Paste CSV with an <code>original_url</code> header, or paste one URL per line.</p><form onSubmit={importCsv}><label className="link-csv-textarea-label" htmlFor="pasted-link-csv">CSV content</label><textarea id="pasted-link-csv" placeholder={"original_url,title\nhttps://example.com,Example link"} value={csv} onChange={e => setCsv(e.target.value)} /><button disabled={!org}>Import pasted links</button></form></section>
      <section className="card link-import-method"><h3>Upload a CSV file</h3><p className="muted">Select a .csv file from your device. Maximum file size is 5 MB.</p><form className="link-file-upload" onSubmit={upload}><label className="link-file-picker"><span className="link-file-icon" aria-hidden="true">↑</span><strong>{file?.name ?? "Choose a CSV file"}</strong><span>{file ? `${(file.size / 1024).toFixed(1)} KB selected` : "CSV format · up to 5 MB"}</span><input type="file" accept=".csv,text/csv" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label><button disabled={!org || !file}>Upload and import</button></form></section>
    </section>}
    {page === "manage" && <section className="card link-catalog-panel"><div className="section-heading"><div><p className="eyebrow">LINK LIBRARY</p><h2>Your links</h2><span>{links.length ? `${links.length} loaded` : "Load links for this organization"}</span></div><div className="link-catalog-actions">{selected.length > 0 && <button className="danger" onClick={() => setConfirmBulkDelete(true)}>Delete selected ({selected.length})</button>}<NavLink className="link-create-cta" to="/workspace/links/create">Create link</NavLink><NavLink className="link-import-cta" to="/workspace/links/import">Import CSV</NavLink></div></div><div className="link-catalog-toolbar"><div className="link-toolbar-actions"><button className="secondary" onClick={() => void load()} disabled={!org || loading}>{loading ? "Loading…" : "Load links"}</button><label className="checkbox"><input type="checkbox" checked={archived} onChange={e => { setArchived(e.target.checked); setLinks([]); }} /> Show archived</label></div><label className="search-field">Search links<input placeholder="Search by title, alias, or URL" value={search} onChange={e => setSearch(e.target.value)} /></label></div>{loading && !links.length ? <p className="muted">Loading links…</p> : !loading && !links.length && org ? <p className="muted">No links match the current filters.</p> : links.map(l => <article className="link-row" key={l.id}><div className="link-main"><label><input type="checkbox" checked={selected.includes(l.id)} onChange={e => setSelected(s => e.target.checked ? [...s, l.id] : s.filter(id => id !== l.id))} /><strong>{l.title || l.short_code}</strong></label><span className="link-destination" title={l.original_url}>{l.original_url}</span>    <span className="muted">{l.short_url || `/?link=${l.short_code}`}</span><span className="muted">{l.is_archived ? "Archived" : "Active"}{l.password_protected ? " · Protected" : ""}{l.is_private ? " · Private" : ""}</span></div><div className="link-actions"><button className="secondary" onClick={() => void openLink(l)}>Open</button><button className="secondary" onClick={() => void edit(l)}>Edit</button><button className="secondary" onClick={() => void toggle(l)}>{l.is_archived ? "Restore" : "Archive"}</button><button className="secondary" onClick={() => void duplicate(l)}>Duplicate</button><button className="secondary" onClick={() => void qr(l)}>QR</button><button className="secondary" onClick={() => void copy(l)}>Copy</button><button className="danger" onClick={() => setDeleteTarget(l)}>Delete</button></div></article>)}{hasMore && <div className="load-more"><button className="secondary" onClick={() => void load(true)} disabled={loading}>{loading ? "Loading…" : "Load more links"}</button></div>}</section>}
  </WorkspaceLayout>;
}
