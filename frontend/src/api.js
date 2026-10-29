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

// Called when the server says this device's sign-in has ended (revoked,
// expired, or the person was turned off). Time saved on the phone is kept
// and syncs after the next sign-in.
const signedOutListeners = new Set();
export function onSignedOut(fn) {
  signedOutListeners.add(fn);
  return () => signedOutListeners.delete(fn);
}
function checkSignedOut(status, path) {
  if (status === 401 && getToken() && !path.startsWith("/api/auth/")) signedOutListeners.forEach((fn) => fn());
}

export async function api(path, { method = "GET", body } = {}) {
  if (DEMO) {
    const { demoFetch } = await import("./demoServer.js");
    const r = await demoFetch(path, { method, body, token: getToken() });
    if (!r.ok) {
      checkSignedOut(r.status, path);
      throw new ApiError(r.status, r.data.detail ?? "Request failed");
    }
    return r.data;
  }
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: {
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "No connection");
  }
  if (res.status === 204) return null;
  if (!res.ok) {
    checkSignedOut(res.status, path);
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    if (Array.isArray(detail)) detail = detail[0]?.msg ? `Check the form: ${detail[0].msg.toLowerCase()}.` : "Check the form and try again.";
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Request failed");
  }
  return res.json();
}

// Save a file from the API (e.g. a CSV) to the device.
export async function download(path, filename) {
  let res;
  try {
    res = await fetch(path, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} });
  } catch {
    throw new ApiError(0, "No connection. Downloads need signal.");
  }
  if (!res.ok) {
    checkSignedOut(res.status, path);
    throw new ApiError(res.status, "Couldn't create the file. Try again.");
  }
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export function safeGet(key, fallback = null) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}

// Unsaved forms kept on this device. Cleared on sign-out so the next person
// to use the phone doesn't see them.
export function clearDrafts() {
  try {
    for (const k of Object.keys(localStorage)) if (k.startsWith("cf.draft.") || /^cf\.\w+\.screen$/.test(k)) localStorage.removeItem(k);
  } catch {}
}

export function safeSet(key, value) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}
