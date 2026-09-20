import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiBaseUrl } from "../../shared/api/client";
import { useSession } from "../../shared/session/SessionProvider";

type AuthMode = "login" | "register" | "recover" | "reset" | "verify";

function responseMessage(body: unknown, fallback: string) {
  if (typeof body === "object" && body !== null) {
    const value = body as { detail?: string; error?: { message?: string } };
    return value.error?.message ?? value.detail ?? fallback;
  }
  return fallback;
}

export type WorkspaceView = "auth" | "shared";

export function WorkspaceApp() {
  const { setTokens } = useSession();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<AuthMode>("login");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isLogin = mode === "login";
  const isRegister = mode === "register";

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setMessage("");
    setError("");
    setShowPassword(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    setSubmitting(true);

    try {
      const headers = { "Content-Type": "application/json" };
      let response: Response;

      if (mode === "verify") {
        response = await fetch(`${apiBaseUrl}/auth/verify-email`, {
          method: "POST",
          headers,
          body: JSON.stringify({ token }),
        });
        if (response.ok) {
          setMessage("Your email is verified. You can sign in now.");
          changeMode("login");
        } else {
          setError(responseMessage(await response.json(), "That verification token is invalid or expired."));
        }
        return;
      }

      if (mode === "reset") {
        response = await fetch(`${apiBaseUrl}/auth/reset-password`, {
          method: "POST",
          headers,
          body: JSON.stringify({ token, new_password: password }),
        });
        if (response.ok) {
          setMessage("Password reset successfully. Sign in with your new password.");
          changeMode("login");
        } else {
          setError(responseMessage(await response.json(), "That reset token is invalid or expired."));
        }
        return;
      }

      if (mode === "recover") {
        response = await fetch(`${apiBaseUrl}/auth/forgot-password`, {
          method: "POST",
          headers,
          body: JSON.stringify({ email }),
        });
        if (response.ok) {
          setMessage("If an account exists for that email, a reset link has been sent.");
        } else {
          setError(responseMessage(await response.json(), "We could not request a reset link."));
        }
        return;
      }

      response = await fetch(`${apiBaseUrl}/auth/${mode}`, {
        method: "POST",
        headers,
        body: JSON.stringify({ email, password, full_name: fullName }),
      });
      const body = await response.json();
      if (!response.ok) {
        setError(response.status === 403 ? "Verify your email before signing in." : responseMessage(body, "We could not sign you in."));
        return;
      }

      if (isRegister) {
        setMessage("Account created. Check your email to verify it, then sign in.");
        changeMode("login");
        return;
      }

      localStorage.setItem("linkhub_access_token", body.access_token);
      localStorage.setItem("linkhub_refresh_token", body.refresh_token);
      setTokens({ accessToken: body.access_token, refreshToken: body.refresh_token });
      navigate(new URLSearchParams(window.location.search).get("returnTo") || "/workspace/links");
    } catch {
      setError("The service is unavailable right now. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function resendVerification() {
    setError("");
    const response = await fetch(`${apiBaseUrl}/auth/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setMessage(response.ok ? "Verification email sent." : "We could not resend the verification email.");
  }

  const title = isRegister ? "Create your workspace" : isLogin ? "Welcome back" : "Account recovery";
  const subtitle = isRegister
    ? "Start organizing, securing, and measuring every shared link."
    : isLogin
      ? "Sign in to manage your links and teams."
      : mode === "recover"
        ? "Enter your email and we will send recovery instructions."
        : "Use the token from your email to restore access.";

  return (
    <main className="auth-shell">
      <section className="auth-brand-panel">
        <div className="brand-mark">↗</div>
        <p className="eyebrow">LINKHUB</p>
        <h1>One workspace for every link.</h1>
        <p>Secure, share, and understand the links your organization relies on.</p>
        <div className="auth-proof">
          <span>✓</span>
          <div><strong>Built for teams</strong><small>Keep ownership, access, and analytics together.</small></div>
        </div>
        <div className="auth-proof">
          <span>✓</span>
          <div><strong>Secure by default</strong><small>Protect private links with organization access and passwords.</small></div>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h2>{title}</h2>
            <p className="muted">{subtitle}</p>
          </div>
          {(isLogin || isRegister) && (
            <div className="auth-mode-switch" aria-label="Authentication mode">
              <button type="button" className={isLogin ? "active" : ""} onClick={() => changeMode("login")}>Sign in</button>
              <button type="button" className={isRegister ? "active" : ""} onClick={() => changeMode("register")}>Create account</button>
            </div>
          )}
        </div>

        <form className="auth-form" onSubmit={submit}>
          {(mode === "verify" || mode === "reset") && (
            <label>Verification or reset token<input value={token} onChange={(event) => setToken(event.target.value)} required autoComplete="one-time-code" /></label>
          )}
          {mode !== "verify" && mode !== "reset" && (
            <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" placeholder="you@company.com" /></label>
          )}
          {isRegister && (
            <label>Full name<input value={fullName} onChange={(event) => setFullName(event.target.value)} required autoComplete="name" placeholder="Your name" /></label>
          )}
          {(isLogin || isRegister || mode === "reset") && (
            <label>Password
              <span className="password-field">
                <input type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete={isLogin ? "current-password" : "new-password"} placeholder="Enter your password" />
                <button type="button" className="password-toggle" onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? "Hide" : "Show"}</button>
              </span>
            </label>
          )}
          {error && <p className="auth-error" role="alert">{error}</p>}
          {message && <p className="auth-success" role="status">{message}</p>}
          <button className="auth-submit" type="submit" disabled={submitting}>{submitting ? "Please wait…" : mode === "register" ? "Create workspace" : mode === "recover" ? "Send recovery email" : mode === "reset" ? "Reset password" : mode === "verify" ? "Verify email" : "Sign in"}</button>
        </form>

        <div className="auth-links">
          {isLogin && <button type="button" className="text-button" onClick={() => changeMode("recover")}>Forgot password?</button>}
          {mode === "verify" && <button type="button" className="text-button" onClick={() => void resendVerification()}>Resend verification email</button>}
          {mode === "recover" && <button type="button" className="text-button" onClick={() => changeMode("reset")}>I have a reset token</button>}
          {!isLogin && <button type="button" className="text-button" onClick={() => changeMode("login")}>Back to sign in</button>}
          {isLogin && <button type="button" className="text-button" onClick={() => changeMode("verify")}>Verify email</button>}
        </div>
        <p className="auth-legal">By continuing, you agree to use LinkHub responsibly and keep your account secure.</p>
      </section>
    </main>
  );
}
