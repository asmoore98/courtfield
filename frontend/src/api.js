// Thin API client. The dev token lives in localStorage until real sign-in exists.

const TOKEN_KEY = "cf.token";

export const getToken = () => safeGet(TOKEN_KEY);
export const setToken = (t) => safeSet(TOKEN_KEY, t);
export const clearToken = () => safeSet(TOKEN_KEY, null);

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export const DEMO = import.meta.env.VITE_DEMO === "1";

export async function api(path, { method = "GET", body } = {}) {
  if (DEMO) {
    const { demoFetch } = await import("./demoServer.js");
    const r = await demoFetch(path, { method, body, token: getToken() });
    if (!r.ok) throw new ApiError(r.status, r.data.detail ?? "Request failed");
    return r.data;
  }
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: {
        Authorization: `Bearer ${getToken()}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "No connection");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Request failed");
  }
  return res.json();
}

export function safeGet(key, fallback = null) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}

export function safeSet(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}
