import { FormEvent, useEffect, useState } from "react";
import { apiBaseUrl } from "../../../shared/api/client";
import { readApiErrorMessage } from "../../../shared/api/errors";
import { WorkspaceFeedback } from "../../../shared/components/WorkspaceFeedback";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";

type Profile = {
  email: string;
  full_name?: string | null;
  avatar_url?: string | null;
  is_email_verified: boolean;
};

export function ProfilePage() {
  const { api } = useSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    void api.request(`${apiBaseUrl}/users/me`).then(async response => {
      if (response.ok) {
        const result = await response.json() as Profile;
        setProfile(result);
        setName(result.full_name ?? "");
      } else {
        setError(await readApiErrorMessage(response, "Could not load profile."));
      }
      setLoading(false);
    });
  }, [api]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSaving(true);
    const response = await api.request(`${apiBaseUrl}/users/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name: name }),
    });
    if (response.ok) {
      setProfile(current => current ? { ...current, full_name: name } : current);
      setMessage("Profile updated.");
    } else {
      setError(await readApiErrorMessage(response, "Could not update profile."));
    }
    setSaving(false);
  }

  async function uploadAvatar(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!file) {
      setError("Choose an image before uploading your avatar.");
      return;
    }
    setUploading(true);
    const body = new FormData();
    body.append("file", file);
    const response = await api.request(`${apiBaseUrl}/users/me/avatar`, {
      method: "POST",
      body,
    });
    if (response.ok) {
      const result = await response.json() as { avatar_url: string };
      setProfile(current => current ? { ...current, avatar_url: result.avatar_url } : current);
      setFile(null);
      setMessage("Avatar uploaded.");
    } else {
      setError(await readApiErrorMessage(response, "Could not upload avatar."));
    }
    setUploading(false);
  }

  const mediaBaseUrl = apiBaseUrl.replace(/\/api\/v1$/, "");

  return (
    <WorkspaceLayout
      title="Profile"
      description="Manage your personal identity, name, avatar, and verification status."
      message={message}
    >
      {error && <WorkspaceFeedback kind="error" message={error} onDismiss={() => setError("")} />}
      {loading ? <section className="card"><p className="muted">Loading profile…</p></section> : (
        <section className="settings-grid">
          <article className="card">
            <h2>Personal details</h2>
            <form onSubmit={save} className="create-form">
              <label>Full name<input value={name} onChange={event => setName(event.target.value)} required maxLength={255} /></label>
              <label>Email address<input value={profile?.email ?? ""} readOnly /></label>
              <button disabled={saving}>{saving ? "Saving…" : "Save profile"}</button>
            </form>
            <p className="muted">Email {profile?.is_email_verified ? "verified" : "not verified"}.</p>
          </article>
          <article className="card">
            <h2>Avatar</h2>
            {profile?.avatar_url && (
              <img
                className="profile-avatar-preview"
                src={`${mediaBaseUrl}${profile.avatar_url}`}
                alt="Current avatar"
              />
            )}
            <form onSubmit={uploadAvatar} className="create-form">
              <label>Choose an image<input type="file" accept="image/png,image/jpeg,image/webp" onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
              {file && <p className="muted" role="status">{file.name} · {(file.size / 1024).toFixed(1)} KB</p>}
              <button disabled={!file || uploading}>{uploading ? "Uploading…" : "Upload avatar"}</button>
            </form>
          </article>
        </section>
      )}
    </WorkspaceLayout>
  );
}
