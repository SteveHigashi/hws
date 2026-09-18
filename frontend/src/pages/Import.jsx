import { useState, useEffect, useRef } from "react";
import api from "../utils/api";
import { useSiteStore } from "../store/siteStore";

// ---------------------------------------------------------------------------
// Small reusable pieces
// ---------------------------------------------------------------------------

function TabBar({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 bg-surface-700 rounded-xl p-1 w-fit">
      {tabs.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            active === t
              ? "bg-accent text-white"
              : "text-slate-400 hover:text-white"
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function Input({ ...props }) {
  return (
    <input
      {...props}
      className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-accent"
    />
  );
}

function Textarea({ ...props }) {
  return (
    <textarea
      {...props}
      className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-accent font-mono text-xs resize-y"
    />
  );
}

function SubmitButton({ loading, label, loadingLabel }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="px-6 py-2.5 bg-accent hover:bg-accent-dim disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
    >
      {loading ? loadingLabel : label}
    </button>
  );
}

function ResultBox({ result, error }) {
  if (error) {
    return (
      <div className="mt-4 p-4 bg-danger/10 border border-danger/30 rounded-xl text-sm text-danger">
        {error}
      </div>
    );
  }
  if (!result) return null;
  const fileResults = result.file_results || [];
  const rows = [
    { label: "Page Views Imported", value: result.page_views?.toLocaleString() ?? "—" },
    { label: "Sessions Created",    value: result.sessions?.toLocaleString()    ?? "—" },
    { label: "Bot Visits Stored",   value: result.bot_visits?.toLocaleString()  ?? "—" },
    { label: "Skipped Lines",       value: result.skipped?.toLocaleString()      ?? "—" },
    { label: "Parse Errors",        value: result.errors?.toLocaleString()       ?? "—" },
  ];
  const cursorTo = result.cursor_to ? new Date(result.cursor_to).toLocaleString() : null;
  return (
    <div className="mt-4 bg-surface-700 border border-surface-500 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-surface-500 flex items-center justify-between">
        <p className="text-xs text-success font-medium uppercase tracking-widest">Import complete</p>
        {cursorTo && <p className="text-xs text-slate-500">cursor: {cursorTo}</p>}
      </div>
      {fileResults.length > 0 && (
        <div className="divide-y divide-surface-600">
          {fileResults.map((f) => (
            <div key={f.name} className="flex items-center gap-3 px-4 py-2.5">
              <span className={`shrink-0 text-sm ${f.ok ? "text-success" : "text-danger"}`}>
                {f.ok ? "✓" : "✗"}
              </span>
              <p className="font-mono text-xs text-slate-300 truncate flex-1 min-w-0">{f.name}</p>
              <p className={`text-xs shrink-0 ${f.ok ? "text-slate-500" : "text-danger"}`}>
                {f.ok ? `${f.page_views.toLocaleString()} views` : f.msg}
              </p>
            </div>
          ))}
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4">
        {rows.map((r) => (
          <div key={r.label} className="bg-surface-800 rounded-lg p-3">
            <p className="text-xs text-slate-500 mb-1">{r.label}</p>
            <p className="text-lg font-mono text-white">{r.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Tracker Setup
// ---------------------------------------------------------------------------

function TrackerSetupTab({ trackerKey: keyProp }) {
  const [copied, setCopied] = useState(false);

  const trackerKey = keyProp || "";
  const snippet = trackerKey
    ? `<script src="/tracker.js" data-key="${trackerKey}" async></script>`
    : `<!-- Select a site from the sidebar to see your tracker snippet. -->`;

  function copy() {
    navigator.clipboard.writeText(snippet).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const scriptTag = snippet;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-base font-semibold text-white mb-1">Add Higashi to your site</h2>
        <p className="text-sm text-slate-400">
          Paste this snippet into the <code className="font-mono text-xs bg-surface-600 px-1 py-0.5 rounded">&lt;head&gt;</code> of every page you want to track.
          The tracker is lightweight (~2 kB) and fires no third-party requests.
        </p>
      </div>

      {/* Snippet box */}
      <div className="bg-surface-700 border border-surface-500 rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 border-b border-surface-500">
          <span className="text-xs font-mono text-slate-500 uppercase tracking-widest">tracker snippet</span>
          <button
            onClick={copy}
            className="text-xs px-3 py-1 rounded-md bg-surface-600 hover:bg-surface-500 text-slate-300 hover:text-white transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <pre className="p-4 text-xs font-mono text-accent-glow overflow-x-auto whitespace-pre-wrap break-all">
          {scriptTag}
        </pre>
      </div>

      {/* Alternative: npm */}
      <div className="bg-surface-800 border border-surface-600 rounded-xl p-4">
        <p className="text-xs text-slate-400 font-medium mb-2 uppercase tracking-widest">Via script tag (CDN / self-hosted)</p>
        <pre className="text-xs font-mono text-slate-300 overflow-x-auto">
          {`<script src="https://your-higashi-domain/tracker.js" data-key="${trackerKey || "YOUR_KEY"}" async></script>`}
        </pre>
      </div>

      {/* How it works */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-500">
        {[
          { title: "Page Views",   body: "Fires on every navigation, including SPA route changes." },
          { title: "Sessions",     body: "Grouped by 30-minute inactivity window, server-side." },
          { title: "No Cookies",   body: "Uses hashed IP + UA fingerprint — fully GDPR-friendly." },
        ].map((c) => (
          <div key={c.title} className="bg-surface-800 border border-surface-600 rounded-xl p-3">
            <p className="text-slate-300 font-medium mb-1">{c.title}</p>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab: Upload Log
// ---------------------------------------------------------------------------

function UploadLogTab({ defaultDomain }) {
  const [file, setFile]       = useState(null);
  const [domain, setDomain]   = useState(defaultDomain || "");
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState(null);
  const [error, setError]     = useState("");
  const dropRef               = useRef(null);
  const [dragging, setDragging] = useState(false);

  // keep domain in sync if parent resolves it later
  useEffect(() => {
    if (defaultDomain && !domain) setDomain(defaultDomain);
  }, [defaultDomain]);

  function handleDrop(e) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  async function submit(e) {
    e.preventDefault();
    if (!file)   return setError("Please select a log file.");
    if (!domain) return setError("Domain is required.");
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("domain", domain);
      const { data } = await api.post("/admin/import/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5 max-w-lg">
      {/* Drag-and-drop area */}
      <div
        ref={dropRef}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => dropRef.current?.querySelector("input")?.click()}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragging
            ? "border-accent bg-accent/5"
            : "border-surface-500 hover:border-accent/50 bg-surface-700"
        }`}
      >
        <input
          type="file"
          accept=".log,.gz,.txt,*"
          className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
          onChange={(e) => setFile(e.target.files[0])}
        />
        {file ? (
          <div>
            <p className="text-sm text-white font-medium">{file.name}</p>
            <p className="text-xs text-slate-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div>
            <p className="text-sm text-slate-400">Drag & drop your nginx access log here</p>
            <p className="text-xs text-slate-600 mt-1">or click to browse — .log, .txt, .gz accepted</p>
          </div>
        )}
      </div>

      <Field label="Site Domain">
        <Input
          type="text"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="yourdomain.com"
        />
      </Field>

      <div className="flex items-center gap-4">
        <SubmitButton loading={loading} label="Import Log" loadingLabel="Importing…" />
        {file && (
          <button
            type="button"
            onClick={() => { setFile(null); setResult(null); setError(""); }}
            className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      <ResultBox result={result} error={error} />
    </form>
  );
}

// ---------------------------------------------------------------------------
// Saved pull profiles — stored on the server, secrets encrypted there and
// never sent back to the browser.
// ---------------------------------------------------------------------------

const LEGACY_PROFILES_KEY = "ha-ssh-profiles";

// Earlier versions kept profiles (with passwords and private keys) in
// localStorage. Move any to the server once, then remove them from the browser.
async function migrateLegacyProfiles() {
  let legacy = [];
  try { legacy = JSON.parse(localStorage.getItem(LEGACY_PROFILES_KEY) || "[]"); }
  catch { legacy = []; }
  if (!Array.isArray(legacy) || legacy.length === 0) {
    try { localStorage.removeItem(LEGACY_PROFILES_KEY); } catch { /* private window */ }
    return;
  }
  let allSaved = true;
  for (const p of legacy) {
    let password = "";
    try { password = p.password ? atob(p.password) : ""; } catch { password = ""; }
    const auth_mode = p.authMode === "key" ? "key" : "password";
    try {
      await api.post("/admin/import/profiles", {
        label: p.label || p.domain || p.host,
        host: p.host, port: parseInt(p.port, 10) || 22, username: p.username,
        auth_mode,
        password: auth_mode === "password" ? password : undefined,
        private_key: auth_mode === "key" ? p.private_key : undefined,
        domain: p.domain || "",
        log_paths: p.log_paths || (p.log_path ? [p.log_path] : []),
      });
    } catch {
      allSaved = false;
    }
  }
  if (allSaved) {
    try { localStorage.removeItem(LEGACY_PROFILES_KEY); } catch { /* private window */ }
  }
}

function PullProfiles({ profiles, activeId, onLoad, onRemove }) {
  if (!profiles.length) return null;

  return (
    <div>
      <p className="text-xs text-slate-500 uppercase tracking-widest mb-2">Saved Pull Profiles</p>
      <div className="flex flex-wrap gap-2">
        {profiles.map((p) => (
          <div key={p.id} className={`flex items-center gap-1 bg-surface-700 border rounded-lg px-3 py-1.5 ${
            p.id === activeId ? "border-accent" : "border-surface-500"
          }`}>
            <button
              type="button"
              onClick={() => onLoad(p)}
              className="text-xs text-slate-300 hover:text-white transition-colors"
            >
              {p.label || p.domain || p.host}
            </button>
            <button
              type="button"
              onClick={() => onRemove(p.id)}
              className="text-slate-600 hover:text-danger transition-colors ml-1 text-xs leading-none"
              title="Remove"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Log file classifier — explains what each file type is for
// ---------------------------------------------------------------------------

function classifyLog(name) {
  if (/^static_/.test(name))
    return { tag: "Web traffic", recommended: true,  color: "text-success", desc: "Recommended — captures page views, visitors, referrers" };
  if (/^php-app/.test(name))
    return { tag: "PHP requests", recommended: false, color: "text-amber-400", desc: "Dynamic PHP page requests, includes form submissions" };
  if (/^backend_/.test(name))
    return { tag: "Backend",      recommended: false, color: "text-slate-400", desc: "Backend server traffic — includes API and admin calls" };
  if (name === "access.log")
    return { tag: "Access log",   recommended: true,  color: "text-success", desc: "Recommended — standard nginx access log" };
  return   { tag: "Access log",   recommended: false, color: "text-slate-400", desc: "Server access log" };
}

// ---------------------------------------------------------------------------
// Tab: SSH Pull
// ---------------------------------------------------------------------------

function SSHPullTab({ defaultDomain }) {
  const [form, setForm] = useState({
    host: "", port: "22", username: "", password: "", private_key: "",
    domain: defaultDomain || "",
  });
  const [authMode, setAuthMode]         = useState("password");
  const [discovering, setDiscovering]   = useState(false);
  const [discovered, setDiscovered]     = useState(null);
  const [discoverErr, setDiscoverErr]   = useState("");
  const [selectedPaths, setSelectedPaths] = useState(new Set());
  const [cursors, setCursors]           = useState({});  // log_path -> cursor obj
  const [loading, setLoading]           = useState(false);
  const [importProgress, setImportProgress] = useState(null);
  const [result, setResult]             = useState(null);
  const [importErr, setImportErr]       = useState("");
  const [saveLabel, setSaveLabel]       = useState("");
  const [showSave, setShowSave]         = useState(false);
  const [profiles, setProfiles]         = useState([]);
  const [profileId, setProfileId]       = useState(null);
  const activeProfile = profiles.find((p) => p.id === profileId) || null;

  async function refreshProfiles() {
    try {
      const { data } = await api.get("/admin/import/profiles");
      setProfiles(data);
    } catch { /* list stays as it was */ }
  }

  useEffect(() => {
    migrateLegacyProfiles().finally(refreshProfiles);
  }, []);

  useEffect(() => {
    if (defaultDomain && !form.domain) setForm((f) => ({ ...f, domain: defaultDomain }));
  }, [defaultDomain]);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
    // A saved login only ever goes to the server it was saved for.
    if (["host", "port", "username"].includes(field)) setProfileId(null);
    if (["host", "port", "username", "password", "private_key"].includes(field)) {
      setDiscovered(null);
      setSelectedPaths(new Set());
      setCursors({});
    }
  }

  function credentials() {
    if (profileId) {
      return {
        profile_id: profileId,
        ...(authMode === "password"
          ? (form.password ? { password: form.password } : {})
          : (form.private_key.trim() ? { private_key: form.private_key } : {})),
      };
    }
    return {
      host:     form.host,
      port:     parseInt(form.port, 10) || 22,
      username: form.username,
      ...(authMode === "password" ? { password: form.password } : { private_key: form.private_key }),
    };
  }

  function togglePath(path) {
    setSelectedPaths((prev) => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  }

  function loadProfile(p) {
    setForm({
      host:        p.host || "",
      port:        String(p.port || "22"),
      username:    p.username || "",
      password:    "",
      private_key: "",
      domain:      p.domain || "",
    });
    setAuthMode(p.auth_mode || "password");
    setProfileId(p.id);
    const saved = p.log_paths || (p.log_path ? [p.log_path] : []);
    setSelectedPaths(new Set(saved));
    setDiscovered(null);
    setDiscoverErr("");
    setResult(null);
    setImportErr("");
  }

  async function persistProfile() {
    const label = saveLabel.trim() || form.domain || form.host;
    if (!label) return;
    try {
      const { data } = await api.post("/admin/import/profiles", {
        label,
        host: form.host, port: parseInt(form.port, 10) || 22, username: form.username,
        auth_mode:   authMode,
        password:    authMode === "password" ? form.password    : undefined,
        private_key: authMode === "key"      ? form.private_key : undefined,
        log_paths:   [...selectedPaths],
        domain:      form.domain,
      });
      setProfileId(data.id);
      setForm((f) => ({ ...f, password: "", private_key: "" }));
      await refreshProfiles();
      setShowSave(false);
      setSaveLabel("");
    } catch (err) {
      setImportErr(err.response?.data?.detail || "Could not save the profile.");
    }
  }

  async function removeProfile(id) {
    try { await api.delete(`/admin/import/profiles/${id}`); } catch { /* refresh shows the truth */ }
    if (id === profileId) setProfileId(null);
    refreshProfiles();
  }

  async function discover() {
    if (!form.host) return setDiscoverErr("Enter a host address first.");
    setDiscovering(true);
    setDiscoverErr("");
    setDiscovered(null);
    setSelectedPaths(new Set());
    setResult(null);
    try {
      const [{ data }, { data: cursorList }] = await Promise.all([
        api.post("/admin/import/ssh/discover", credentials()),
        api.get("/admin/import/cursors").catch(() => ({ data: [] })),
      ]);
      setDiscovered(data);
      const cursorMap = {};
      for (const c of cursorList) cursorMap[c.log_path] = c;
      setCursors(cursorMap);
      // Auto-select recommended files
      const recommended = new Set(
        data.logs.filter((l) => classifyLog(l.name).recommended).map((l) => l.path)
      );
      setSelectedPaths(recommended.size > 0 ? recommended : new Set(data.logs.slice(0, 1).map((l) => l.path)));
    } catch (err) {
      setDiscoverErr(err.response?.data?.detail || "Could not connect to server.");
    } finally {
      setDiscovering(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (selectedPaths.size === 0) return setImportErr("Select at least one log file above.");
    if (!defaultDomain)           return setImportErr("No site selected — pick one from the dropdown at the top.");
    setImportErr("");
    setResult(null);
    setLoading(true);
    const totals = { page_views: 0, sessions: 0, bot_visits: 0, skipped: 0, errors: 0 };
    const fileResults = [];
    try {
      for (const path of selectedPaths) {
        const name = path.split("/").pop();
        setImportProgress(name);
        try {
          const { data } = await api.post("/admin/import/ssh", {
            ...credentials(), log_path: path, domain: defaultDomain,
          });
          totals.page_views += data.page_views || 0;
          totals.sessions   += data.sessions   || 0;
          totals.bot_visits += data.bot_visits || 0;
          totals.skipped    += data.skipped    || 0;
          totals.errors     += data.errors     || 0;
          fileResults.push({ name, ok: true, page_views: data.page_views || 0 });
        } catch (fileErr) {
          fileResults.push({ name, ok: false, msg: fileErr.response?.data?.detail || "Failed" });
        }
      }
      setResult({ ...totals, file_results: fileResults });
    } catch (err) {
      setImportErr(err.response?.data?.detail || "Import failed.");
    } finally {
      setLoading(false);
      setImportProgress(null);
    }
  }

  const hasSavedSecret = !!(activeProfile && activeProfile.has_secret && activeProfile.auth_mode === authMode);
  const canDiscover = form.host && form.username &&
    (hasSavedSecret || (authMode === "password" ? form.password : form.private_key.trim()));

  return (
    <form onSubmit={submit} className="space-y-5 max-w-lg">
      <PullProfiles profiles={profiles} activeId={profileId} onLoad={loadProfile} onRemove={removeProfile} />

      {/* ── Credentials ── */}
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <Field label="Host">
            <Input type="text" value={form.host} onChange={(e) => update("host", e.target.value)}
              placeholder="server.example.com" autoComplete="off" />
          </Field>
        </div>
        <Field label="Port">
          <Input type="number" value={form.port} onChange={(e) => update("port", e.target.value)}
            placeholder="22" min="1" max="65535" />
        </Field>
      </div>

      <Field label="Username">
        <Input type="text" value={form.username} onChange={(e) => update("username", e.target.value)}
          placeholder="ubuntu" autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
      </Field>

      <div>
        <label className="block text-xs text-slate-400 mb-1.5">Authentication</label>
        <div className="flex gap-1 bg-surface-700 rounded-lg p-1 w-fit mb-3">
          {["password", "key"].map((m) => (
            <button key={m} type="button" onClick={() => setAuthMode(m)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                authMode === m ? "bg-accent text-white" : "text-slate-400 hover:text-white"
              }`}>
              {m === "password" ? "Password" : "Private Key"}
            </button>
          ))}
        </div>
        {authMode === "password" ? (
          <Input type="password" value={form.password}
            onChange={(e) => update("password", e.target.value)}
            placeholder={hasSavedSecret ? "Saved on the server — leave blank" : "••••••••"} autoComplete="new-password" />
        ) : (
          <Textarea value={form.private_key}
            onChange={(e) => update("private_key", e.target.value)}
            placeholder={hasSavedSecret ? "Saved on the server — leave blank" : "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"}
            rows={6} />
        )}
      </div>

      {/* ── Discover ── */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={discover}
          disabled={discovering || !canDiscover}
          className="px-4 py-2.5 bg-surface-600 hover:bg-surface-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors border border-surface-500"
        >
          {discovering ? "Searching…" : "Find Log Files"}
        </button>
        {!canDiscover && (
          <p className="text-xs text-slate-600">Fill in host, username, and password first</p>
        )}
      </div>

      {discoverErr && (
        <div className="p-3 bg-danger/10 border border-danger/30 rounded-xl text-sm text-danger">
          {discoverErr}
        </div>
      )}

      {/* ── Discovered log list ── */}
      {discovered && (
        <div className="bg-surface-700 border border-surface-500 rounded-xl overflow-hidden">
          <div className="px-4 py-2.5 border-b border-surface-500 bg-surface-800 flex items-center justify-between">
            <p className="text-xs text-slate-400">
              {discovered.logs.length > 0
                ? `Found ${discovered.logs.length} log file${discovered.logs.length !== 1 ? "s" : ""} — check the ones you want to import`
                : "No log files found on this server"}
            </p>
            <span className="text-xs text-slate-600 uppercase tracking-widest">via {discovered.method}</span>
          </div>

          {discovered.logs.length === 0 ? (
            <p className="p-4 text-xs text-slate-500">Could not auto-detect logs. Enter the path manually below.</p>
          ) : (
            <div className="divide-y divide-surface-600">
              {discovered.logs.map((log) => {
                const cls     = classifyLog(log.name);
                const checked = selectedPaths.has(log.path);
                const cursor  = cursors[log.path];
                const lastAt  = cursor?.last_line_at
                  ? new Date(cursor.last_line_at).toLocaleString()
                  : null;
                return (
                  <label
                    key={log.path}
                    className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                      checked ? "bg-accent/10" : "hover:bg-surface-600"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => togglePath(log.path)}
                      className="mt-0.5 shrink-0 accent-accent"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-sm font-medium ${checked ? "text-white" : "text-slate-300"}`}>
                          {log.name}
                        </span>
                        <span className={`text-xs font-medium px-1.5 py-0.5 rounded bg-surface-600 ${cls.color}`}>
                          {cls.tag}
                        </span>
                        {cls.recommended && (
                          <span className="text-xs text-success bg-success/10 px-1.5 py-0.5 rounded">
                            Recommended
                          </span>
                        )}
                        {lastAt && (
                          <span className="text-xs text-slate-500 bg-surface-600 px-1.5 py-0.5 rounded">
                            last import: {lastAt}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 mt-0.5">{cls.desc}</p>
                      <p className="text-xs text-slate-600 font-mono mt-0.5 truncate">{log.path}</p>
                    </div>
                  </label>
                );
              })}
            </div>
          )}

          {selectedPaths.size > 1 && (
            <div className="px-4 py-2 bg-surface-800 border-t border-surface-500">
              <p className="text-xs text-slate-500">
                {selectedPaths.size} files selected — they will be imported in sequence and results combined
              </p>
            </div>
          )}
        </div>
      )}

      {/* ── Manual path fallback ── */}
      {discovered?.logs.length === 0 && (
        <Field label="Log Path">
          <Input type="text" value={[...selectedPaths][0] || ""}
            onChange={(e) => setSelectedPaths(new Set([e.target.value].filter(Boolean)))}
            placeholder="Enter path manually" />
        </Field>
      )}

      {/* ── Domain + import ── */}
      {(selectedPaths.size > 0 || discovered) && (
        <>
          {importErr && (
            <div className="p-3 bg-danger/10 border border-danger/30 rounded-xl text-sm text-danger">
              {importErr}
            </div>
          )}

          <div className="flex items-center gap-3 flex-wrap">
            <button
              type="submit"
              disabled={loading || selectedPaths.size === 0}
              className="px-6 py-2.5 bg-accent hover:bg-accent-dim disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {loading
                ? importProgress
                  ? `Importing ${importProgress}…`
                  : "Importing…"
                : `Pull & Import${selectedPaths.size > 1 ? ` (${selectedPaths.size} files)` : ""}`}
            </button>
            <button type="button" onClick={() => setShowSave((s) => !s)}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors">
              {showSave ? "Cancel" : "Save as profile"}
            </button>
          </div>

          {showSave && (
            <div className="flex gap-2 items-center">
              <input
                type="text"
                value={saveLabel}
                onChange={(e) => setSaveLabel(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), persistProfile())}
                placeholder={form.domain || form.host || "Profile name"}
                className="flex-1 bg-surface-700 border border-surface-500 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-accent"
              />
              <button type="button" onClick={persistProfile}
                className="px-4 py-2 bg-accent hover:bg-accent-dim text-white text-xs rounded-lg transition-colors">
                Save
              </button>
            </div>
          )}

          {result && <ResultBox result={result} />}
        </>
      )}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Main Import page
// ---------------------------------------------------------------------------

const TABS = ["Tracker Setup", "Upload Log", "SSH Pull"];

export default function Import() {
  const [activeTab, setActiveTab] = useState("Tracker Setup");
  const { sites, currentSiteId } = useSiteStore();
  const currentSite = sites.find((s) => s.id === currentSiteId) || sites[0];
  const siteDomain = currentSite?.domain || "";

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Import Data</h1>
        <p className="text-xs text-slate-500 mt-0.5">
          Add the tracker snippet to your site, or import historical logs
        </p>
      </div>

      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      <div className="bg-surface-800 border border-surface-600 rounded-xl p-6">
        {activeTab === "Tracker Setup" && <TrackerSetupTab trackerKey={currentSite?.tracker_key} />}
        {activeTab === "Upload Log"    && <UploadLogTab defaultDomain={siteDomain} />}
        {activeTab === "SSH Pull"      && <SSHPullTab   defaultDomain={siteDomain} />}
      </div>
    </div>
  );
}
