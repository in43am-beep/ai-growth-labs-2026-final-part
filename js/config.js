// Central API configuration for the RankForge AI frontend.
// Production backend (Railway). Used when the static frontend is hosted
// separately (e.g. Netlify) from the backend.
const PROD_API_BASE = "https://rankforge-ai-production.up.railway.app";

// When the site is served from the SAME server as the backend (local dev,
// a temporary tunnel, or an all-in-one deploy), call the API on the same
// origin so links keep working without re-pointing config. Otherwise use
// the production backend URL.
(function () {
  var host = window.location.hostname || "";
  var sameOrigin = (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.endsWith(".trycloudflare.com") ||
    host.endsWith(".devinapps.com") ||
    host.endsWith(".up.railway.app")
  );
  var API_BASE = sameOrigin ? "" : PROD_API_BASE;
  // Expose globally so other scripts (auth, voice-call, live-chat, inline JS) can use it.
  window.API_BASE = API_BASE;
  window.VOICE_API_URL = API_BASE || window.location.origin;
})();
