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

  // Research sharing lives HERE rather than beside the Live card on purpose: it
  // is not Higashi Live, it needs no Live key, and nothing about buying or
  // configuring Live may switch it on.
  const [research, setResearch] = useState(null);
  const [researchBusy, setResearchBusy] = useState(false);

  const load = () => api.get("/auth/passkeys").then(({ data }) => setKeys(data)).catch(() => setKeys([]));
  useEffect(() => { load(); }, []);
  useEffect(() => {
    api.get("/admin/settings/research").then(({ data }) => setResearch(data)).catch(() => setResearch(null));
  }, []);

  const toggleResearch = async (enabled) => {
    setResearchBusy(true);
    setError("");
    setMessage("");
    try {
      await api.post("/admin/settings/research", { enabled });
      setResearch((r) => ({ ...r, enabled }));
      setMessage(enabled
        ? "Thank you — aggregate figures will be shared from the next run."
        : "Sharing is off. Nothing further will be sent.");
    } catch (err) {
      setError(err.response?.data?.detail || "The setting could not be saved");
    } finally {
      setResearchBusy(false);
    }
  };

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

      {research && (
        <div className="bg-surface-800 border border-surface-600 rounded-xl p-5 space-y-4">
          <div>
            <p className="text-sm font-medium text-slate-300">Help improve Higashi (optional)</p>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              You can choose to share the aggregate figures Higashi has already worked out for your own
              dashboard. They may be used to improve Higashi and Higashi Live, improve crawler detection,
              study trends across sites, and produce aggregate industry research, reports and white papers.
            </p>
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              This is not Higashi Live and needs no Live key. It is off until you turn it on, and turning it
              off stops anything further being sent.
            </p>
          </div>

          <div>
            <p className="text-xs font-medium text-slate-400">What is shared</p>
            <ul className="text-xs text-slate-500 mt-1 space-y-1 list-disc list-inside leading-relaxed">
              {(research.what_is_shared || []).map((item) => (<li key={item}>{item}</li>))}
            </ul>
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">{research.never_shared}</p>
          </div>

          <div className="flex items-center justify-between pt-1">
            <p className="text-sm text-slate-300">
              {research.enabled ? "Sharing is on." : "Sharing is off."}
            </p>
            <button
              type="button"
              disabled={researchBusy}
              onClick={() => toggleResearch(!research.enabled)}
              className={`px-3 py-1.5 rounded-lg text-sm border transition ${
                research.enabled
                  ? "border-surface-600 text-slate-300 hover:bg-surface-700"
                  : "border-accent text-accent hover:bg-accent hover:text-white"
              } disabled:opacity-50`}
            >
              {researchBusy ? "Saving…" : research.enabled ? "Turn off sharing" : "Share aggregate figures"}
            </button>
          </div>
        </div>
      )}

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
