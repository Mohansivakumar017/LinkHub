import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { WorkspaceLayout } from "../../workspace/WorkspaceLayout";

export function SettingsPage() {
  const { api, clear } = useSession();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState("");

  async function change(event: FormEvent) {
    event.preventDefault();
    const response = await api.request(`${apiBaseUrl}/users/me/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: current, new_password: next }),
    });
    if (!response.ok) {
      setMessage("Could not change password");
      return;
    }
    clear();
    navigate("/auth");
  }

  return (
    <WorkspaceLayout
      title="Settings & security"
      description="Manage password security. Changing your password signs you out."
      message={message}
    >
      <section className="settings-grid">
        <article className="card">
          <h2>Change password</h2>
          <form className="create-form" onSubmit={change}>
            <input
              type="password"
              placeholder="Current password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              required
            />
            <input
              type="password"
              minLength={8}
              placeholder="New password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              required
            />
            <button type="submit">Change password</button>
          </form>
        </article>
      </section>
    </WorkspaceLayout>
  );
}
