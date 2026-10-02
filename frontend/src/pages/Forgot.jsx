import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../utils/api";

// Higashi cannot assume the install can send mail, so a reset is something the
// person who runs the server creates. The page says exactly what to run.
export default function Forgot() {
  const [email, setEmail] = useState("");
  const [mode, setMode] = useState(null);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const { data } = await api.post("/auth/forgot", { email });
      setMode(data.mode || "server");
    } catch (err) {
      setError(err.response?.data?.detail || "Could not reach the server");
    }
  };

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-white">Reset your password</h1>
        </div>
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-6 glow space-y-4 text-sm text-slate-300">
          {mode === null ? (
            <form onSubmit={submit} className="space-y-4">
              {error && <p className="text-danger text-sm">{error}</p>}
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Your email</label>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-accent" />
              </div>
              <button type="submit" className="w-full bg-accent hover:bg-accent-dim text-white font-medium py-2.5 rounded-lg text-sm">Continue</button>
            </form>
          ) : mode === "mail" ? (
            <p>If that address has an account, a reset link is on its way. It works once, for 30 minutes.</p>
          ) : (
            <>
              <p>This Higashi does not send email, so the reset comes from the server it runs on. Whoever runs it (that may be you) opens a terminal there and runs:</p>
              <pre className="bg-surface-900 border border-surface-600 rounded-lg p-3 text-xs text-slate-200 overflow-x-auto">python manage_users.py reset-link {email || "you@example.com"}</pre>
              <p>It prints a link that works once, for 30 minutes. Open it here and choose a new password. If you would rather type the password on the server, run <code className="text-slate-200">manage_users.py set-password</code> instead.</p>
              <p className="text-xs text-slate-500">On the hosted reference install the command is prefixed with <code>sudo -u higashi HIGASHI_ENV_PATH=/etc/higashi/higashi.env /opt/higashi/.venv/bin/python</code> from <code>/opt/higashi/backend</code>.</p>
            </>
          )}
          <p className="text-center text-xs"><Link to="/login" className="text-slate-300 hover:text-white underline underline-offset-2">Back to sign in</Link></p>
        </div>
      </div>
    </div>
  );
}
