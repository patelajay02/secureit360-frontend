// lib/auth.js
// SecureIT360 — JWT auth helper
// Used by every page to make authenticated API calls

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("secureit360_token");
}

export function setToken(token) {
  if (typeof window === "undefined") return;
  localStorage.setItem("secureit360_token", token);
}

export function clearToken() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("secureit360_token");
  localStorage.removeItem("secureit360_user");
}

export function getUser() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("secureit360_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setUser(user) {
  if (typeof window === "undefined") return;
  localStorage.setItem("secureit360_user", JSON.stringify(user));
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
  const decoded = decodeToken(token);
  if (!decoded || !decoded.exp) return true;
  return Date.now() / 1000 > decoded.exp;
}

export async function authFetch(path, options = {}) {
  const token = getToken();

  if (!token || isTokenExpired(token)) {
    logout();
    throw new Error("Session expired. Please log in again.");
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

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  return response;
}

export function logout() {
  clearToken();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

export function requireAuth(router) {
  const token = getToken();
  if (!token || isTokenExpired(token)) {
    router.push("/login");
    return false;
  }
  return true;
}