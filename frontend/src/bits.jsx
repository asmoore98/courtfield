// Small pieces shared by the leads, estimates and clients screens.
import { useEffect, useState } from "react";
import { api, safeGet, safeSet } from "./api";

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) : "");
export const fmtWhen = (iso) =>
  iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) : "";
export const money0 = (n) => (n == null ? "" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }));

export const COURT_LABEL = { tennis: "Tennis", pickleball: "Pickleball", basketball: "Basketball", multi_court: "Multi-court", turf_field: "Turf field" };
export const SCOPE_LABEL = { new_construction: "New construction", resurfacing: "Resurfacing", repair: "Repair" };

// Which screen a tab is on (list, one record, a form). An open form is
// remembered so switching tabs and coming back lands on it again.
export function useScreen(key, initial) {
  const [screen, setState] = useState(() => initial ?? safeGet(key) ?? { view: "list" });
  const setScreen = (s) => {
    safeSet(key, s.view === "edit" ? s : null);
    setState(s);
  };
  useEffect(() => {
    if (initial) safeSet(key, initial.view === "edit" ? initial : null);
  }, []);
  return [screen, setScreen];
}

// Load from the API; `reload()` fetches again.
export function useApi(path) {
  const [state, setState] = useState({ data: null, error: null });
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    api(path)
      .then((data) => live && setState({ data, error: null }))
      .catch((e) => live && setState((s) => ({ ...s, error: e.message })));
    return () => {
      live = false;
    };
  }, [path, n]);
  return { ...state, reload: () => setN((x) => x + 1) };
}

// Form state that's kept on this device until it's saved or thrown away.
export function useDraft(key, initial) {
  const [saved] = useState(() => safeGet(key));
  const [form, setForm] = useState(() => saved?.form ?? initial);
  const [restoredAt, setRestoredAt] = useState(saved?.savedAt ?? null);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    if (dirty) safeSet(key, { form, savedAt: Date.now() });
  }, [dirty, form]);
  const set = (k, v) => {
    setDirty(true);
    setForm((f) => ({ ...f, [k]: v }));
  };
  return {
    form,
    set,
    setForm: (f) => {
      setDirty(true);
      setForm(f);
    },
    restoredAt,
    discard: (fresh) => {
      safeSet(key, null);
      setDirty(false);
      setRestoredAt(null);
      setForm(fresh);
    },
    done: () => safeSet(key, null),
  };
}

export function Restored({ at, onDiscard, label = "Start over" }) {
  if (!at) return null;
  return (
    <div className="restored" role="status">
      <span>Picked up your unsaved work from {fmtWhen(new Date(at).toISOString())}.</span>
      <button type="button" className="link" onClick={onDiscard}>
        {label}
      </button>
    </div>
  );
}

// Shared-drive links, one per line, shown as tappable links. Anything that
// isn't a web link shows as plain text.
export function LinkList({ text, empty = "None yet." }) {
  const lines = (text ?? "").split("\n").map((s) => s.trim()).filter(Boolean);
  if (!lines.length) return <p className="help">{empty}</p>;
  return (
    <ul className="link-list">
      {lines.map((l, i) => (
        <li key={i}>
          {/^https?:\/\//i.test(l) ? (
            <a href={l} target="_blank" rel="noopener noreferrer">
              {prettyLink(l)}
            </a>
          ) : (
            l
          )}
        </li>
      ))}
    </ul>
  );
}

function prettyLink(url) {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, "");
    if (host === "drive.google.com" || host === "docs.google.com") return `Google Drive: ${decodeURIComponent(u.pathname).slice(0, 60)}`;
    return `${host}${u.pathname.length > 1 ? decodeURIComponent(u.pathname).slice(0, 50) : ""}`;
  } catch {
    return url;
  }
}

export function LinksField({ value, onChange, id }) {
  return (
    <label htmlFor={id}>
      Plans &amp; documents
      <span className="help field-help">Paste share links (Google Drive, Dropbox), one per line.</span>
      <textarea id={id} rows={3} value={value} onChange={(e) => onChange(e.target.value)} placeholder="https://drive.google.com/…" />
    </label>
  );
}

// The paper trail: who did what and when.
export function ActivityList({ items }) {
  if (!items?.length) return null;
  return (
    <section className="panel">
      <h3>History</h3>
      <ol className="activity">
        {items.map((a, i) => (
          <li key={i}>
            <span className="act-what">
              <b>{a.action}</b>
              {a.detail && <span className="act-detail">{a.detail}</span>}
            </span>
            <span className="act-who">
              {a.by}
              <span className="sub">{fmtWhen(a.at)}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// A button that opens a short note box before it acts (lost, dropped, follow-up…).
export function NoteAction({ label, prompt, placeholder, required = true, tone, onSubmit }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  if (!open)
    return (
      <button type="button" className={tone === "danger" ? "btn-ghost danger" : "btn-ghost"} onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  async function go(e) {
    e.preventDefault();
    if (required && note.trim().length < 3) return setError("Write a few words first.");
    setBusy(true);
    setError(null);
    try {
      await onSubmit(note.trim());
      setOpen(false);
      setNote("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="note-action" onSubmit={go}>
      <label>
        {prompt}
        <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder={placeholder} autoFocus />
      </label>
      {error && <p className="err">{error}</p>}
      <div className="note-buttons">
        <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>
          Cancel
        </button>
        <button className="btn" disabled={busy}>
          {busy ? "Saving…" : label}
        </button>
      </div>
    </form>
  );
}

export const ESTIMATE_STATUS = [
  ["draft", "Draft"],
  ["sent", "Sent"],
  ["won", "Won"],
  ["lost", "Lost"],
  ["no_bid", "No bid"],
  ["expired", "Expired"],
];
export const LEAD_STATUS = { new: "New", estimating: "Being estimated", estimated: "Estimate sent", dropped: "Dropped" };

export function StatusChip({ status, label }) {
  return <span className={`chip st-${status}`}>{label ?? Object.fromEntries(ESTIMATE_STATUS)[status] ?? LEAD_STATUS[status] ?? status}</span>;
}
