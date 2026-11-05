// Sending a job out to the field: who runs it, who's on the crew, when it
// starts. The GM and PMs use it when they make the job from a won estimate,
// and on the job page to change it. Picking the crew lead brings their usual
// crew (set up on the Team tab); it can still be changed for this job.
import { useEffect, useState } from "react";
import { api } from "./api";

let crewCache = null;

export function useCrews() {
  const [crews, setCrews] = useState(null);
  useEffect(() => {
    api("/api/crews").then(setCrews).catch(() => setCrews([]));
  }, []);
  return crews;
}

export function useCrewList() {
  const [list, setList] = useState(crewCache);
  useEffect(() => {
    if (crewCache) return;
    api("/api/crew")
      .then((r) => setList((crewCache = r)))
      .catch(() => setList([]));
  }, []);
  return list;
}

export const fmtDay = (d) =>
  d ? new Date(`${d}T12:00:00`).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "";

// A moment (UTC from the server) as the day it was here: "Thu, Nov 5".
export const fmtLocalDay = (iso) =>
  iso ? new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" }) : "";

export default function CrewForm({ initial, submitLabel, busyLabel = "Saving…", onSubmit, onCancel, note }) {
  const people = useCrewList();
  const crews = useCrews();
  const [lead, setLead] = useState(initial?.crew_lead_id ?? "");
  const [crew, setCrew] = useState(() => new Set((initial?.crew_members ?? []).map((c) => c.id)));
  const [start, setStart] = useState(initial?.start_date ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const leads = (people ?? []).filter((p) => p.role === "crew_lead");
  const usual = crews?.find((c) => c.lead_id === lead);
  const usualIds = new Set((usual?.members ?? []).map((m) => m.id));
  // Their usual crew first, then everyone else.
  const others = (people ?? []).filter((p) => p.id !== lead).sort((a, b) => usualIds.has(b.id) - usualIds.has(a.id));
  const offToday = [...usualIds].filter((id) => !crew.has(id)).length;
  const extras = [...crew].filter((id) => !usualIds.has(id)).length;
  function pickLead(id) {
    setLead(id);
    const c = crews?.find((x) => x.lead_id === id);
    if (c) setCrew(new Set(c.members.map((m) => m.id)));
  }
  const toggle = (id) =>
    setCrew((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  async function go(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await onSubmit({ crew_lead_id: lead || null, crew_ids: [...crew].filter((id) => id !== lead), start_date: start || null });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form className="crew-form" onSubmit={go}>
      {note && <p className="help">{note}</p>}
      <div className="grid">
        <label>
          Start date
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          Crew lead
          <select value={lead} onChange={(e) => pickLead(e.target.value)}>
            <option value="">{people ? "Not sent out yet" : "Loading the team…"}</option>
            {leads.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      {people && !leads.length && <p className="help t-near">No crew leads on the team yet. Add them on the Team tab.</p>}
      {lead && usual && (
        <p className="help crew-usual">
          <b>{usual.name}:</b> {usual.members.map((m) => m.name).join(", ") || "nobody else yet"}.
          {(offToday > 0 || extras > 0)
            ? ` For this job: ${[offToday && `${offToday} off`, extras && `${extras} extra`].filter(Boolean).join(", ")}.`
            : " Tap below to take someone off or add a helper for this job."}
        </p>
      )}
      {lead && crews && !usual && (
        <p className="help">This crew lead doesn't have a usual crew yet. Set one up on the Team tab, or pick people below.</p>
      )}
      {others.length > 0 && (
        <fieldset className="crew-pick">
          <legend>On the crew</legend>
          <div className="seg">
            {others.map((p) => (
              <button type="button" key={p.id} aria-pressed={crew.has(p.id)} onClick={() => toggle(p.id)}
                className={usualIds.size && !usualIds.has(p.id) ? "not-usual" : undefined}>
                {p.name}
                {p.role === "crew_lead" && <span className="sub-inline"> (lead)</span>}
              </button>
            ))}
          </div>
        </fieldset>
      )}
      {error && <p className="err">{error}</p>}
      <div className="note-buttons">
        {onCancel && (
          <button type="button" className="btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button className="btn" disabled={busy}>
          {busy ? busyLabel : submitLabel}
        </button>
      </div>
    </form>
  );
}

// "Marco Diaz's crew · starts Mon, Nov 16"
export function crewLine(j) {
  if (!j.crew_lead_name) return j.start_date ? `Starts ${fmtDay(j.start_date)} · no crew yet` : "Not sent to a crew yet";
  const n = (j.crew_members ?? []).length;
  const when = j.started_at ? ` · started ${fmtLocalDay(j.started_at)}` : j.start_date ? ` · starts ${fmtDay(j.start_date)}` : "";
  return `${j.crew_lead_name}${n ? ` + ${n}` : ""}${when}`;
}
