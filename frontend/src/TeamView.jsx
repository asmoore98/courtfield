// The GM's people screen: who's on the team, what they do, what their hour
// costs, and who can sign in. Sign-in links are shared by text or email.
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

const ROLES = [
  ["crew", "Crew member", "Clocked in by their crew lead. Doesn't sign in."],
  ["crew_lead", "Crew lead", "Clocks the crew in and out on a phone."],
  ["estimator", "Estimator", "Builds jobs and estimates."],
  ["gm", "General manager", "Everything, including people and time corrections."],
  ["owner", "Owner", "Sees jobs, hours and dollars. Read-only."],
  ["warehouse", "Warehouse", "Materials tools arrive in Phase 2."],
];
const ROLE_LABEL = Object.fromEntries(ROLES.map(([v, l]) => [v, l]));
const SIGNS_IN = new Set(["crew_lead", "estimator", "gm", "owner", "warehouse"]);

function signInStatus(p) {
  if (!p.active) return ["Turned off", "off"];
  if (!p.signs_in) return ["Doesn't sign in", "none"];
  if (!p.has_password) return ["Link sent, not used yet", "wait"];
  if (p.devices) return [`Signed in on ${p.devices} device${p.devices === 1 ? "" : "s"}`, "ok"];
  return ["Signed out", "none"];
}

function InviteLink({ url, name, onClose }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      document.getElementById("invite-url")?.select();
    }
  }
  return (
    <div className="invite-box" role="status">
      <b>Send this sign-in link to {name}</b>
      <p className="help">Text or email it. It works once and expires in 7 days. They'll set their own password.</p>
      <div className="invite-row">
        <input id="invite-url" readOnly value={url} onFocus={(e) => e.target.select()} />
        <button className="btn" onClick={copy}>{copied ? "Copied" : "Copy link"}</button>
      </div>
      <button className="link" onClick={onClose}>Done</button>
    </div>
  );
}

