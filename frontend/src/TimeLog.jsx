// A job's time log, plus the tools to add, fix and remove time: the GM on
// any job, a crew lead on their own crew's recent time (the server decides
// which entries; see can_fix). Every change needs a reason and is kept in the
// entry's history, and the office sees which ones a crew lead changed.
import { Fragment, useEffect, useState } from "react";
import { api } from "./api";

const pad = (n) => String(n).padStart(2, "0");
const toDate = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const toTime = (iso) => { const d = new Date(iso); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
const toIso = (date, time) => new Date(`${date}T${time}`).toISOString();
const dayLabel = (iso) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
const timeLabel = (iso) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
const ACTION_WORD = { add: "Added by hand", edit: "Corrected", remove: "Removed" };

function describe(snap) {
  if (!snap) return "";
  const out = snap.clock_out ? timeLabel(snap.clock_out) : "on the clock";
  return `${snap.worker} · ${snap.task} · ${dayLabel(snap.clock_in)} ${timeLabel(snap.clock_in)} to ${out}`;
}

function TimeForm({ entry, jobId, tasks, crew: everyone, crewIds, onSaved, onCancel }) {
  const editing = !!entry;
  // A crew lead picks from this job's crew; anyone else (a helper that day) is a tap away.
  const [showAll, setShowAll] = useState(false);
  const crew = crewIds && !showAll ? everyone.filter((c) => crewIds.has(c.id) || c.id === entry?.worker_id) : everyone;
  const today = toDate(new Date().toISOString());
  const [f, setF] = useState(() =>
    editing
      ? {
          worker_id: entry.worker_id,
          task_id: entry.task_id,
          date: toDate(entry.clock_in),
          start: toTime(entry.clock_in),
          end: entry.clock_out ? toTime(entry.clock_out) : "",
          endDate: entry.clock_out ? toDate(entry.clock_out) : toDate(entry.clock_in),
          reason: "",
        }
      : { worker_id: crew[0]?.id ?? "", task_id: tasks[0]?.task_id ?? "", date: today, start: "07:00", end: "15:30", endDate: today, reason: "" }
  );
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value, ...(k === "date" && x.endDate === x.date ? { endDate: e.target.value } : {}) }));

  async function save(e) {
    e.preventDefault();
    setError(null);
    if (!editing && !f.end) return setError("Enter the time they finished.");
    setSaving(true);
    const clock_in = toIso(f.date, f.start);
    const clock_out = f.end ? toIso(f.endDate, f.end) : null;
    try {
      if (editing) {
        const body = { reason: f.reason };
        if (f.worker_id !== entry.worker_id) body.worker_id = f.worker_id;
        if (f.task_id !== entry.task_id) body.task_id = f.task_id;
        // The form shows minutes, so only send a time that was actually changed
        // (otherwise the seconds get cut off and look like a change).
        if (f.date !== toDate(entry.clock_in) || f.start !== toTime(entry.clock_in)) body.clock_in = clock_in;
        const wasEnd = entry.clock_out ? `${toDate(entry.clock_out)} ${toTime(entry.clock_out)}` : "";
        if ((f.end ? `${f.endDate} ${f.end}` : "") !== wasEnd) body.clock_out = clock_out;
        if (Object.keys(body).length === 1) {
          setSaving(false);
          return setError("Nothing changed yet.");
        }
        await api(`/api/time/${entry.id}`, { method: "PATCH", body });
      } else {
        await api("/api/time/office", {
          method: "POST",
          body: { job_id: jobId, task_id: f.task_id, worker_id: f.worker_id, clock_in, clock_out, reason: f.reason },
        });
      }
      onSaved();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  const id = (k) => `tf-${entry?.id ?? "new"}-${k}`;
  return (
    <form className="timeform" onSubmit={save}>
      <h4>{editing ? `Fix time for ${entry.worker_name}` : "Add time"}</h4>
      <div className="tf-grid">
        <label htmlFor={id("worker")}>
          Crew member
          <select id={id("worker")} value={f.worker_id} onChange={set("worker_id")}>
            {crew.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {crewIds && (
            <button type="button" className="link tf-all" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Just this job's crew" : "Someone else helping? Show everyone"}
            </button>
          )}
        </label>
        <label htmlFor={id("task")}>
          Task
          <select id={id("task")} value={f.task_id} onChange={set("task_id")}>
            {tasks.map((t) => (
              <option key={t.task_id} value={t.task_id}>{t.name}</option>
            ))}
          </select>
        </label>
        <label htmlFor={id("date")}>
          Day
          <input id={id("date")} type="date" required value={f.date} max={today} onChange={set("date")} />
        </label>
        <label htmlFor={id("start")}>
          Started
          <input id={id("start")} type="time" required value={f.start} onChange={set("start")} />
        </label>
        <label htmlFor={id("end")}>
          Finished
          <input id={id("end")} type="time" value={f.end} onChange={set("end")} />
        </label>
        {f.end && f.endDate !== f.date && (
          <label htmlFor={id("enddate")}>
            Finished on
            <input id={id("enddate")} type="date" value={f.endDate} onChange={set("endDate")} />
          </label>
        )}
        <label htmlFor={id("reason")} className="tf-reason">
          Reason for the change
          <input
            id={id("reason")}
            required
            minLength={3}
            value={f.reason}
            onChange={set("reason")}
            placeholder={editing ? "e.g. Clocked out late, left at 3:30" : "e.g. Crew lead's phone was dead"}
          />
        </label>
      </div>
      {editing && !entry.clock_out && <p className="help">Leave Finished blank to keep them on the clock.</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="tf-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Cancel</button>
        <button className="btn" disabled={saving}>{saving ? "Saving…" : editing ? "Save correction" : "Add time"}</button>
      </div>
    </form>
  );
}

function RemoveForm({ entry, onDone, onCancel }) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState(null);
  async function remove(e) {
    e.preventDefault();
    try {
      await api(`/api/time/${entry.id}/remove`, { method: "POST", body: { reason } });
      onDone();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form className="timeform" onSubmit={remove}>
      <h4>Remove {entry.worker_name}'s time on {entry.task_name}, {dayLabel(entry.clock_in)}?</h4>
      <p className="help">The entry stops counting toward hours and cost. It stays in the history with your reason.</p>
      <label htmlFor={`rm-${entry.id}`}>
        Reason
        <input id={`rm-${entry.id}`} required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Clocked in on the wrong job" />
      </label>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="tf-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>Keep it</button>
        <button className="btn-danger">Remove time</button>
      </div>
    </form>
  );
}

function History({ entry }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    api(`/api/time/${entry.id}/history`).then(setRows).catch(() => setRows([]));
  }, [entry.id]);
  if (!rows) return <p className="help">Loading history…</p>;
  if (!rows.length) return <p className="help">No changes. Entered from the field.</p>;
  return (
    <ol className="history">
      {rows.map((h, i) => (
        <li key={i}>
          <b>{ACTION_WORD[h.action]}</b> by {h.changed_by}
          {h.by_crew_lead && " (crew lead)"}, {dayLabel(h.changed_at)} {timeLabel(h.changed_at)}
          <span className="h-reason">“{h.reason}”</span>
          {h.before && <span className="h-line">Was: {describe(h.before)}</span>}
          {h.after && h.action !== "add" && <span className="h-line">Now: {describe(h.after)}</span>}
          {h.action === "add" && <span className="h-line">{describe(h.after)}</span>}
        </li>
      ))}
    </ol>
  );
}

export default function TimeLog({ me, jobId, tasks, onChanged, bare = false, crewIds = null }) {
  const [version, setVersion] = useState(0);
  const [showRemoved, setShowRemoved] = useState(false);
  const [entries, setEntries] = useState(null);
  const [crew, setCrew] = useState([]);
  const [open, setOpen] = useState(null); // { kind: "add" | "fix" | "remove" | "history", id? }
  const lead = me.role === "crew_lead";
  const canFix = me.role === "gm" || lead;
  const seesHistory = me.sees_dollars || lead;

  useEffect(() => {
    let live = true;
    const go = () =>
      api(`/api/time?job_id=${jobId}${showRemoved ? "&include_removed=true" : ""}`)
        .then((d) => live && setEntries(d))
        .catch(() => {});
    go();
    const t = setInterval(go, 30000);
    return () => { live = false; clearInterval(t); };
  }, [jobId, showRemoved, version]);
  useEffect(() => {
    if (canFix) api("/api/crew").then(setCrew).catch(() => {});
  }, [canFix]);

  const changed = () => {
    setOpen(null);
    setVersion((v) => v + 1);
    onChanged();
  };
  const toggle = (kind, id) => setOpen((o) => (o?.kind === kind && o?.id === id ? null : { kind, id }));
  const cols = 4 + (canFix || seesHistory ? 1 : 0);

  const Wrap = bare ? "div" : "section";
  return (
    <Wrap className={bare ? "time-log" : "panel"}>
      <div className="panel-head">
        <h3>{lead ? "Your crew's time on this job" : "Time log"}</h3>
        <div className="log-tools">
          {seesHistory && (
            <label className="check">
              <input type="checkbox" checked={showRemoved} onChange={(e) => setShowRemoved(e.target.checked)} />
              Show removed time
            </label>
          )}
          {canFix && (
            <button className="btn-ghost" onClick={() => toggle("add")}>Add time</button>
          )}
        </div>
      </div>
      {open?.kind === "add" && <TimeForm jobId={jobId} tasks={tasks} crew={crew} crewIds={crewIds} onSaved={changed} onCancel={() => setOpen(null)} />}

      {!entries ? (
        <p className="empty">Loading time…</p>
      ) : !entries.length ? (
        <p className="empty">No time logged on this job yet.{canFix ? " Use Add time if hours were missed." : ""}</p>
      ) : bare ? (
        // On a phone: one card per entry instead of a table.
        <ul className="time-cards">
          {entries.slice(0, 80).map((e) => (
            <li key={e.id} className={e.removed ? "is-removed" : ""}>
              <div className="tc-line">
                <b>{e.worker_name}</b>
                <span className="tc-hours">{e.hours == null ? <span className="t-near">On the clock</span> : `${e.hours.toFixed(1)} hrs`}</span>
              </div>
              <div className="tc-line sub">
                <span>
                  {e.task_name} · {dayLabel(e.clock_in)} {timeLabel(e.clock_in)}
                  {e.clock_out ? ` to ${timeLabel(e.clock_out)}` : ""}
                </span>
              </div>
              {(e.removed || e.edited || e.off_site) && (
                <div className="tc-flags">
                  {e.off_site && <span className="flag">Off site</span>}
                  {e.removed ? <span className="flag flag-removed">Removed</span> : e.edited && <span className="flag flag-edited">Corrected</span>}
                </div>
              )}
              <div className="tc-actions">
                {canFix && e.can_fix && !e.removed && (
                  <>
                    <button className="link" onClick={() => toggle("fix", e.id)}>Fix</button>
                    <button className="link" onClick={() => toggle("remove", e.id)}>Remove</button>
                  </>
                )}
                {(e.edited || e.removed || e.changed_by_lead) && (
                  <button className="link" onClick={() => toggle("history", e.id)}>History</button>
                )}
                {!e.can_fix && !e.removed && <span className="sub">Only the office can change this one</span>}
              </div>
              {open?.id === e.id && (
                <div className="tc-open">
                  {open.kind === "fix" && <TimeForm entry={e} jobId={jobId} tasks={tasks} crew={crew} crewIds={crewIds} onSaved={changed} onCancel={() => setOpen(null)} />}
                  {open.kind === "remove" && <RemoveForm entry={e} onDone={changed} onCancel={() => setOpen(null)} />}
                  {open.kind === "history" && <History entry={e} />}
                </div>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div className="table-scroll">
          <table className="log">
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col">Crew</th>
                <th scope="col">Task</th>
                <th scope="col" className="num">Hours</th>
                {cols === 5 && <th scope="col"><span className="sr-only">Actions</span></th>}
              </tr>
            </thead>
            <tbody>
              {entries.slice(0, 80).map((e) => (
                <Fragment key={e.id}>
                  <tr className={e.removed ? "is-removed" : ""}>
                    <td>
                      {dayLabel(e.clock_in)} <span className="sub-inline">{timeLabel(e.clock_in)}{e.clock_out ? `–${timeLabel(e.clock_out)}` : ""}</span>
                    </td>
                    <td>{e.worker_name}</td>
                    <td>
                      {e.task_name}
                      {e.off_site && <span className="flag" title="GPS stamp was more than 400 m from the job pin">Off site</span>}
                      {e.removed ? (
                        <span className="flag flag-removed">Removed</span>
                      ) : (
                        e.edited && <span className="flag flag-edited">Corrected</span>
                      )}
                      {e.changed_by_lead && !lead && <span className="flag flag-lead" title="A crew lead added, fixed or removed this">Changed by crew lead</span>}
                    </td>
                    <td className="num">{e.hours == null ? <span className="t-near">On the clock</span> : e.hours.toFixed(1)}</td>
                    {cols === 5 && (
                      <td className="row-actions">
                        {canFix && e.can_fix && !e.removed && (
                          <>
                            <button className="link" onClick={() => toggle("fix", e.id)}>Fix</button>
                            <button className="link" onClick={() => toggle("remove", e.id)}>Remove</button>
                          </>
                        )}
                        {seesHistory && (e.edited || e.removed || e.changed_by_lead) && (
                          <button className="link" onClick={() => toggle("history", e.id)}>History</button>
                        )}
                      </td>
                    )}
                  </tr>
                  {open?.id === e.id && (
                    <tr className="row-open">
                      <td colSpan={cols}>
                        {open.kind === "fix" && <TimeForm entry={e} jobId={jobId} tasks={tasks} crew={crew} crewIds={crewIds} onSaved={changed} onCancel={() => setOpen(null)} />}
                        {open.kind === "remove" && <RemoveForm entry={e} onDone={changed} onCancel={() => setOpen(null)} />}
                        {open.kind === "history" && <History entry={e} />}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Wrap>
  );
}
