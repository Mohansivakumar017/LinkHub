import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";

type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
  usage_count?: number;
  revoked_at?: string | null;
  organization_id?: string | null;
};
type Organization = { id: string; name: string };

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "Never";
}

export function ApiKeysPage() {
  const { api } = useSession();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmation, setConfirmation] = useState<{ item: ApiKey; action: "rotate" | "revoke" } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");

  async function load() {
    setLoading(true);
    const response = await api.request(`${apiBaseUrl}/api-keys`);
    if (response.ok) {
      setKeys(await response.json());
      setError("");
    } else {
      setError(await readApiErrorMessage(response, "Could not load API keys."));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    void api.request(`${apiBaseUrl}/organizations`).then(async response => {
      if (response.ok) setOrganizations(await response.json() as Organization[]);
      else setError(await readApiErrorMessage(response, "Could not load organizations for API key scope."));
    });
  }, []);

  async function create(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setMessage("");
    setError("");
    const response = await api.request(`${apiBaseUrl}/api-keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), organization_id: organizationId || null }),
    });
    if (response.ok) {
      const created = await response.json() as { key: string };
      setNewKey(created.key);
      setName("");
      setMessage("API key created. This secret is shown only once.");
      await load();
    } else {
      setError(await readApiErrorMessage(response, "Could not create API key."));
    }
    setSubmitting(false);
  }

  async function rotate(item: ApiKey) {
    if (!item.is_active) return false;
    setError("");
    setMessage("");
    const response = await api.request(`${apiBaseUrl}/api-keys/${item.id}/rotate`, { method: "POST" });
    if (response.ok) {
      const replacement = await response.json() as { key: string };
      setNewKey(replacement.key);
      setMessage("API key rotated. Update your integration with the new secret.");
      await load();
      return true;
    } else {
      setError(await readApiErrorMessage(response, "Could not rotate API key."));
      return false;
    }
  }

  async function revoke(item: ApiKey) {
    if (!item.is_active) return false;
    setError("");
    setMessage("");
    const response = await api.request(`${apiBaseUrl}/api-keys/${item.id}`, { method: "DELETE" });
    if (response.ok) {
      setMessage("API key revoked. Requests using it will now be rejected.");
      await load();
      return true;
    } else {
      setError(await readApiErrorMessage(response, "Could not revoke API key."));
      return false;
    }
  }

  async function confirmAction() {
    if (!confirmation) return;
    setConfirming(true);
    const completed = confirmation.action === "rotate"
      ? await rotate(confirmation.item)
      : await revoke(confirmation.item);
    setConfirming(false);
    if (completed) setConfirmation(null);
  }

  async function copyKey() {
    setError("");
    setMessage("");
    try {
      await navigator.clipboard.writeText(newKey);
      setMessage("API key copied. Store it in your secret manager; it will not be shown again.");
    } catch {
      setError("Could not copy the API key. Check browser clipboard permissions and try again.");
    }
  }

  return (
    <WorkspaceLayout title="API keys" description="Create credentials for trusted integrations and revoke them immediately when access changes." message={message}>
      {confirmation && <ConfirmDialog title={confirmation.action === "rotate" ? "Rotate API key?" : "Revoke API key?"} message={confirmation.action === "rotate" ? `The current key "${confirmation.item.name}" will stop working immediately.` : `The key "${confirmation.item.name}" cannot be restored after revocation.`} confirmLabel={confirmation.action === "rotate" ? "Rotate key" : "Revoke key"} danger={confirmation.action === "revoke"} busy={confirming} onCancel={() => setConfirmation(null)} onConfirm={() => void confirmAction()} />}
      <section className="card api-key-create">
        <div className="section-heading">
          <div><h2>Create an API key</h2><span>Use a separate key for each integration so access can be audited and revoked independently.</span></div>
        </div>
        <form className="api-key-form" onSubmit={create}>
          <label>Key name<input placeholder="e.g. Production sync" value={name} onChange={(event) => setName(event.target.value)} maxLength={128} required /></label>
          <label>Organization scope<select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}><option value="">Personal (all permitted resources)</option>{organizations.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
          <button type="submit" disabled={submitting}>{submitting ? "Creating…" : "Create API key"}</button>
        </form>
        {newKey && <div className="secret-output" role="status"><div className="api-key-output"><strong>Copy this secret now</strong><code>{newKey}</code></div><button type="button" className="secondary" onClick={() => void copyKey()}>Copy</button></div>}
        {error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}
      </section>

      <section className="card">
        <div className="section-heading"><div><h2>Your API keys</h2><span>Only the key prefix is retained for identification.</span></div><button type="button" className="secondary" onClick={() => void load()} disabled={loading}>Refresh</button></div>
        {loading ? <p className="muted">Loading API keys…</p> : keys.length === 0 ? <p className="muted">No API keys yet. Create one when an integration needs access.</p> : (
          <div className="api-key-list">
            {keys.map((item) => <article className={`api-key-row ${item.is_active ? "" : "is-revoked"}`} key={item.id}>
              <div className="api-key-details"><div className="api-key-title"><strong>{item.name}</strong><span className={`status-pill ${item.is_active ? "active" : "revoked"}`}>{item.is_active ? "Active" : "Revoked"}</span></div><code>{item.key_prefix}••••••••</code><small>{item.organization_id ? `Organization-scoped · ${organizations.find(org => org.id === item.organization_id)?.name ?? item.organization_id}` : "Personal scope"} · Created {formatDate(item.created_at)} · Last used {formatDate(item.last_used_at)} · {item.usage_count ?? 0} requests</small></div>
              <div className="link-actions"><button type="button" className="secondary" onClick={() => setConfirmation({ item, action: "rotate" })} disabled={!item.is_active}>Rotate</button><button type="button" className="danger" onClick={() => setConfirmation({ item, action: "revoke" })} disabled={!item.is_active}>Revoke</button></div>
            </article>)}
          </div>
        )}
      </section>

      <section className="card api-key-help"><h2>Using an API key</h2><p className="muted">Send the secret in the <code>X-API-Key</code> header. Never put it in a URL, browser code, or source repository.</p><pre><code>{`curl -H "X-API-Key: lhk_your_secret" \\\n  ${apiBaseUrl}/urls/api/organizations/{organization_id}`}</code></pre></section>
    </WorkspaceLayout>
  );
}
