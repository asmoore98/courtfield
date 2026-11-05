// Settings, for everyone: your profile, how the app looks, your password and
// signed-in devices, and the suggestion box. The GM also gets the team's
// suggestions and the company settings (proposal header, Drive, estimates).
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { fmtWhen } from "./bits";
import Photos, { uploadAll } from "./Photos";
import { applyPrefs } from "./prefs";

const FIELDS = [
  ["proposal_name", "Company name on proposals", "Leave blank to use the account name"],
  ["proposal_address", "Address", ""],
  ["proposal_phone", "Phone", ""],
  ["proposal_email", "Email", ""],
  ["proposal_license", "License number", "e.g. CBC1234567"],
  ["proposal_logo_url", "Logo link", "A link to the logo image (optional)"],
];


const ROLE_WORD = { gm: "GM", owner: "Owner", estimator: "Estimator", pm: "Project manager", crew_lead: "Crew lead", crew: "Crew", warehouse: "Shop / warehouse", sales: "Sales" };

function Saved({ when }) {
  return when ? <span className="loc-msg" role="status">Saved.</span> : null;
}

function Profile({ me, onMe }) {
  const [name, setName] = useState(me.name);
  const [phone, setPhone] = useState(me.phone ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onMe(await api("/api/me", { method: "PATCH", body: { name: name.trim(), phone: phone.trim() } }));
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="panel settings-form" onSubmit={save}>
      <h3>Your profile</h3>
      <div className="grid">
        <label>
          Name
          <input value={name} onChange={(e) => { setName(e.target.value); setSaved(false); }} required minLength={2} autoComplete="name" />
        </label>
        <label>
          Phone
          <input value={phone} onChange={(e) => { setPhone(e.target.value); setSaved(false); }} inputMode="tel" autoComplete="tel" placeholder="(555) 555-5555" />
        </label>
        <div className="fact">
          <span className="fact-label">Sign-in email</span>
          <span>{me.email || "—"}</span>
          <span className="help">To change it, ask the GM.</span>
        </div>
        <div className="fact">
          <span className="fact-label">Role</span>
          <span>{ROLE_WORD[me.role] ?? me.role}</span>
          <span className="help">{me.company_name}</span>
        </div>
      </div>
      {error && <p className="err">{error}</p>}
      <div className="editor-actions">
        <Saved when={saved} />
        <button className="btn" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button>
      </div>
    </form>
  );
}

function Looks({ me, onMe, tabs }) {
  const prefs = { theme: "system", text: "normal", start: "", ...(me.prefs ?? {}) };
  const [error, setError] = useState(null);
  async function set(k, v) {
    const next = { ...prefs, [k]: v };
    applyPrefs(next); // right away, even before it's saved
    onMe({ ...me, prefs: next });
    setError(null);
    try {
      onMe(await api("/api/me", { method: "PATCH", body: { prefs: next } }));
    } catch (e) {
      setError(e.status === 0 ? "Changed on this phone. It'll save to your account next time you're online." : e.message);
    }
  }
  return (
    <section className="panel settings-form">
      <h3>How the app looks</h3>
      <div className="setting-row">
        <span className="setting-label">Screen</span>
        <div className="seg" role="group" aria-label="Screen">
          {[["system", "Match my phone"], ["light", "Light"], ["dark", "Dark"]].map(([v, l]) => (
            <button type="button" key={v} aria-pressed={prefs.theme === v} onClick={() => set("theme", v)}>{l}</button>
          ))}
        </div>
      </div>
      <div className="setting-row">
        <span className="setting-label">Text size</span>
        <div className="seg" role="group" aria-label="Text size">
          {[["normal", "Normal"], ["large", "Larger"]].map(([v, l]) => (
            <button type="button" key={v} aria-pressed={prefs.text === v} onClick={() => set("text", v)}>{l}</button>
          ))}
        </div>
      </div>
      {tabs.length > 1 && (
        <label className="setting-row">
          <span className="setting-label">Open the app on</span>
          <select value={prefs.start} onChange={(e) => set("start", e.target.value)}>
            <option value="">The usual tab</option>
            {tabs.filter(([k]) => k !== "settings").map(([k, l]) => (
              <option key={k} value={k}>{l}</option>
            ))}
          </select>
        </label>
      )}
      <p className="help">Saved to your account, so it's the same on every phone and computer you sign in on.</p>
      {error && <p className="help t-near">{error}</p>}
    </section>
  );
}

