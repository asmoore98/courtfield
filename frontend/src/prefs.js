// How the app looks for this person: light or dark screen and text size.
// Saved to their account (Settings) and kept on this device so the right
// look shows before the app has loaded anything.
import { safeGet, safeSet } from "./api";

const KEY = "cf.prefs";

export function applyPrefs(p) {
  const prefs = p ?? {};
  const root = document.documentElement;
  if (prefs.theme === "light" || prefs.theme === "dark") root.dataset.theme = prefs.theme;
  else delete root.dataset.theme;
  if (prefs.text === "large") root.dataset.text = "large";
  else delete root.dataset.text;
  const dark = prefs.theme === "dark" || (prefs.theme !== "light" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#12171d" : "#1d4f8f");
  safeSet(KEY, prefs);
}

export const savedPrefs = () => safeGet(KEY, {});
