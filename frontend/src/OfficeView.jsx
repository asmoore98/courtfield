import { useEffect, useState } from "react";
import { api } from "./api";
import HoursBar, { HoursText, statusOf } from "./HoursBar";

const money = (n) =>
  n == null ? "" : n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const pct = (p) => (p == null ? "" : `${Math.round(p * 100)}%`);
const STATUS_WORD = { scheduled: "Scheduled", active: "In progress", complete: "Complete" };
const TONE_WORD = { under: "On track", near: "Close to estimate", over: "Over estimate", none: "No estimate" };

function useLoad(path, deps = []) {
  const [state, set] = useState({ data: null, error: null });
  useEffect(() => {
    let live = true;
    const go = () =>
      api(path)
        .then((data) => live && set({ data, error: null }))
        .catch((e) => live && set((s) => ({ ...s, error: e.message })));
    go();
    const t = setInterval(go, 30000);
    return () => {
      live = false;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

function JobList({ onOpen }) {
  const { data, error } = useLoad("/api/jobs/summary");
  if (error && !data) return <p className="empty">Couldn't load jobs: {error}</p>;
  if (!data) return <p className="empty">Loading jobs…</p>;
  if (!data.length) return <p className="empty">No jobs yet. Jobs you add show their hours against the estimate here.</p>;

  const order = { active: 0, scheduled: 1, complete: 2 };
  const jobs = [...data].sort((a, b) => order[a.status] - order[b.status]);
  return (
    <ul className="joblist">
      {jobs.map((j) => {
        const tone = statusOf(j.hours_used_pct);
        return (
          <li key={j.job_id}>
            <button className="jobrow" onClick={() => onOpen(j.job_id)}>
              <span className="jobrow-head">
                <span className="jobrow-name">{j.job_name}</span>
                <span className={`chip chip-${j.status}`}>
                  {STATUS_WORD[j.status]}
                  {j.crew_on_site > 0 && `, ${j.crew_on_site} on site`}
                </span>
              </span>
              <HoursBar estimated={j.estimated_hours} actual={j.actual_hours} open={j.open_hours} size="lg" />
              <span className="jobrow-foot">
                <HoursText estimated={j.estimated_hours} actual={j.actual_hours} open={j.open_hours} />
                {j.actual_hours + j.open_hours > 0 && <span className={`t-${tone}`}>{TONE_WORD[tone]}</span>}
                <span className="money">
                  Labor {money(j.actual_labor_cost)} of {money(j.estimated_labor_cost)}
                  {j.labor_variance != null && (
                    <b className={j.labor_variance > 0 ? "t-over" : "t-under"}>
                      {j.labor_variance > 0 ? ` ${money(j.labor_variance)} over` : ` ${money(-j.labor_variance)} under`}
                    </b>
                  )}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function JobDetail({ jobId, onBack }) {
  const { data: c } = useLoad(`/api/jobs/${jobId}/costing`, [jobId]);
  const { data: entries } = useLoad(`/api/time?job_id=${jobId}`, [jobId]);
  if (!c) return <p className="empty">Loading job…</p>;

  const sees$ = c.actual_labor_cost != null;
  return (
    <div className="detail">
      <button className="link back" onClick={onBack}>
        All jobs
      </button>
      <h2 className="detail-title">{c.job_name}</h2>
      <div className="detail-figures">
        <div>
          <span className="fig">{Math.round(c.actual_hours + c.open_hours)}</span>
          <span className="fig-label">of {Math.round(c.estimated_hours)} hours used</span>
        </div>
        {sees$ && (
          <div>
            <span className="fig">{money(c.actual_labor_cost)}</span>
            <span className="fig-label">of {money(c.estimated_labor_cost)} labor budget</span>
          </div>
        )}
        <div>
          <span className="fig">{c.crew_on_site}</span>
          <span className="fig-label">on site now</span>
        </div>
      </div>

      <section className="panel">
        <h3>Hours by task</h3>
        <table className="tasktable">
          <thead>
            <tr>
              <th scope="col">Task</th>
              <th scope="col" className="w-bar">
                Hours against estimate
              </th>
              <th scope="col" className="num">Used</th>
              {sees$ && <th scope="col" className="num">Labor</th>}
            </tr>
          </thead>
          <tbody>
            {c.tasks.map((t) => (
              <tr key={t.task_id}>
                <th scope="row">{t.name}</th>
                <td className="w-bar">
                  <HoursBar estimated={t.estimated_hours} actual={t.actual_hours} open={t.open_hours} />
                </td>
                <td className="num">
                  <HoursText estimated={t.estimated_hours} actual={t.actual_hours} open={t.open_hours} />
                  <span className={`sub t-${t.status === "no_estimate" ? "none" : t.status}`}>{pct(t.hours_used_pct)}</span>
                </td>
                {sees$ && (
                  <td className="num">
                    {money(t.actual_labor_cost)}
                    <span className="sub">of {money(t.estimated_labor_cost)}</span>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <h3>Time log</h3>
        {!entries?.length ? (
          <p className="empty">No time logged on this job yet.</p>
        ) : (
          <table className="log">
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col">Crew</th>
                <th scope="col">Task</th>
                <th scope="col" className="num">Hours</th>
              </tr>
            </thead>
            <tbody>
              {entries.slice(0, 60).map((e) => (
                <tr key={e.id}>
                  <td>
                    {new Date(e.clock_in).toLocaleDateString(undefined, { month: "short", day: "numeric" })}{" "}
                    <span className="sub-inline">{new Date(e.clock_in).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
                  </td>
                  <td>{e.worker_name}</td>
                  <td>
                    {e.task_name}
                    {e.off_site && <span className="flag" title="GPS stamp was more than 400 m from the job pin">Off site</span>}
                  </td>
                  <td className="num">{e.hours == null ? <span className="t-near">On the clock</span> : e.hours.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

export default function OfficeView() {
  const [open, setOpen] = useState(null);
  return open ? <JobDetail jobId={open} onBack={() => setOpen(null)} /> : <JobList onOpen={setOpen} />;
}