function Password() {
  const [f, setF] = useState({ current: "", new: "", again: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  async function save(e) {
    e.preventDefault();
    setMsg(null);
    if (f.new !== f.again) return setMsg({ err: true, text: "The new passwords don't match." });
    setBusy(true);
    try {
      const r = await api("/api/me/password", { method: "POST", body: { current: f.current, new: f.new } });
      setF({ current: "", new: "", again: "" });
      setMsg({ text: `Password changed.${r.signed_out ? ` Signed out ${r.signed_out} other device${r.signed_out > 1 ? "s" : ""}.` : ""}` });
    } catch (err) {
      setMsg({ err: true, text: err.message });
    } finally {
      setBusy(false);
    }
  }
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  return (
    <form className="panel settings-form" onSubmit={save}>
      <h3>Password</h3>
      <div className="grid">
        <label className="span-2">
          Current password
          <input type="password" value={f.current} onChange={set("current")} autoComplete="current-password" required />
        </label>
        <label>
          New password
          <input type="password" value={f.new} onChange={set("new")} autoComplete="new-password" minLength={8} required />
        </label>
        <label>
          New password again
          <input type="password" value={f.again} onChange={set("again")} autoComplete="new-password" minLength={8} required />
        </label>
      </div>
      <p className="help">At least 8 characters. Your other phones and computers will need to sign in again.</p>
      {msg && <p className={msg.err ? "err" : "help"} role="status">{msg.text}</p>}
      <div className="editor-actions">
        <button className="btn" disabled={busy}>{busy ? "Saving…" : "Change password"}</button>
      </div>
    </form>
  );
}

function deviceName(ua) {
  const s = ua || "";
  const os = /iPhone/.test(s) ? "iPhone" : /iPad/.test(s) ? "iPad" : /Android/.test(s) ? "Android" : /Windows/.test(s) ? "Windows" : /Mac OS X|Macintosh/.test(s) ? "Mac" : /Linux/.test(s) ? "Linux" : "";
  const br = /Edg\//.test(s) ? "Edge" : /CriOS|Chrome\//.test(s) ? "Chrome" : /FxiOS|Firefox\//.test(s) ? "Firefox" : /Safari\//.test(s) ? "Safari" : "";
  return [br, os].filter(Boolean).join(" on ") || s.slice(0, 60) || "Unknown device";
}

function Devices() {
  const [list, setList] = useState(null);
  const [msg, setMsg] = useState(null);
  const load = useCallback(() => api("/api/me/devices").then(setList).catch(() => setList([])), []);
  useEffect(() => void load(), [load]);
  async function others() {
    const r = await api("/api/me/devices/sign-out-others", { method: "POST" });
    setMsg(`Signed out ${r.signed_out} device${r.signed_out === 1 ? "" : "s"}.`);
    load();
  }
  if (!list) return null;
  return (
    <section className="panel settings-form">
      <h3>Where you're signed in</h3>
      <ul className="device-list">
        {list.map((d) => (
          <li key={d.id}>
            <b>{deviceName(d.device)}</b>
            {d.this_one && <span className="chip chip-active">This one</span>}
            <span className="sub">Last used {fmtWhen(d.last_used)}</span>
          </li>
        ))}
      </ul>
      {list.length > 1 && (
        <button className="btn-ghost" onClick={others}>Sign out everywhere else</button>
      )}
      {msg && <p className="help">{msg}</p>}
      <p className="help">Lost a phone? Sign out everywhere else, then change your password.</p>
    </section>
  );
}

const PAGES = ["", "Field (crew screen)", "Jobs", "Leads", "Estimates", "Clients", "Library", "Crews", "Materials", "Timesheets", "Team", "Settings", "Signing in", "Somewhere else"];
const KIND_WORD = { idea: "Idea", problem: "Problem" };
const STATUS_WORD = { new: "Sent", seen: "Seen", done: "Done" };

function SuggestionBox({ onSent }) {
  const [kind, setKind] = useState("idea");
  const [text, setText] = useState("");
  const [page, setPage] = useState("");
  const [shots, setShots] = useState([]);
  const [busy, setBusy] = useState(null);
  const [msg, setMsg] = useState(null);
  async function send(e) {
    e.preventDefault();
    setMsg(null);
    if (text.trim().length < 3) return setMsg({ err: true, text: "Write a few words about it first." });
    setBusy("Sending…");
    try {
      const f = await api("/api/feedback", { method: "POST", body: { kind, text: text.trim(), page, device: navigator.userAgent.slice(0, 200) } });
      if (shots.length) await uploadAll("feedback", f.id, shots, (i, n) => setBusy(`Uploading screenshot ${i} of ${n}…`));
      await api(`/api/feedback/${f.id}/send`, { method: "POST" });
      setText("");
      setShots([]);
      setPage("");
      setMsg({ text: "Sent. Thanks! It goes straight to the person who builds the app." });
      onSent();
    } catch (err) {
      setMsg({ err: true, text: err.status === 0 ? "No signal. Try again in a minute; what you wrote is still here." : err.message });
    } finally {
      setBusy(null);
    }
  }
  return (
    <form className="panel settings-form suggestion-box" onSubmit={send}>
      <h3>Suggestion box</h3>
      <p className="help">An idea to make the app better, or something that isn't working right. Add screenshots if they help.</p>
      <div className="seg" role="group" aria-label="What kind">
        <button type="button" aria-pressed={kind === "idea"} onClick={() => setKind("idea")}>An idea</button>
        <button type="button" aria-pressed={kind === "problem"} onClick={() => setKind("problem")}>Something's wrong</button>
      </div>
      <label>
        {kind === "problem" ? "What happened? What did you expect?" : "What's your idea?"}
        <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)}
          placeholder={kind === "problem" ? "e.g. On the Field tab, Clock out is hidden behind the keyboard when I type a note." : "e.g. Let the crew lead see tomorrow's job the night before."} />
      </label>
      <label>
        Where in the app? <span className="optional">(optional)</span>
        <select value={page} onChange={(e) => setPage(e.target.value)}>
          {PAGES.map((p) => (
            <option key={p} value={p}>{p || "Pick one"}</option>
          ))}
        </select>
      </label>
      <Photos kind="feedback" id={null} pending={shots} onPending={setShots} title="Screenshots" when="send it" />
      {msg && <p className={msg.err ? "err" : "help"} role="status">{msg.text}</p>}
      <div className="editor-actions">
        <button className="btn" disabled={!!busy}>{busy ?? "Send it"}</button>
      </div>
    </form>
  );
}

