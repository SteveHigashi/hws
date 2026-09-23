import { useEffect, useState } from "react";
import api from "../utils/api";
import { useAuthStore } from "../hooks/useAuth";
import { passkeysSupported, registerPasskey } from "../utils/webauthn";

function timeAgo(iso) {
  if (!iso) return "never";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (diff <= 0) return "today";
  return `${diff}d ago`;
}

// Passkeys are an addition, never a replacement: the password keeps working, so
// losing a device never locks anyone out of their own install.
export default function Account() {
  const email = useAuthStore((s) => s.email);
  const [keys, setKeys] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = () => api.get("/auth/passkeys").then(({ data }) => setKeys(data)).catch(() => setKeys([]));
  useEffect(() => { load(); }, []);

  const add = async () => {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      await registerPasskey(navigator.platform || "This device");
      setMessage("Passkey added. You can now sign in with it.");
      load();
    } catch (err) {
      if (err?.name !== "NotAllowedError" && err?.name !== "AbortError") {
        setError(err.response?.data?.detail || "The passkey could not be added");
      }
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this passkey? Your password still works.")) return;
    await api.delete(`/auth/passkeys/${id}`);
    load();
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-white">Account</h1>
        <p className="text-sm text-slate-500 mt-1">{email}</p>
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 space-y-4">
        <div>
          <p className="text-sm font-medium text-slate-300">Passkeys</p>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            Sign in with your device instead of typing a password — Touch ID, Windows Hello, a phone or a
            security key. Your password keeps working, so a lost device never locks you out.
          </p>
        </div>

        {message && <p className="text-xs text-green-400">{message}</p>}
        {error && <p className="text-xs text-danger">{error}</p>}

        {keys.length > 0 && (
          <ul className="divide-y divide-surface-600 border border-surface-600 rounded-lg">
            {keys.map((k) => (
              <li key={k.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                <span className="text-slate-200">{k.name || "Passkey"}</span>
                <span className="text-xs text-slate-500">added {timeAgo(k.created_at)} · used {timeAgo(k.last_used_at)}</span>
                <button onClick={() => remove(k.id)} className="ml-auto text-xs text-slate-600 hover:text-danger">Remove</button>
              </li>
            ))}
          </ul>
        )}

        {passkeysSupported() ? (
          <button
            onClick={add}
            disabled={busy}
            className="bg-accent hover:bg-accent-dim disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {busy ? "Waiting for your device…" : keys.length ? "Add another passkey" : "Add a passkey"}
          </button>
        ) : (
          <p className="text-xs text-slate-500">This browser cannot use passkeys.</p>
        )}
      </div>

      <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 space-y-2">
        <p className="text-sm font-medium text-slate-300">Password</p>
        <p className="text-xs text-slate-500 leading-relaxed">
          To change it, sign out and use <span className="text-slate-400">Forgot your password?</span>, or run{" "}
          <code className="text-slate-400">manage_users.py set-password</code> on the server this Higashi runs on.
        </p>
      </div>
    </div>
  );
}
