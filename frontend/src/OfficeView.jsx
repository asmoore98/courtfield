import { useEffect, useState } from "react";
import MaterialRequests from "./MaterialRequests";
import MaterialCheck from "./MaterialCheck";
import { amountText, fmt } from "./qty";
import { DEMO, api } from "./api";
import { useScreen } from "./bits";
import JobEditor, { COST_CATEGORIES, EstimateTable } from "./JobEditor";
import TimeLog from "./TimeLog";
import JobMaterials from "./JobMaterials";
import HoursBar, { HoursText, Pace, statusOf } from "./HoursBar";
import CrewForm, { crewLine, fmtDay } from "./CrewForm";
import Photos from "./Photos";
import { ActivityList, NoteAction, fmtWhen } from "./bits";

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

// Won estimates that don't have a job yet: one tap turns each into a job.
function WonEstimates({ me, onOpen }) {
  const [won, setWon] = useState([]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(null); // the estimate being made into a job and sent out
  const assigns = me.role === "gm" || me.role === "pm";
  useEffect(() => {
    if (!me.estimates || DEMO) return;
    api("/api/estimates?status=won")
      .then((rows) => setWon(rows.filter((e) => !e.job_id)))
      .catch(() => {});
  }, [me.estimates]);
  if (!won.length) return null;
  async function make(e, crew) {
    setError(null);
    setBusy(e.id);
    try {
      const { job_id } = await api(`/api/estimates/${e.id}/create-job`, { method: "POST", ...(crew ? { body: crew } : {}) });
      onOpen(job_id);
    } catch (err) {
      setError(err.message);
      setBusy(null);
      throw err;
    }
  }
  return (
    <section className="panel won-waiting">
      <h3>Jobs ready to be scheduled</h3>
      <p className="help">
        These estimates were won. {assigns ? "Make each one a job: pick the start date and the crew, and it goes to the crew lead's phone." : "The GM or a PM makes each one a job and sends it to a crew."}
      </p>
      <ul className="row-list">
        {won.map((e) => (
          <li key={e.id}>
            <div className="row-btn">
              <span className="row-main">
                <b>{e.name}</b>
                <span className="sub">
                  {e.number} · {e.client_name} · {money(e.price)}
                </span>
              </span>
              {sending !== e.id && (
                <button className="btn" onClick={() => (assigns ? setSending(e.id) : make(e).catch(() => {}))} disabled={busy === e.id}>
                  {busy === e.id ? "Creating…" : assigns ? "Schedule it" : "Create job"}
                </button>
              )}
            </div>
            {sending === e.id && (
              <CrewForm
                submitLabel="Create the job and send it out"
                busyLabel="Creating…"
                note="Pick the start date and the crew. You can leave the crew for later; it waits under Not sent to a crew yet."
                onCancel={() => setSending(null)}
                onSubmit={(crew) => make(e, crew)}
              />
            )}
          </li>
        ))}
      </ul>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}

function JobList({ me, onOpen, onNew }) {
  const { data, error } = useLoad("/api/jobs/summary");
  const newButton = (
    <>
    <WonEstimates me={me} onOpen={onOpen} />
    <div className="list-head spread">
      <p className="help">
        Jobs come from won estimates.
        {me.creates_jobs && " Work that never had an estimate, like a warranty callback or a quick patch, can be added here without one:"}
      </p>
      {me.creates_jobs && (
        <button className="btn-ghost" onClick={onNew}>
          Add a job with no estimate
        </button>
      )}
    </div>
    </>
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

  // In progress first, then what's starting soonest, then jobs nobody's been
  // sent yet; finished jobs fold away at the bottom.
  const byStart = (a, b) => (a.start_date ?? "9999") < (b.start_date ?? "9999") ? -1 : 1;
  const groups = [
    ["In progress", data.filter((j) => j.status === "active").sort(byStart)],
    ["Scheduled", data.filter((j) => j.status === "scheduled" && j.crew_lead_name).sort(byStart)],
    ["Not sent to a crew yet", data.filter((j) => j.status === "scheduled" && !j.crew_lead_name)],
  ];
  const done = data.filter((j) => j.status === "complete");
  const row = (j) => {
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
              {j.on_clock?.length > 0 && <span className="jobrow-onclock">{onClockLine(j.on_clock)}</span>}
              <span className={`jobrow-crew${j.crew_lead_name ? "" : " t-near"}`}>
                {crewLine(j)}
                {j.open_problems > 0 && (
                  <b className="t-over">
                    {" "}
                    · {j.open_problems} problem{j.open_problems > 1 ? "s" : ""} from the site
                  </b>
                )}
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
  };
  return (
    <>
    {newButton}
    {groups.map(([title, list]) =>
      list.length ? (
        <section key={title} className="job-group">
          <h3 className="group-title">
            {title} <span className="count">{list.length}</span>
          </h3>
          <ul className="joblist">{list.map(row)}</ul>
        </section>
      ) : null
    )}
    {done.length > 0 && (
      <details className="job-group done-group">
        <summary className="group-title">
          Complete <span className="count">{done.length}</span>
        </summary>
        <ul className="joblist">{done.map(row)}</ul>
      </details>
    )}
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
                          {l.category === "equipment" ? (l.in_house ? "In-house equipment" : "Equipment rental") : CAT_LABEL[l.category]}
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

// The crew lead starts a job on site (pin, site walk, clock in). The GM can
// still mark a job in progress by hand, e.g. one that has no crew lead.
const NEXT_STATUS = {
  scheduled: ["active", "Mark in progress"],
  active: ["complete", "Mark complete"],
  complete: ["active", "Reopen job"],
};

// What the crew lead found on site, the crew and start date, photos and history.
function FieldPanel({ me, jobId, c, onChanged }) {
  const [editing, setEditing] = useState(false);
  const [n, setN] = useState(0);
  const { data } = useLoad(`/api/jobs/${jobId}/reports`, [jobId, n]);
  const assigns = me.role === "gm" || me.role === "pm";
  const reports = data?.reports ?? [];
  const open = reports.filter((r) => r.kind === "problem" && !r.resolved_at);
  const reload = () => {
    setN((x) => x + 1);
    onChanged();
  };
  return (
    <>
      <section className="panel">
        <div className="panel-head">
          <h3>Crew and start date</h3>
          {assigns && !editing && (
            <button className="link" onClick={() => setEditing(true)}>
              {c.crew_lead_name ? "Change" : "Send to a crew"}
            </button>
          )}
        </div>
        {editing ? (
          <CrewForm
            initial={c}
            submitLabel={c.crew_lead_name ? "Save" : "Send it out"}
            onCancel={() => setEditing(false)}
            onSubmit={(body) =>
              api(`/api/jobs/${jobId}/crew`, { method: "PUT", body }).then(() => {
                setEditing(false);
                reload();
              })
            }
          />
        ) : (
          <dl className="facts">
            <div>
              <dt>Crew lead</dt>
              <dd>{c.crew_lead_name ?? <span className="t-near">Not sent to a crew yet</span>}</dd>
            </div>
            <div>
              <dt>Crew</dt>
              <dd>{(c.crew_members ?? []).map((m) => m.name).join(", ") || "—"}</dd>
            </div>
            <div>
              <dt>Start date</dt>
              <dd>{c.start_date ? fmtDay(c.start_date) : "—"}</dd>
            </div>
            <div>
              <dt>On site</dt>
              <dd>{c.started_at ? `Started ${fmtWhen(c.started_at)}` : "Not started yet"}</dd>
            </div>
          </dl>
        )}
      </section>

      <section className={`panel${open.length ? " has-problems" : ""}`}>
        <h3>
          From the site{open.length > 0 && <span className="count warn">{open.length} to handle</span>}
        </h3>
        {!reports.length ? (
          <p className="help">Nothing reported yet. Problems the crew lead finds on site (damage, anything different from the estimate) show up here.</p>
        ) : (
          <ul className="reports">
            {reports.map((r) => (
              <li key={r.id} className={r.kind === "problem" && !r.resolved_at ? "is-open" : ""}>
                <p className="r-text">
                  <b>{r.kind === "problem" ? (r.resolved_at ? "Problem (handled)" : "Problem") : "Note"}:</b> {r.text}
                </p>
                <p className="sub">
                  {r.by} · {fmtWhen(r.at)}
                </p>
                {r.resolved_at && (
                  <p className="r-resolved">
                    Handled by {r.resolved_by} {fmtWhen(r.resolved_at)}: {r.resolution}
                  </p>
                )}
                {assigns && r.kind === "problem" && !r.resolved_at && (
                  <NoteAction
                    label="Mark handled"
                    prompt="What was done about it?"
                    placeholder="e.g. Called the client, change order sent"
                    onSubmit={(resolution) => api(`/api/jobs/${jobId}/reports/${r.id}/resolve`, { method: "POST", body: { resolution } }).then(reload)}
                  />
                )}
              </li>
            ))}
          </ul>
        )}
        <Photos kind="job" id={jobId} title="Site photos" />
      </section>

      <MaterialRequests jobId={jobId} canHandle={assigns} onChanged={reload} hideEmpty />

      <ActivityList items={data?.activity} />
    </>
  );
}

// Who's on the clock right now, grouped by task. The page refreshes it every 30 seconds.
const since = (iso) => {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso)) / 60000));
  const t = new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return `since ${t} (${mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)} h ${String(mins % 60).padStart(2, "0")}`})`;
};

function byTask(onClock) {
  const groups = new Map();
  for (const e of onClock ?? []) groups.set(e.task, [...(groups.get(e.task) ?? []), e]);
  return [...groups.entries()];
}

// "Color coats: Luis · Fence: Tyler, Andre" for the job list.
export const onClockLine = (onClock) =>
  byTask(onClock).map(([task, people]) => `${task}: ${people.map((p) => p.worker.split(" ")[0]).join(", ")}`).join(" · ");

function OnTheClock({ c }) {
  const groups = byTask(c.on_clock);
  return (
    <section className="panel on-clock">
      <h3>
        On the clock now
        {c.on_clock?.length > 0 && <span className="chip chip-active">{c.on_clock.length} {c.on_clock.length === 1 ? "person" : "people"}</span>}
      </h3>
      {!groups.length ? (
        <p className="help">Nobody on the clock on this job right now.</p>
      ) : (
        <ul className="oc-groups">
          {groups.map(([task, people]) => (
            <li key={task}>
              <b className="oc-task">{task}</b>
              <ul className="oc-people">
                {people.map((p) => (
                  <li key={p.worker_id}>
                    {p.worker} <span className="sub-inline">{since(p.since)}</span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// How far along the crew lead says a task is, how the hours compare, and photos.
function TaskDone({ t }) {
  const [photos, setPhotos] = useState(false);
  if (!t.progress_pct) return null;
  return (
    <span className="task-done">
      <span className={`chip chip-${t.progress_pct === 100 ? "done" : "active"}`}>
        {t.progress_pct === 100 ? "Done" : `${t.progress_pct}% done`}
      </span>
      <Pace pct={t.progress_pct} estimated={t.estimated_hours} used={t.actual_hours + t.open_hours} />
      {t.progress_note && <span className="sub">{t.progress_note}</span>}
      <button className="link" onClick={() => setPhotos((v) => !v)} aria-expanded={photos}>
        {photos ? "Hide photos" : "Photos"}
      </button>
      {photos && <Photos kind="task" id={t.task_id} canAdd={false} title="Photos of the work" />}
    </span>
  );
}

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
          {me.role === "gm" && !(c.status === "scheduled" && c.crew_lead_name) && (
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

      {(c.status === "active" || c.on_clock?.length > 0) && <OnTheClock c={c} />}

      {!DEMO && <FieldPanel me={me} jobId={jobId} c={c} onChanged={() => setVersion((v) => v + 1)} />}

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
            {c.tasks.map((t) =>
              t.kind === "sub" ? (
                <tr key={t.task_id} className="sub-task-row">
                  <th scope="row">
                    {t.name}
                    <span className="sub">Done by a sub</span>
                  </th>
                  <td className="w-bar sub-inline">No crew hours: the sub does this work</td>
                  <td className="num">—</td>
                  {sees$ && (
                    <td className="num">
                      {money(t.sub_price ?? 0)}
                      <span className="sub">sub price</span>
                    </td>
                  )}
                </tr>
              ) : (
              <tr key={t.task_id}>
                <th scope="row">
                  {t.name}
                  {amountText(t) && <span className="sub">{amountText(t)}</span>}
                  {t.crew_size > 1 && t.estimated_hours > 0 && (
                    <span className="sub">
                      {t.crew_size} people × {fmt(t.estimated_hours / t.crew_size, 1)} hrs
                    </span>
                  )}
                  <TaskDone t={t} />
                </th>
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
              )
            )}
          </tbody>
        </table>
      </section>

      {sees$ && c.estimate && <EstimatePanel jobId={jobId} costing={c} version={version} />}

      {!DEMO && (
        <section className="panel">
          <h3>Materials for this job</h3>
          <MaterialCheck jobId={jobId} kind="on_site" canCheck={false} />
          <JobMaterials jobId={jobId} me={me} />
        </section>
      )}

      <TimeLog me={me} jobId={jobId} tasks={c.tasks} onChanged={() => setVersion((v) => v + 1)} />
    </div>
  );
}

const SCREEN_KEY = "cf.office.screen";

export default function OfficeView({ me, go, initial }) {
  // screen: { view: "list" } | { view: "job", id } | { view: "edit", id? }
  // An open job editor is remembered, so switching tabs and coming back lands
  // on the same form (its unsaved work is kept as a draft by the editor).
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const toList = () => setScreen({ view: "list" });
  if (screen.view === "edit")
    return (
      <JobEditor
        me={me}
        go={go}
        jobId={screen.id}
        onDone={(id) => setScreen({ view: "job", id })}
        onCancel={() => (screen.id ? setScreen({ view: "job", id: screen.id }) : toList())}
      />
    );
  if (screen.view === "job")
    return <JobDetail me={me} jobId={screen.id} onBack={toList} onEdit={() => setScreen({ view: "edit", id: screen.id })} />;
  return <JobList me={me} onOpen={(id) => setScreen({ view: "job", id })} onNew={() => setScreen({ view: "edit" })} />;
}
