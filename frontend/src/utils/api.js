import axios from "axios";

// When built with VITE_API_PROXY set, all requests go through the PHP proxy.
// Otherwise uses the clean /api base (dev, desktop sidecar, VPS with nginx).
const PROXY = import.meta.env.VITE_API_PROXY || "";

const api = axios.create({ baseURL: PROXY ? "" : "/api" });

// Attach stored token on cold load
const stored = JSON.parse(localStorage.getItem("ha-auth") || "{}");
if (stored?.state?.token) {
  api.defaults.headers.common["Authorization"] = `Bearer ${stored.state.token}`;
}

// Append site_id to all GET requests when a site is selected
api.interceptors.request.use((config) => {
  if (config.method === "get" || config.method === "GET") {
    try {
      const siteState = JSON.parse(localStorage.getItem("ha-site") || "{}");
      const siteId = siteState?.state?.currentSiteId;
      if (siteId) {
        const url = new URL(config.url, "http://placeholder");
        url.searchParams.set("site_id", siteId);
        config.url = url.pathname + url.search;
      }
    } catch (_) {
      // Never break the request
    }
  }
  return config;
});

// PHP proxy rewrite — runs after site_id is appended so the full path is captured
if (PROXY) {
  api.interceptors.request.use((config) => {
    config.url = `${PROXY}?path=${encodeURIComponent("/api" + config.url)}`;
    return config;
  });
}

// On any 401 (expired/invalid token), clear the stale session and bounce to login
// instead of leaving a dead dashboard that silently fails every data call.
api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status;
    let url = error?.config?.url || "";
    try { url = decodeURIComponent(url); } catch (_) {}
    const isLoginCall = url.includes("/auth/login");
    if (status === 401 && !isLoginCall) {
      try {
        localStorage.removeItem("ha-auth");
        delete api.defaults.headers.common["Authorization"];
      } catch (_) {}
      if (!window.location.hash.startsWith("#/login")) {
        window.location.hash = "#/login";
      }
    }
    return Promise.reject(error);
  }
);

// Build a full URL for callers that use fetch/EventSource directly (streaming endpoints).
// Honours VITE_API_PROXY the same way the axios instance does.
export function apiUrl(path) {
  return PROXY ? `${PROXY}?path=${encodeURIComponent("/api" + path)}` : `/api${path}`;
}

export default api;
