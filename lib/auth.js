// lib/auth.js
// SecureIT360 - JWT auth helper with auto token refresh
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

export function setToken(token) {
  if (typeof window === "undefined") return;
  localStorage.setItem("token", token);
}

export function getRefreshToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export function setRefreshToken(token) {
  if (typeof window === "undefined") return;
  localStorage.setItem("refresh_token", token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
  localStorage.removeItem("mfa_gate");
  localStorage.removeItem("mfa_return_to");
}

// ── MFA gate (mandatory enrollment / challenge) ──────────────────────────────
// Set at login from the backend-authoritative decision; read by the global
// route guard. "enroll" | "challenge" | "" (cleared once the session is AAL2).
export function setMfaGate(gate) {
  if (typeof window === "undefined") return;
  if (!gate || gate === "allow") localStorage.removeItem("mfa_gate");
  else localStorage.setItem("mfa_gate", gate);
}

export function getMfaGate() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("mfa_gate") || "";
}

export function clearMfaGate() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("mfa_gate");
}

export function setMfaReturnTo(path) {
  if (typeof window === "undefined") return;
  if (path) localStorage.setItem("mfa_return_to", path);
}

export function getMfaReturnTo() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("mfa_return_to") || "";
}

export function getUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setUser(user) {
  if (typeof window === "undefined") return;
  localStorage.setItem("user", JSON.stringify(user));
}

export function decodeToken(token) {
  try {
    const payload = token.split(".")[1];
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

export function isTokenExpired(token) {
  try {
    const decoded = decodeToken(token);
    if (!decoded || !decoded.exp) return false;
    return Date.now() / 1000 > decoded.exp;
  } catch {
    return false;
  }
}

export function isTokenExpiringSoon(token) {
  try {
    const decoded = decodeToken(token);
    if (!decoded || !decoded.exp) return false;
    // Refresh if less than 10 minutes remaining
    return (decoded.exp - Date.now() / 1000) < 600;
  } catch {
    return false;
  }
}

async function refreshToken() {
  const refreshTkn = getRefreshToken();
  if (!refreshTkn) return false;
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshTkn }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    if (data.token) {
      setToken(data.token);
      if (data.refresh_token) setRefreshToken(data.refresh_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

export async function authFetch(path, options = {}) {
  let token = getToken();
  
  if (!token) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }

  // Auto refresh if token expiring soon
  if (isTokenExpiringSoon(token)) {
    const refreshed = await refreshToken();
    if (refreshed) {
      token = getToken();
    }
  }

  if (isTokenExpired(token)) {
    const refreshed = await refreshToken();
    if (refreshed) {
      token = getToken();
    } else {
      logout();
      throw new Error("Session expired. Please log in again.");
    }
  }

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    const refreshed = await refreshToken();
    if (refreshed) {
      token = getToken();
      return fetch(`${API_BASE}${path}`, {
        ...options,
        headers: { ...headers, Authorization: `Bearer ${token}` },
      });
    }
    logout();
    throw new Error("Your session has expired. Please log in again.");
  }

  return response;
}

export async function publicFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

export function logout() {
  clearToken();
  if (typeof window !== "undefined") {
    window.location.href = "/";
  }
}

export function requireAuth(router) {
  const token = getToken();
  if (!token || isTokenExpired(token)) {
    router.push("/");
    return false;
  }
  return true;
}

// Auto logout after 15 minutes of inactivity
if (typeof window !== "undefined") {
  let inactivityTimer;
  
  const resetTimer = () => {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => {
      logout();
    }, 15 * 60 * 1000);
  };

  ["mousemove", "keydown", "click", "scroll", "touchstart"].forEach(event => {
    window.addEventListener(event, resetTimer, true);
  });

  resetTimer();
}