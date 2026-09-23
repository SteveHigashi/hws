import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "../hooks/useAuth";
import { passkeysSupported, signInWithPasskey } from "../utils/webauthn";

export default function Login() {
  const savedEmail =
    useAuthStore((s) => s.email) ||
    localStorage.getItem("ha-login-email") ||
    "";
  const [email, setEmail] = useState(savedEmail);
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const completeSignIn = useAuthStore((s) => s.completeSignIn);
  const [passkeyBusy, setPasskeyBusy] = useState(false);
  const token = useAuthStore((s) => s.token);
  const navigate = useNavigate();

  useEffect(() => {
    if (token) navigate("/dashboard", { replace: true });
  }, [token, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password, { remember });
      navigate("/dashboard");
    } catch (err) {
      const status = err?.response?.status;
      if (!status) {
        setError("Cannot reach the backend — is it running?");
      } else if (status === 401) {
        setError("Invalid email or password");
      } else {
        setError(`Login failed (${status})`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-accent pulse-dot" />
            <span className="text-xs text-slate-400 uppercase tracking-widest font-mono">Higashi Analytics</span>
          </div>
          <h1 className="text-2xl font-semibold text-white">Sign in</h1>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface-800 border border-surface-600 rounded-xl p-6 glow space-y-4">
          {error && (
            <p className="text-danger text-sm bg-danger/10 border border-danger/20 rounded-lg px-3 py-2">{error}</p>
          )}
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
              placeholder="admin@yourdomain.com"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
              placeholder="••••••••"
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 rounded border-surface-500 bg-surface-700 text-accent focus:ring-accent"
            />
            Remember this computer
          </label>
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-accent hover:bg-accent-dim disabled:opacity-50 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
          <p className="text-center text-xs">
            <Link to="/forgot" className="text-slate-500 hover:text-slate-300 underline">Forgot your password?</Link>
          </p>
        </form>

        {passkeysSupported() && (
          <div className="mt-4 text-center">
            <button
              type="button"
              disabled={passkeyBusy}
              onClick={async () => {
                setError("");
                setPasskeyBusy(true);
                try {
                  const data = await signInWithPasskey(email);
                  completeSignIn(data, email, { remember });
                  navigate("/dashboard", { replace: true });
                } catch (err) {
                  // A cancelled prompt is not a failure worth shouting about.
                  if (err?.name !== "NotAllowedError" && err?.name !== "AbortError") {
                    setError(err.response?.data?.detail || "That passkey was not accepted");
                  }
                } finally {
                  setPasskeyBusy(false);
                }
              }}
              className="w-full border border-surface-600 hover:border-surface-500 text-slate-300 text-sm py-2.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {passkeyBusy ? "Waiting for your passkey…" : "Sign in with a passkey"}
            </button>
            <p className="text-xs text-slate-600 mt-2">Add one from Account once you are signed in.</p>
          </div>
        )}
      </div>
    </div>
  );
}