function PersonForm({ person, onSaved, onCancel }) {
  const [f, setF] = useState(() => ({
    name: person?.name ?? "",
    role: person?.role ?? "crew",
    email: person?.email ?? "",
    hourly_cost: person?.hourly_cost ?? "",
  }));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));
  const needsEmail = SIGNS_IN.has(f.role);
  const pid = person?.id ?? "new";

  async function save(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const body = { name: f.name.trim(), role: f.role, email: needsEmail ? f.email.trim() || null : null, hourly_cost: Number(f.hourly_cost || 0) };
    try {
      const r = person
        ? await api(`/api/team/${person.id}`, { method: "PATCH", body })
        : await api("/api/team", { method: "POST", body });
      onSaved(r);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="timeform" onSubmit={save}>
      <h4>{person ? `Edit ${person.name}` : "Add a person"}</h4>
      <div className="tf-grid">
        <label htmlFor={`pf-name-${pid}`}>
          Name
          <input id={`pf-name-${pid}`} required value={f.name} onChange={set("name")} />
        </label>
        <label htmlFor={`pf-role-${pid}`}>
          Role
          <select id={`pf-role-${pid}`} value={f.role} onChange={set("role")}>
            {ROLES.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
        </label>
        <label htmlFor={`pf-cost-${pid}`}>
          Labor cost per hour
          <span className="affix">
            <span aria-hidden="true">$</span>
            <input id={`pf-cost-${pid}`} type="number" inputMode="decimal" min="0" step="0.01" value={f.hourly_cost} onChange={set("hourly_cost")} />
          </span>
        </label>
        {needsEmail && (
          <label htmlFor={`pf-email-${pid}`}>
            Email for signing in
            <input id={`pf-email-${pid}`} type="email" required autoCapitalize="none" value={f.email} onChange={set("email")} />
          </label>
        )}
      </div>
      <p className="help">
        {ROLES.find(([v]) => v === f.role)?.[2]} Labor cost is wage plus payroll taxes and workers' comp; it drives the labor dollars on each job.
      </p>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="tf-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={busy}>{busy ? "Saving…" : person ? "Save" : needsEmail ? "Add and create sign-in link" : "Add person"}</button>
      </div>
    </form>
  );
}

export default function TeamView({ me }) {
  const [people, setPeople] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null); // { kind: "add" | "edit", id? }
  const [invite, setInvite] = useState(null); // { url, name }
  const [showOff, setShowOff] = useState(false);

  const load = useCallback(() => api("/api/team").then(setPeople).catch((e) => setError(e.message)), []);
  useEffect(() => void load(), [load]);

  const saved = (r) => {
    setOpen(null);
    if (r.invite_url) setInvite({ url: r.invite_url, name: r.person.name });
    load();
  };
  const act = async (path, person) => {
    setError(null);
    try {
      saved(await api(path, { method: "POST" }));
    } catch (e) {
      setError(e.message);
    }
  };
  const setActive = async (p, active) => {
    setError(null);
    try {
      await api(`/api/team/${p.id}`, { method: "PATCH", body: { active } });
      load();
    } catch (e) {
      setError(e.message);
    }
  };

  if (!people) return <p className="empty">{error ? `Couldn't load the team: ${error}` : "Loading team…"}</p>;
  const shown = people.filter((p) => showOff || p.active);
  const offCount = people.length - people.filter((p) => p.active).length;

  return (
    <div className="team">
      <div className="detail-head">
        <h2 className="detail-title">Team</h2>
        <div className="detail-actions">
          <button className="btn" onClick={() => setOpen({ kind: "add" })}>Add a person</button>
        </div>
      </div>
      <p className="help">Crew members who don't use the app only need a name and labor cost. Crew leads and office staff sign in with their email.</p>

      {invite && <InviteLink {...invite} onClose={() => setInvite(null)} />}
      {open?.kind === "add" && <PersonForm onSaved={saved} onCancel={() => setOpen(null)} />}
      {error && <p className="alert" role="alert">{error}</p>}

      <section className="panel">
        <div className="panel-head">
          <h3>{people.filter((p) => p.active).length} people</h3>
          {offCount > 0 && (
            <label className="check">
              <input type="checkbox" checked={showOff} onChange={(e) => setShowOff(e.target.checked)} />
              Show {offCount} turned off
            </label>
          )}
        </div>
        <ul className="people">
          {shown.map((p) => {
            const [status, tone] = signInStatus(p);
            const self = p.id === me.id;
            return (
              <li key={p.id} className={p.active ? "" : "is-off"}>
                <div className="person">
                  <div className="person-main">
                    <span className="person-name">{p.name}{self && <span className="you"> (you)</span>}</span>
                    <span className="person-meta">
                      {ROLE_LABEL[p.role]}
                      {p.email && <> · {p.email}</>}
                    </span>
                  </div>
                  <span className="person-cost">${p.hourly_cost.toFixed(2)}<span className="sub-inline"> /hr</span></span>
                  <span className={`signin-status s-${tone}`}>{status}</span>
                </div>
                <div className="person-actions">
                  <button className="link" onClick={() => setOpen(open?.id === p.id ? null : { kind: "edit", id: p.id })}>Edit</button>
                  {p.active && p.signs_in && (
                    <button className="link" onClick={() => act(`/api/team/${p.id}/invite`, p)}>
                      {p.has_password ? "New password link" : "New sign-in link"}
                    </button>
                  )}
                  {p.active && p.devices > 0 && !self && (
                    <button className="link" onClick={() => act(`/api/team/${p.id}/signout`, p)}>Sign out all devices</button>
                  )}
                  {!self && (p.active ? (
                    <button className="link danger" onClick={() => setActive(p, false)}>Turn off</button>
                  ) : (
                    <button className="link" onClick={() => setActive(p, true)}>Turn back on</button>
                  ))}
                </div>
                {open?.kind === "edit" && open.id === p.id && <PersonForm person={p} onSaved={saved} onCancel={() => setOpen(null)} />}
              </li>
            );
          })}
        </ul>
      </section>
      <p className="help">Turning someone off ends their sign-ins and takes them off the crew list. Their past hours stay on every job.</p>
    </div>
  );
}
