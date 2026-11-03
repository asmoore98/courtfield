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

// The company's Google Drive folder (Settings), for the "Open Google Drive" button.
let driveUrl = "";
export const setDriveUrl = (u) => {
  driveUrl = u || "";
};

export function LinksField({ value, onChange, id }) {
  return (
    <div className="links-field">
      <label htmlFor={id}>
        Plans &amp; documents
        <span className="help field-help">
          Open Google Drive, find the file, tap Share → Copy link, and paste it here. One link per line.
        </span>
      </label>
      <textarea id={id} rows={3} value={value} onChange={(e) => onChange(e.target.value)} placeholder="https://drive.google.com/…" />
      <a className="btn-ghost drive-btn" href={driveUrl || "https://drive.google.com/"} target="_blank" rel="noopener noreferrer">
        Open Google Drive
      </a>
    </div>
  );
}

// Enter in a box moves on instead of saving the whole form (a save on an
// estimate makes a new version). Saving takes the Save button.
export function noEnterSubmit(e) {
  const t = e.target;
  if (e.key === "Enter" && t.tagName === "INPUT" && !["submit", "button", "checkbox", "radio"].includes(t.type)) {
    e.preventDefault();
    const fields = [...e.currentTarget.querySelectorAll("input:not([type=hidden]):not([disabled]), select, textarea")];
    fields[fields.indexOf(t) + 1]?.focus();
  }
}

/* ---------- addresses: street, city, state, ZIP ---------- */

const PARTS = ["street", "city", "state", "zip"];

// "100 Main St, Stuart, FL 34994": the one-line version, as the server builds it.
export function composeAddress(a) {
  const region = [a.state, a.zip].map((x) => (x ?? "").trim()).filter(Boolean).join(" ");
  const place = [(a.city ?? "").trim(), region].filter(Boolean).join(", ");
  return [(a.street ?? "").trim(), place].filter(Boolean).join(", ");
}

// Address parts from a saved record: its own parts, or an old one-line
// address split as well as it can be ("Street, City, ST 12345").
export function addressFrom(rec, prefix, line) {
  const parts = Object.fromEntries(PARTS.map((p) => [p, rec?.[`${prefix}_${p}`] ?? ""]));
  if (PARTS.some((p) => parts[p]) || !line) return parts;
  const m = line.trim().match(/^(.*?),\s*([^,]+?),\s*([A-Za-z]{2})\.?\s*(\d{5}(?:-\d{4})?)?$/);
  return m ? { street: m[1], city: m[2], state: m[3].toUpperCase(), zip: m[4] ?? "" } : { street: line.trim(), city: "", state: "", zip: "" };
}

// What to send: the parts under their prefix and the one-line version.
export const addressBody = (a, prefix, lineKey) => ({
  ...Object.fromEntries(PARTS.map((p) => [`${prefix}_${p}`, (a?.[p] ?? "").trim()])),
  [lineKey]: composeAddress(a ?? {}),
});

export const blankAddress = () => ({ street: "", city: "", state: "FL", zip: "" });

/* Street, city, state and ZIP boxes. The autocomplete names let a phone or
   browser fill in an address it already knows. `section` keeps a billing
   address and a site address apart when both are on one page. */
export function AddressFields({ value, onChange, section = "site", legend }) {
  const a = value ?? blankAddress();
  const set = (k, v) => onChange({ ...a, [k]: v });
  const ac = (f) => `section-${section} ${f}`;
  return (
    <fieldset className="address">
      {legend && <legend>{legend}</legend>}
      <label className="addr-street">
        Street address
        <input value={a.street} onChange={(e) => set("street", e.target.value)} autoComplete={ac("street-address")} placeholder="123 Main St" />
      </label>
      <div className="addr-row">
        <label className="addr-city">
          City
          <input value={a.city} onChange={(e) => set("city", e.target.value)} autoComplete={ac("address-level2")} />
        </label>
        <label className="addr-state">
          State
          <input value={a.state} onChange={(e) => set("state", e.target.value.toUpperCase())} autoComplete={ac("address-level1")} maxLength={2} />
        </label>
        <label className="addr-zip">
          ZIP
          <input value={a.zip} onChange={(e) => set("zip", e.target.value.replace(/[^\d-]/g, ""))} autoComplete={ac("postal-code")} inputMode="numeric" maxLength={10} />
        </label>
      </div>
    </fieldset>
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
export const LEAD_STATUS = {
  new: "New",
  estimating: "Being estimated",
  estimated: "Estimate sent",
  won: "Won",
  lost: "Lost",
  no_bid: "No bid",
  expired: "Estimate expired",
  dropped: "Dropped",
};

export function StatusChip({ status, label }) {
  return <span className={`chip st-${status}`}>{label ?? Object.fromEntries(ESTIMATE_STATUS)[status] ?? LEAD_STATUS[status] ?? status}</span>;
}
