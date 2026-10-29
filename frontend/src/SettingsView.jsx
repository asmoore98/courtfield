// GM settings: what prints at the top of a proposal, standard terms, and how
// long a sent estimate stays good. Placeholder until the real letterhead is set.
import { useEffect, useState } from "react";
import { api } from "./api";

const FIELDS = [
  ["proposal_name", "Company name on proposals", "Leave blank to use the account name"],
  ["proposal_address", "Address", ""],
  ["proposal_phone", "Phone", ""],
  ["proposal_email", "Email", ""],
  ["proposal_license", "License number", "e.g. CBC1234567"],
  ["proposal_logo_url", "Logo link", "A link to the logo image (optional)"],
];

export default function SettingsView() {
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
      const body = Object.fromEntries([...FIELDS.map(([k]) => [k, f[k] ?? ""]), ["proposal_terms", f.proposal_terms ?? ""]]);
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
    <form className="editor" onSubmit={save}>
      <h2 className="detail-title">Settings</h2>
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
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>
    </form>
  );
}
