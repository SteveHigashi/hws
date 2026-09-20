import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import api from "../utils/api";

export default function Reset() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 10) return setError("Use at least 10 characters.");
    if (password !== again) return setError("The two passwords differ.");
    try {
      const { data } = await api.post("/auth/reset", { token, new_password: password });
      setDone(data.email);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not reset the password");
    }
  };

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-white">Choose a new password</h1>
        </div>
        <form onSubmit={submit} className="bg-surface-800 border border-surface-600 rounded-xl p-6 glow space-y-4 text-sm">
          {!token && <p className="text-danger">This page needs the link from the server; open it from there.</p>}
          {error && <p className="text-danger bg-danger/10 border border-danger/20 rounded-lg px-3 py-2">{error}</p>}
          {done ? (
            <p className="text-slate-300">Password changed for {done}. Taking you to sign in…</p>
          ) : (
            <>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">New password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password"
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-accent" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1.5">Again</label>
                <input type="password" value={again} onChange={(e) => setAgain(e.target.value)} required autoComplete="new-password"
                  className="w-full bg-surface-700 border border-surface-500 rounded-lg px-3 py-2.5 text-white focus:outline-none focus:border-accent" />
              </div>
              <button type="submit" disabled={!token} className="w-full bg-accent hover:bg-accent-dim disabled:opacity-50 text-white font-medium py-2.5 rounded-lg">Set password</button>
            </>
          )}
          <p className="text-center text-xs"><Link to="/login" className="text-slate-500 hover:text-slate-300 underline">Back to sign in</Link></p>
        </form>
      </div>
    </div>
  );
}
