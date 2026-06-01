// Central API configuration for the RankForge AI frontend.
// All API calls go to the deployed backend (Railway).
const API_BASE = "https://rankforge-ai-production.up.railway.app";

// Expose globally so other scripts (auth, voice-call, live-chat, page inline JS) can use it.
window.API_BASE = API_BASE;
window.VOICE_API_URL = API_BASE;
