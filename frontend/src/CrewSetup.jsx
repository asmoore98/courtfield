// The GM's crews: each crew lead's usual people. When a job is sent out,
// picking the crew lead brings their crew along. Someone is on one crew at a
// time; adding them here takes them off their old crew.
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

function CrewEdit({ crew, leadId, people, crews, onSaved, onCancel }) {
  const [lead, setLead] = useState(leadId ?? "");
  const [name, setName] = useState(crew?.name && crew.name !== `${crew.lead_name}'s crew` ? crew.name : "");
  const [picked, setPicked] = useState(() => new Set((crew?.members ?? []).map((m) => m.id)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const hasCrew = new Set(crews.map((c) => c.lead_id));
  const freeLeads = people.filter((p) => p.role === "crew_lead" && (!hasCrew.has(p.id) || p.id === leadId));
  const onCrew = {};
  for (const c of crews) for (const m of c.members) onCrew[m.id] = c;
  const choices = people.filter((p) => p.id !== lead && !(p.role === "crew_lead" && hasCrew.has(p.id)));
  const toggle = (id) => setPicked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  async function save(e) {
    e.preventDefault();
    if (!lead) return setError("Pick the crew lead.");
    setBusy(true);
    setError(null);
    try {
      await api(`/api/crews/${lead}`, { method: "PUT", body: { name: name.trim(), member_ids: [...picked] } });
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }
  return (
    <form className="crew-form" onSubmit={save}>
      <div className="grid">
        <label>
          Crew lead
          <select value={lead} onChange={(e) => setLead(e.target.value)} disabled={!!leadId}>
            <option value="">Pick a crew lead</option>
            {freeLeads.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label>
          Crew name (optional)
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder={lead ? `${people.find((p) => p.id === lead)?.name}'s crew` : "e.g. Crew 1"} />
        </label>
      </div>
      <fieldset className="crew-pick">
        <legend>On the crew</legend>
        <div className="seg">
          {choices.map((p) => {
            const other = onCrew[p.id] && onCrew[p.id].lead_id !== lead ? onCrew[p.id] : null;
            return (
              <button type="button" key={p.id} aria-pressed={picked.has(p.id)} onClick={() => toggle(p.id)}>
                {p.name}
                {other && !picked.has(p.id) && <span className="sub-inline"> ({other.lead_name})</span>}
              </button>
            );
          })}
        </div>
      </fieldset>
      {[...picked].some((id) => onCrew[id] && onCrew[id].lead_id !== lead) && (
        <p className="help t-near">Anyone already on another crew moves to this one.</p>
      )}
      {error && <p className="err">{error}</p>}
      <div className="note-buttons">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={busy}>{busy ? "Saving…" : "Save crew"}</button>
      </div>
    </form>
  );
}

export default function CrewSetup({ people }) {
  const [crews, setCrews] = useState(null);
  const [open, setOpen] = useState(null); // "new" or a lead id
  const [error, setError] = useState(null);
  const load = useCallback(() => api("/api/crews").then(setCrews).catch((e) => setError(e.message)), []);
  useEffect(() => void load(), [load]);
  const field = (people ?? []).filter((p) => p.active && (p.role === "crew" || p.role === "crew_lead"));
  if (!crews) return null;
  const onACrew = new Set(crews.flatMap((c) => [c.lead_id, ...c.members.map((m) => m.id)]));
  const loose = field.filter((p) => !onACrew.has(p.id));
  const saved = () => { setOpen(null); load(); };
  async function remove(c) {
    setError(null);
    try {
      await api(`/api/crews/${c.lead_id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <section className="panel crews-setup">
      <div className="panel-head">
        <h3>Crews</h3>
        {open !== "new" && <button className="btn-ghost" onClick={() => setOpen("new")}>Set up a crew</button>}
      </div>
      <p className="help">
        Each crew lead's usual people. When you send a job out, pick the crew lead and their crew comes with them. You can
        still change who's on it for that one job.
      </p>
      {open === "new" && <CrewEdit people={field} crews={crews} onSaved={saved} onCancel={() => setOpen(null)} />}
      {error && <p className="err">{error}</p>}
      {!crews.length ? (
        <p className="empty">No crews yet.</p>
      ) : (
        <ul className="crew-cards">
          {crews.map((c) => (
            <li key={c.lead_id}>
              <div className="cc-head">
                <b>{c.name}</b>
                <span className="cc-actions">
                  <button className="link" onClick={() => setOpen(open === c.lead_id ? null : c.lead_id)}>Edit</button>
                  <button className="link danger" onClick={() => remove(c)}>Remove</button>
                </span>
              </div>
              <p>
                <span className="sub-inline">Lead:</span> {c.lead_name}
              </p>
              <p>
                <span className="sub-inline">Crew:</span> {c.members.map((m) => m.name).join(", ") || "nobody else yet"}
              </p>
              {open === c.lead_id && (
                <CrewEdit crew={c} leadId={c.lead_id} people={field} crews={crews} onSaved={saved} onCancel={() => setOpen(null)} />
              )}
            </li>
          ))}
        </ul>
      )}
      {loose.length > 0 && <p className="help">Not on a crew: {loose.map((p) => p.name).join(", ")}</p>}
    </section>
  );
}