function FeedbackList({ me, version }) {
  const [data, setData] = useState(null);
  const gm = me.role === "gm";
  const load = useCallback(() => api("/api/feedback").then(setData).catch(() => setData({ items: [] })), []);
  useEffect(() => void load(), [load, version]);
  const [open, setOpen] = useState(null);
  async function mark(f, status) {
    await api(`/api/feedback/${f.id}`, { method: "PATCH", body: { status } });
    load();
  }
  if (!data || !data.items.length) return null;
  return (
    <section className="panel settings-form">
      <h3>{gm ? "Suggestions from the team" : "What you've sent"}</h3>
      {gm && !data.email_ready && (
        <p className="help t-near">
          Email isn't set up on the server yet, so these are only here for now. Once it's set up, each new one is emailed with its screenshots.
        </p>
      )}
      <ul className="reports feedback-list">
        {data.items.map((f) => (
          <li key={f.id} className={f.status === "new" && f.kind === "problem" ? "is-open" : ""}>
            <p>
              <b>{KIND_WORD[f.kind]}:</b> {f.text}
              <span className={`chip chip-fb-${f.status}`}>{STATUS_WORD[f.status]}</span>
            </p>
            <p className="sub">
              {gm && `${f.by} · `}
              {fmtWhen(f.at)}
              {f.page && ` · ${f.page}`}
              {f.screenshots > 0 && ` · ${f.screenshots} screenshot${f.screenshots > 1 ? "s" : ""}`}
              {gm && f.email_error && ` · not emailed`}
            </p>
            {f.reply && <p className="r-resolved">Reply: {f.reply}</p>}
            {(f.screenshots > 0 || gm) && (
              <div className="fb-actions">
                {f.screenshots > 0 && (
                  <button className="link" onClick={() => setOpen(open === f.id ? null : f.id)}>{open === f.id ? "Hide screenshots" : "Screenshots"}</button>
                )}
                {gm && f.status !== "seen" && f.status !== "done" && <button className="link" onClick={() => mark(f, "seen")}>Mark seen</button>}
                {gm && f.status !== "done" && <button className="link" onClick={() => mark(f, "done")}>Mark done</button>}
              </div>
            )}
            {open === f.id && <Photos kind="feedback" id={f.id} canAdd={false} title="Screenshots" />}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function SettingsView({ me, onMe, tabs = [] }) {
  const [sent, setSent] = useState(0);
  return (
    <div className="settings">
      <h2 className="detail-title">Settings</h2>
      <div className="settings-cols">
        <div>
          <Profile me={me} onMe={onMe} />
          <Looks me={me} onMe={onMe} tabs={tabs} />
          <Password />
          <Devices />
        </div>
        <div>
          <SuggestionBox onSent={() => setSent((n) => n + 1)} />
          <FeedbackList me={me} version={sent} />
        </div>
      </div>
      {me.role === "gm" && <CompanySettings />}
    </div>
  );
}

function CompanySettings() {
  const [f, setF] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api("/api/company").then(setF).catch((e) => setError(e.message));
  }, []);
  if (!f) return <p className="empty">{error ?? "Loading settings…"}</p>;
  const set = (k, v) => {
    setSaved(false);
    setF((x) => ({ ...x, [k]: v }));
  };

  async function save(e) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const body = Object.fromEntries([
        ...FIELDS.map(([k]) => [k, f[k] ?? ""]), ["proposal_terms", f.proposal_terms ?? ""], ["drive_folder_url", f.drive_folder_url ?? ""],
      ]);
      body.estimate_valid_days = Number(f.estimate_valid_days) || 30;
      setF(await api("/api/company", { method: "PATCH", body }));
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="editor company-settings" onSubmit={save}>
      <h2 className="settings-group">Company <span className="sub-inline">(GM only)</span></h2>
      <section className="panel">
        <h3>Proposal header</h3>
        <p className="help">What prints at the top of every proposal. Fill in what you know now and change it any time.</p>
        <div className="grid">
          {FIELDS.map(([k, label, ph]) => (
            <label key={k} className={k === "proposal_name" || k === "proposal_address" || k === "proposal_logo_url" ? "span-2" : undefined}>
              {label}
              <input value={f[k] ?? ""} onChange={(e) => set(k, e.target.value)} placeholder={ph || (k === "proposal_name" ? f.name : "")} />
            </label>
          ))}
          <label className="span-2">
            Standard terms
            <span className="help field-help">Payment schedule, warranty, change orders, weather, access… Prints at the bottom of every proposal.</span>
            <textarea rows={6} value={f.proposal_terms ?? ""} onChange={(e) => set("proposal_terms", e.target.value)} />
          </label>
        </div>
      </section>
      <section className="panel">
        <h3>Google Drive</h3>
        <label className="span-2">
          Company Drive folder
          <span className="help field-help">
            The "Open Google Drive" button next to every link box opens this folder. Open the folder in Drive and copy the address from the browser. Blank opens
            Google Drive's home page.
          </span>
          <input value={f.drive_folder_url ?? ""} onChange={(e) => set("drive_folder_url", e.target.value)} placeholder="https://drive.google.com/drive/folders/…" />
        </label>
      </section>
      <section className="panel">
        <h3>Estimates</h3>
        <label className="inline-field">
          A sent estimate is good for
          <span className="affix">
            <input type="number" min="1" max="365" value={f.estimate_valid_days} onChange={(e) => set("estimate_valid_days", e.target.value)} />
            <span aria-hidden="true">days</span>
          </span>
        </label>
        <p className="help">After that it's marked expired. A follow-up reminder shows 15 days after it's sent. Each estimate can change its own number of days.</p>
      </section>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        {saved && <span className="loc-msg">Saved.</span>}
        <button className="btn" disabled={saving}>
          {saving ? "Saving…" : "Save company settings"}
        </button>
      </div>
    </form>
  );
}
