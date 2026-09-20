import { FormEvent, useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { apiBaseUrl } from "../../../shared/api/client";
import { useSession } from "../../../shared/session/SessionProvider";
import { describeSharedLinkFailure } from "../access";

export function SharedLinkPage() {
  const { code: routeCode } = useParams(); const location = useLocation(); const code = routeCode ?? new URLSearchParams(location.search).get("link") ?? ""; const navigate = useNavigate(); const { tokens } = useSession();
  const [password, setPassword] = useState(""), [error, setError] = useState(""), [loading, setLoading] = useState(false);
  const open = useCallback(async (event?: FormEvent, supplied?: string) => {
    event?.preventDefault(); if (!code) return; setLoading(true); setError("");
    const secret = supplied ?? password; const query = secret ? `?password=${encodeURIComponent(secret)}` : "";
    const headers: HeadersInit = tokens?.accessToken ? { Authorization: `Bearer ${tokens.accessToken}` } : {};
    const r = await fetch(`${apiBaseUrl}/urls/resolve/${encodeURIComponent(code)}${query}`, { headers });
    if (r.ok) { const body = await r.json(); window.location.assign(body.original_url); return; }
    const body = await r.json().catch(() => ({})) as {
      detail?: string;
      error?: { message?: string };
    };
    const detail = body.detail ?? body.error?.message ?? "";
    setError(describeSharedLinkFailure(r.status, detail).message); setLoading(false);
  }, [code, tokens?.accessToken]);
  useEffect(() => { void open(undefined, ""); }, [open]);
  const requiresPassword = error.toLowerCase().includes("password");
  const requiresAuthentication = error.toLowerCase().includes("sign in")
    || error.toLowerCase().includes("authentication");
  return <main className="centered"><section className="card auth-card shared-link-page"><p className="eyebrow">LINKHUB SHARED LINK</p><h1>Open shared link</h1><p className="muted">Link code: <strong>{code}</strong></p>{error && <p className="notice">{error}</p>}{requiresAuthentication && <button className="secondary" onClick={() => navigate(`/auth?returnTo=/shared/${encodeURIComponent(code ?? "")}`)}>Sign in to retry</button>}{requiresPassword && <form onSubmit={(event) => open(event, password)}><input autoFocus type="password" placeholder="Enter link password" value={password} onChange={e=>setPassword(e.target.value)} required /><button disabled={loading}>{loading ? "Checking access…" : "Open with password"}</button></form>}{!requiresPassword && !requiresAuthentication && <button onClick={() => void open(undefined, "")} disabled={loading}>{loading ? "Checking access…" : "Open shared link"}</button>}</section></main>;
}
