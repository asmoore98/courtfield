import { useEffect, useState } from "react";
import { DEMO, api } from "./api";
import { useScreen } from "./bits";
import JobEditor, { COST_CATEGORIES, EstimateTable } from "./JobEditor";
import TimeLog from "./TimeLog";
import JobMaterials from "./JobMaterials";
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

function JobList({ me, onOpen, onNew }) {
  const { data, error } = useLoad("/api/jobs/summary");
  const newButton = (
    <div className="list-head spread">
      <p className="help">Jobs come from won estimates.{me.creates_jobs && " For a callback or small job with no estimate:"}</p>
      {me.creates_jobs && (
        <button className="btn-ghost" onClick={onNew}>
          New job without an estimate
        </button>
      )}
    </div>
  );
  if (error && !data) return <p className="empty">Couldn't load jobs: {error}</p>;
  if (!data) return <p className="empty">Loading jobs…</p>;
  if (!data.length)
    return (
      <>
        {newButton}
        <p className="empty">No jobs yet. Jobs you add show their hours against the estimate here.</p>
      </>
    );

  const order = { active: 0, scheduled: 1, complete: 2 };
  const jobs = [...data].sort((a, b) => order[a.status] - order[b.status]);
  return (
    <>
    {newButton}
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
                {j.estimate?.margin_pct != null && (
                  <span className={j.estimate.profit < 0 ? "t-over" : j.estimate.margin_pct < 0.15 ? "t-near" : ""}>
                    Est. margin {Math.round(j.estimate.margin_pct * 100)}%
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
    </>
  );
}

const CAT_LABEL = { ...Object.fromEntries(COST_CATEGORIES), equipment: "Equipment rental", subcontractor: "Subcontractor" };
const money2 = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

function EstimatePanel({ jobId, costing, version }) {
  const { data: job } = useLoad(`/api/jobs/${jobId}`, [jobId, version]);
  const est = { ...costing.estimate, hours: costing.estimated_hours };
  const taskName = Object.fromEntries((job?.tasks ?? []).map((t) => [t.id, t.name]));
  const lines = job?.cost_lines ?? [];
  return (
    <section className="panel">
      <h3>Estimate</h3>
      <div className="est-layout">
        <EstimateTable est={est} taxPct={job?.sales_tax_pct ?? 0} />
        <div className="est-lines">
          <h4>Materials and other costs</h4>
          {!lines.length ? (
            <p className="help">No material or other cost lines yet. Add them with Edit job.</p>
          ) : (
            <div className="table-scroll">
              <table className="lines-table">
                <thead>
                  <tr>
                    <th scope="col">Item</th>
                    <th scope="col" className="num">Qty</th>
                    <th scope="col" className="num">Per unit</th>
                    <th scope="col" className="num">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((l) => (
                    <tr key={l.id}>
                      <th scope="row">
                        {l.description}
                        <span className="sub">
                          {CAT_LABEL[l.category]}
                          {l.task_id && taskName[l.task_id] ? ` · ${taskName[l.task_id]}` : ""}
                        </span>
                      </th>
                      <td className="num">{l.quantity} {l.unit}</td>
                      <td className="num">{money2(l.unit_cost)}</td>
                      <td className="num">{money2(l.quantity * l.unit_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const NEXT_STATUS = {
  scheduled: ["active", "Start job"],
  active: ["complete", "Mark complete"],
  complete: ["active", "Reopen job"],
};

function JobDetail({ me, jobId, onBack, onEdit }) {
  const [version, setVersion] = useState(0);
  const [statusError, setStatusError] = useState(null);
  const { data: c } = useLoad(`/api/jobs/${jobId}/costing`, [jobId, version]);
  if (!c) return <p className="empty">Loading job…</p>;

  const sees$ = c.actual_labor_cost != null;
  async function setStatus(status) {
    setStatusError(null);
    try {
      await api(`/api/jobs/${jobId}/status`, { method: "PATCH", body: { status } });
      setVersion((v) => v + 1);
    } catch (e) {
      setStatusError(e.message);
    }
  }
  return (
    <div className="detail">
      <button className="link back" onClick={onBack}>
        All jobs
      </button>
      <div className="detail-head">
        <h2 className="detail-title">{c.job_name}</h2>
        <div className="detail-actions">
          {me.edits_jobs && (
            <button className="btn-ghost" onClick={onEdit}>
              Edit job
            </button>
          )}
          {me.role === "gm" && (
            <button className="btn-ghost" onClick={() => setStatus(NEXT_STATUS[c.status][0])}>
              {NEXT_STATUS[c.status][1]}
            </button>
          )}
        </div>
      </div>
      {statusError && <p className="alert" role="alert">{statusError}</p>}
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
        {sees$ && c.materials_actual_cost != null && c.estimate && (
          <div>
            <span className={`fig ${c.materials_actual_cost > c.estimate.material ? "t-over" : ""}`}>{money(c.materials_actual_cost)}</span>
            <span className="fig-label">of {money(c.estimate.material)} materials used</span>
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

      {sees$ && c.estimate && <EstimatePanel jobId={jobId} costing={c} version={version} />}

      {!DEMO && (
        <section className="panel">
          <h3>Materials for this job</h3>
          <JobMaterials jobId={jobId} me={me} />
        </section>
      )}

      <TimeLog me={me} jobId={jobId} tasks={c.tasks} onChanged={() => setVersion((v) => v + 1)} />
    </div>
  );
}

const SCREEN_KEY = "cf.office.screen";

export default function OfficeView({ me, initial }) {
  // screen: { view: "list" } | { view: "job", id } | { view: "edit", id? }
  // An open job editor is remembered, so switching tabs and coming back lands
  // on the same form (its unsaved work is kept as a draft by the editor).
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const toList = () => setScreen({ view: "list" });
  if (screen.view === "edit")
    return (
      <JobEditor
        jobId={screen.id}
        onDone={(id) => setScreen({ view: "job", id })}
        onCancel={() => (screen.id ? setScreen({ view: "job", id: screen.id }) : toList())}
      />
    );
  if (screen.view === "job")
    return <JobDetail me={me} jobId={screen.id} onBack={toList} onEdit={() => setScreen({ view: "edit", id: screen.id })} />;
  return <JobList me={me} onOpen={(id) => setScreen({ view: "job", id })} onNew={() => setScreen({ view: "edit" })} />;
}
