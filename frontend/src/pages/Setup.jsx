import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api from "../utils/api";

const steps = ["Welcome", "Admin", "Install", "Site", "Done"];

export default function Setup() {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    admin_email: "",
    admin_password: "",
    admin_password_confirm: "",
    public_url: window.location.origin || "",
    snippet_mode: "",
    site_domain: "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  });
  const [probe, setProbe] = useState({ status: "idle", reachable: null, mode: null });
  const [trackerSnippet, setTrackerSnippet] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.get("/setup/status").then(({ data }) => {
      if (data.setup_complete) navigate("/login");
    });
  }, []);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function runProbe() {
    setError("");
    setProbe({ status: "probing", reachable: null, mode: null });
    try {
      const { data } = await api.post("/setup/probe", { public_url: form.public_url });
      update("public_url", data.public_url);
      update("snippet_mode", data.snippet_mode || "");
      setProbe({ status: "done", reachable: data.reachable, mode: data.snippet_mode });
    } catch (e) {
      setProbe({ status: "done", reachable: false, mode: null });
      setError(e.response?.data?.detail || "Could not reach that URL");
    }
  }

  async function submit() {
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/setup/initialize", {
        admin_email: form.admin_email,
        admin_password: form.admin_password,
        site_name: form.site_domain,
        site_domain: form.site_domain,
        public_url: form.public_url,
        snippet_mode: form.snippet_mode,
        timezone: form.timezone,
      });
      setTrackerSnippet(data.tracker_snippet);
      setStep(4);
    } catch (e) {
      setError(e.response?.data?.detail || "Setup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                  i < step ? "bg-success text-white" : i === step ? "bg-accent text-white" : "bg-surface-600 text-slate-500"
                }`}
              >
                {i < step ? "✓" : i + 1}
              </div>
              <span className={`text-xs ${i === step ? "text-white" : "text-slate-500"}`}>{s}</span>
              {i < steps.length - 1 && <div className="w-6 h-px bg-surface-500" />}
            </div>
          ))}
        </div>

        <div className="bg-surface-800 border border-surface-600 rounded-xl p-6 glow">
          {/* Step 0: Welcome */}
          {step === 0 && (
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2 h-2 rounded-full bg-accent pulse-dot" />
                  <span className="text-xs font-mono text-slate-400 uppercase tracking-widest">Higashi Analytics</span>
                </div>
                <h2 className="text-xl font-semibold text-white">Welcome</h2>
                <p className="text-sm text-slate-400 mt-2">
                  Three quick steps. Takes about a minute.
                </p>
              </div>
              <ul className="text-sm text-slate-400 space-y-1.5 mt-2">
                <li className="flex gap-2"><span className="text-accent">→</span> Create your admin account</li>
                <li className="flex gap-2"><span className="text-accent">→</span> Tell us where this install lives</li>
                <li className="flex gap-2"><span className="text-accent">→</span> Add the first site to track</li>
              </ul>
              <button onClick={() => setStep(1)} className="w-full bg-accent hover:bg-accent-dim text-white font-medium py-2.5 rounded-lg transition-colors text-sm mt-2">
                Get started →
              </button>
            </div>
          )}

          {/* Step 1: Admin account */}
          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white">Admin Account</h2>
              {error && <p className="text-danger text-xs bg-danger/10 border border-danger/20 rounded-lg px-3 py-2">{error}</p>}
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Email</label>
                <input type="email" value={form.admin_email} onChange={(e) => update("admin_email", e.target.value)}
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-accent"
                  placeholder="you@yourdomain.com" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Password</label>
                <input type="password" autoComplete="new-password" value={form.admin_password} onChange={(e) => update("admin_password", e.target.value)}
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-accent"
                  placeholder="••••••••" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Confirm Password</label>
                <input type="password" autoComplete="new-password" value={form.admin_password_confirm} onChange={(e) => update("admin_password_confirm", e.target.value)}
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-accent"
                  placeholder="••••••••" />
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={() => setStep(0)} className="flex-1 bg-surface-600 hover:bg-surface-500 text-slate-300 font-medium py-2.5 rounded-lg text-sm transition-colors">Back</button>
                <button onClick={() => {
                    if (!form.admin_email || !form.admin_password) { setError("Email and password are required"); return; }
                    if (form.admin_password !== form.admin_password_confirm) { setError("Passwords do not match"); return; }
                    setError(""); setStep(2);
                  }}
                  className="flex-1 bg-accent hover:bg-accent-dim text-white font-medium py-2.5 rounded-lg text-sm transition-colors">Next →</button>
              </div>
            </div>
          )}

          {/* Step 2: Public URL of this install (the one field that powers every snippet) */}
          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white">Where does this install live?</h2>
              <p className="text-xs text-slate-400">
                The public URL of <em>this</em> Higashi instance. Every tracker snippet uses it, so the sites you track
                know where to send data.
              </p>
              {error && <p className="text-danger text-xs bg-danger/10 border border-danger/20 rounded-lg px-3 py-2">{error}</p>}
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Public URL</label>
                <input type="text" value={form.public_url} onChange={(e) => { update("public_url", e.target.value); setProbe({ status: "idle", reachable: null, mode: null }); }}
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-accent"
                  placeholder="https://analytics.yourdomain.com" />
              </div>

              {probe.status === "done" && probe.reachable && (
                <div className="text-xs text-success bg-success/10 border border-success/20 rounded-lg px-3 py-2">
                  ✓ Reachable. Using <span className="font-mono">{probe.mode === "php" ? "PHP proxy" : "clean URLs"}</span>.
                </div>
              )}
              {probe.status === "done" && !probe.reachable && (
                <div className="text-xs text-warning bg-warning/10 border border-warning/20 rounded-lg px-3 py-2">
                  Couldn't reach that URL yet. You can continue — snippets will still embed it, but make sure DNS/proxying
                  is set before you paste them.
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button onClick={() => setStep(1)} className="flex-1 bg-surface-600 hover:bg-surface-500 text-slate-300 font-medium py-2.5 rounded-lg text-sm transition-colors">Back</button>
                <button onClick={runProbe} disabled={!form.public_url || probe.status === "probing"}
                  className="flex-1 bg-surface-600 hover:bg-surface-500 disabled:opacity-50 text-slate-300 font-medium py-2.5 rounded-lg text-sm transition-colors">
                  {probe.status === "probing" ? "Testing..." : "Test connection"}
                </button>
                <button onClick={() => { if (!form.public_url) { setError("Public URL is required"); return; } setError(""); setStep(3); }}
                  className="flex-1 bg-accent hover:bg-accent-dim text-white font-medium py-2.5 rounded-lg text-sm transition-colors">Next →</button>
              </div>
            </div>
          )}

          {/* Step 3: First site */}
          {step === 3 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white">Your First Site</h2>
              <p className="text-xs text-slate-400">The domain you want to track. You can add more later.</p>
              {error && <p className="text-danger text-xs bg-danger/10 border border-danger/20 rounded-lg px-3 py-2">{error}</p>}
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Domain</label>
                <input type="text" value={form.site_domain} onChange={(e) => update("site_domain", e.target.value)}
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-accent"
                  placeholder="yourdomain.com" />
              </div>
              <div className="flex gap-3 pt-2">
                <button onClick={() => setStep(2)} className="flex-1 bg-surface-600 hover:bg-surface-500 text-slate-300 font-medium py-2.5 rounded-lg text-sm transition-colors">Back</button>
                <button onClick={() => { if (!form.site_domain) { setError("Domain is required"); return; } submit(); }} disabled={loading}
                  className="flex-1 bg-accent hover:bg-accent-dim disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
                  {loading ? "Setting up..." : "Complete setup →"}
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Done */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-success text-xl">✓</span>
                <h2 className="text-lg font-semibold text-white">Setup complete</h2>
              </div>
              <p className="text-sm text-slate-400">Add this snippet to the <code className="font-mono text-xs bg-surface-600 px-1 py-0.5 rounded">&lt;head&gt;</code> of every page you want to track:</p>
              <pre className="bg-surface-700 border border-surface-500 rounded-lg p-3 text-xs font-mono text-accent-glow overflow-x-auto whitespace-pre-wrap break-all">
                {trackerSnippet}
              </pre>
              <button onClick={() => navigate("/login")}
                className="w-full bg-accent hover:bg-accent-dim text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
                Go to dashboard →
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
