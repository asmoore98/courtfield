import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { amountText, fmt } from "./qty";
import { DEMO, api, safeGet, safeSet } from "./api";
import { getPosition, useFieldTime } from "./fieldStore";
import HoursBar, { HoursText, Pace } from "./HoursBar";
import MaterialCheck from "./MaterialCheck";
import InstallHint from "./InstallHint";
import JobMaterials from "./JobMaterials";
import { useLocationSharing } from "./locationShare";
import Photos from "./Photos";
import { crewLine, fmtDay, fmtLocalDay } from "./CrewForm";
import TimeLog from "./TimeLog";
import { fmtWhen, noEnterSubmit } from "./bits";

const JOBS_KEY = "cf.jobs";
const CREW_KEY = "cf.crew";
const JOB_KEY = "cf.job";

function useCached(key, path) {
  const [data, setData] = useState(() => safeGet(key, []));
  const [loaded, setLoaded] = useState(false); // heard from the server (or gave up) at least once
  const load = useCallback(async () => {
    try {
      const d = await api(path);
      setData(d);
      safeSet(key, d);
    } catch {}
    setLoaded(true);
  }, [key, path]);
  useEffect(() => void load(), [load]);
  return [data, load, loaded];
}

const NOTICE_KEY = "cf.locNotice";

// One-time notice, kept on the server as a record that the crew lead was told.
function LocationNotice({ me, onDone }) {
  const [busy, setBusy] = useState(false);
  async function ok() {
    setBusy(true);
    safeSet(NOTICE_KEY, true);
    try {
      await api("/api/me/location-notice", { method: "POST" });
    } catch {} // offline: sent again next time the app opens
    onDone();
  }
  return (
    <section className="panel loc-notice" aria-labelledby="loc-notice-h">
      <h2 id="loc-notice-h">Location while your crew is on the clock</h2>
      <p>
        While anyone you clocked in is on the clock, this app sends this phone's location to the office every few minutes
        while it's open. The office uses it to see which job each crew is at and to split the day into time on the job
        and travel. It stops as soon as everyone you clocked in is clocked out.
      </p>
      <p className="help">Your phone will ask to allow location for this app. Choose Allow.</p>
      <button className="btn" onClick={ok} disabled={busy}>Got it</button>
    </section>
  );
}

function LocationStatus({ share, active }) {
  if (share.permission === "denied" || share.permission === "unsupported") {
    return (
      <p className="alert loc-alert" role="alert">
        Location is off for this app, so the office can't see where the crew is or how much was travel. Turn on Location
        for this site in your phone's settings, then reopen the app.
      </p>
    );
  }
  if (!active) return null;
  return (
    <p className="loc-status">
      <span className="loc-dot" aria-hidden="true" />
      Sharing location with the office while your crew is on the clock
      {share.lastAt && <span className="sub-inline"> · updated {share.lastAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>}
    </p>
  );
}

function useTick(ms) {
  const [, set] = useState(0);
  useEffect(() => {
    const t = setInterval(() => set((n) => n + 1), ms);
    return () => clearInterval(t);
  }, [ms]);
}

function elapsed(fromIso) {
  const mins = Math.max(0, Math.round((Date.now() - new Date(fromIso)) / 60000));
  return mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)} h ${String(mins % 60).padStart(2, "0")}`;
}

function SyncStatus({ online, pendingCount, lastSync, onSync }) {
  let text = "All time synced";
  let tone = "ok";
  if (!online) {
    text = pendingCount ? `No signal. ${pendingCount} saved on this phone` : "No signal. Changes save to this phone";
    tone = "warn";
  } else if (pendingCount) {
    text = `Syncing ${pendingCount}…`;
    tone = "busy";
  }
  return (
    <button className={`sync sync-${tone}`} onClick={onSync} title={lastSync ? `Last synced ${lastSync.toLocaleTimeString()}` : ""}>
      <span className="sync-dot" aria-hidden="true" />
      {text}
    </button>
  );
}

export default function FieldView({ me }) {
  const [showMats, setShowMats] = useState(false);
  const [jobs, reloadJobs, jobsLoaded] = useCached(JOBS_KEY, "/api/jobs");
  const [crew] = useCached(CREW_KEY, "/api/crew");
  const [jobId, setJobId] = useState(() => safeGet(JOB_KEY));
  const [selected, setSelected] = useState(new Set());
  const [costing, setCosting] = useState(null);
  const [working, setWorking] = useState(false);
  const field = useFieldTime(me?.id);
  useTick(30000);
  const [noticed, setNoticed] = useState(() => DEMO || !!me?.location_notice_at || !!safeGet(NOTICE_KEY));
  useEffect(() => {
    // Told while offline: make sure the server has the record.
    if (!DEMO && me && !me.location_notice_at && safeGet(NOTICE_KEY)) api("/api/me/location-notice", { method: "POST" }).catch(() => {});
  }, [me]);
  const share = useLocationSharing({ enabled: !DEMO && noticed, active: field.myCrewOnClock, canFlush: field.pendingCount === 0 });
  const [pinMsg, setPinMsg] = useState(null);
  useEffect(() => setPinMsg(null), [jobId]);
  async function pinHere() {
    setPinMsg("Finding this phone's location…");
    const pos = await getPosition(15000);
    if (!pos) return setPinMsg("Couldn't get a location. Check that Location is on for this app and try again.");
    try {
      await api(`/api/jobs/${jobId}/site`, { method: "POST", body: pos });
      await reloadJobs();
      setPinMsg("Site pin set. Time here now counts as on the job.");
    } catch (e) {
      setPinMsg(e.status === 0 ? "No signal. Try again once you have a connection." : e.message);
    }
  }

  const job = jobs.find((j) => j.id === jobId) ?? null;
  useEffect(() => safeSet(JOB_KEY, jobId), [jobId]);
  const [showAll, setShowAll] = useState(false); // everyone on the team, not just this job's crew

  const loadCosting = useCallback(async () => {
    if (!jobId) return;
    try {
      setCosting(await api(`/api/jobs/${jobId}/costing`));
    } catch {}
  }, [jobId]);
  useEffect(() => {
    loadCosting();
    const t = setInterval(loadCosting, 30000);
    return () => clearInterval(t);
  }, [loadCosting, field.lastSync]);

  const taskName = useMemo(() => {
    const m = {};
    for (const j of jobs) for (const t of j.tasks) m[t.id] = { task: t.name, job: j.name, jobId: j.id };
    return m;
  }, [jobs]);

  const toggle = (id) =>
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const selectedIds = [...selected];
  const selectedOnClock = selectedIds.filter((id) => field.openFor(id));
  const shownCount = useRef(0); // keep the label steady while the bar slides away
  if (selectedOnClock.length) shownCount.current = selectedOnClock.length;

  async function run(action) {
    setWorking(true);
    try {
      await action();
      setSelected(new Set());
    } finally {
      setWorking(false);
    }
  }

  // Not started yet: the crew sent to this job is picked to clock in.
  const notStarted = job && !job.started_at && job.status !== "active";
  useEffect(() => {
    if (!notStarted) return;
    const ids = [job.crew_lead_id, ...(job.crew_members ?? []).map((m) => m.id)].filter(Boolean);
    setSelected(new Set(ids.filter((id) => crew.some((c) => c.id === id))));
  }, [jobId, notStarted, crew.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!job) return <JobPicker me={me} jobs={jobs} loaded={jobsLoaded} onOpen={setJobId} onRefresh={reloadJobs} />;
  const started = !!job.started_at || job.status === "active";
  // This job's crew first; anyone else on the team is a tap away.
  const onJob = new Set([job.crew_lead_id, ...(job.crew_members ?? []).map((m) => m.id)].filter(Boolean));
  const assigned = onJob.size > 0;
  const shownCrew = assigned && !showAll ? crew.filter((c) => onJob.has(c.id) || field.openFor(c.id)?.job_id === jobId) : crew;

  const costByTask = Object.fromEntries((costing?.tasks ?? []).map((t) => [t.task_id, t]));
  const crewName = (id) => crew.find((c) => c.id === id)?.name ?? "A crew member";

  return (
    <div className="field">
      <InstallHint />
      <div className="field-top">
        <button className="link back" onClick={() => setJobId(null)}>
          {me.role === "crew_lead" ? "Your jobs" : "All open jobs"}
        </button>
        <SyncStatus {...field} onSync={field.sync} />
      </div>
      <div className="field-job">
        <h2 className="detail-title">{job.name}</h2>
        <p className="detail-sub">
          {job.address && (
            <a href={job.lat != null ? `https://www.google.com/maps/search/?api=1&query=${job.lat},${job.lng}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(job.address)}`} target="_blank" rel="noopener noreferrer">
              {job.address}
            </a>
          )}
          {job.started_at ? ` · Started ${fmtLocalDay(job.started_at)}` : job.start_date ? ` · Starts ${fmtDay(job.start_date)}` : ""}
        </p>
      </div>

      {!noticed && <LocationNotice me={me} onDone={() => setNoticed(true)} />}
      {noticed && !DEMO && <LocationStatus share={share} active={field.myCrewOnClock} />}
      {!started && !DEMO && (
        <OnSite
          job={job}
          crew={shownCrew}
          selected={selected}
          toggle={toggle}
          setSelected={setSelected}
          onShowAll={assigned ? () => setShowAll((v) => !v) : null}
          showAll={showAll}
          onStarted={async (started) => {
            await reloadJobs();
            const setup = started.tasks.find((t) => t.name === SETUP_TASK);
            if (setup && selected.size) await run(() => field.startTask([...selected], jobId, setup.id));
          }}
        />
      )}

      {job.started_at && !job.site_walk_at && !DEMO && (
        <SiteWalk job={job} costByTask={costByTask} onDone={reloadJobs} />
      )}

      {started && !DEMO && job && job.lat == null && (
        <div className="pin-ask">
          <span>This job has no site pin, so on-the-job and travel time can't be worked out.</span>
          <button className="btn-ghost" onClick={pinHere}>Set the site pin here</button>
          {pinMsg && <span className="sub">{pinMsg}</span>}
        </div>
      )}
      {!DEMO && job && job.lat != null && pinMsg && <p className="help pin-done" role="status">{pinMsg}</p>}

      {field.problems.map((p) => (
        <div className="alert" role="alert" key={p.id}>
          <span>
            Time for {crewName(p.worker_id)} wasn't saved: {p.reason}.
          </span>
          <button onClick={() => field.dismissProblem(p.id)}>Dismiss</button>
        </div>
      ))}

      {(started || DEMO) && (
      <>
      <section className="panel">
        <div className="panel-head">
          <h2>Crew</h2>
          <button className="link" onClick={() => setSelected(selected.size === shownCrew.length ? new Set() : new Set(shownCrew.map((c) => c.id)))}>
            {selected.size === shownCrew.length ? "Clear" : "Select all"}
          </button>
        </div>
        <ul className="crew">
          {shownCrew.map((c) => {
            const cur = field.openFor(c.id);
            const where = cur ? taskName[cur.task_id] : null;
            const elsewhere = cur && cur.job_id !== jobId;
            return (
              <li key={c.id}>
                <label className={`crew-row ${selected.has(c.id) ? "is-picked" : ""}`}>
                  <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
                  <span className="crew-name">{c.name}</span>
                  {cur ? (
                    <span className={`on-task ${elsewhere ? "elsewhere" : ""}`}>
                      {elsewhere ? `${where?.job ?? "Another job"}` : where?.task ?? "On the clock"}
                      <span className="since">{elapsed(cur.clock_in)}</span>
                    </span>
                  ) : (
                    <span className="off">Off the clock</span>
                  )}
                </label>
              </li>
            );
          })}
        </ul>
        {assigned && (
          <button className="link" onClick={() => setShowAll((v) => !v)}>
            {showAll ? "Just this job's crew" : "Someone else helping today? Show everyone"}
          </button>
        )}
      </section>

      {(DEMO || !job.started_at || job.site_walk_at) && (
      <section className="panel">
        <div className="panel-head">
          <h2>Tasks</h2>
          <span className="hint">
            {selected.size ? `Tap a task to put ${selected.size} on it` : "Pick crew above, then tap a task"}
          </span>
        </div>
        <p className="help tasks-help">
          Hours are labor hours: everyone's time added up. 3 people for 8 hours is 24 hours on that task.
        </p>
        <ul className="tasks">
          {job?.tasks.filter((t) => t.kind !== "sub").map((t) => {
            const c = costByTask[t.id];
            const here = crew.filter((w) => field.openFor(w.id)?.task_id === t.id).length;
            return (
              <li key={t.id} className={t.progress === "done" ? "is-done" : undefined}>
                <button
                  className="task"
                  disabled={!selected.size || working}
                  onClick={() => run(() => field.startTask(selectedIds, jobId, t.id))}
                >
                  <span className="task-line">
                    <span className="task-name">
                      {t.name}
                      {amountText(t) && <span className="task-qty"> · {amountText(t)}</span>}
                    </span>
                    {c && <HoursText estimated={c.estimated_hours} actual={c.actual_hours} open={c.open_hours} />}
                  </span>
                  {c && <HoursBar estimated={c.estimated_hours} actual={c.actual_hours} open={c.open_hours} />}
                  <span className="task-plan">{planText(t)}</span>
                  {here > 0 && <span className="here">{here} on it now</span>}
                </button>
                {!DEMO && t.name !== SETUP_TASK && <TaskProgress job={job} t={t} c={c} onSaved={async () => { await reloadJobs(); loadCosting(); }} />}
              </li>
            );
          })}
        </ul>
      </section>
      )}

      </>
      )}

      {started && !DEMO && (job.site_walk_at || !job.started_at) && <ReportBox jobId={jobId} />}
      {started && !DEMO && (job.site_walk_at || !job.started_at) && <EstimateSummary job={job} costByTask={costByTask} collapsible />}
      {started && !DEMO && <MaterialAsk me={me} job={job} />}
      {started && !DEMO && costing && (me.role === "crew_lead" || me.role === "gm") && (
        <CrewHours me={me} jobId={jobId} tasks={costing.tasks} crewIds={onJob} onChanged={loadCosting} />
      )}

      {me && jobId && !DEMO && (
        <section className="panel">
          <div className="panel-head">
            <h2>Materials</h2>
            <button className="link" onClick={() => setShowMats((v) => !v)} aria-expanded={showMats}>
              {showMats ? "Hide" : "Show what's planned and sent"}
            </button>
          </div>
          {(started || DEMO) && <MaterialCheck jobId={jobId} kind="on_site" />}
          {showMats && <JobMaterials key={jobId} jobId={jobId} me={me} compact />}
        </section>
      )}

      {(started || DEMO) && (
      <div className={`actionbar ${selectedOnClock.length ? "show" : ""}`} aria-hidden={!selectedOnClock.length}>
        <button className="btn-stop" disabled={working || !selectedOnClock.length} onClick={() => run(() => field.clockOut(selectedOnClock))}>
          Clock out {shownCount.current}
        </button>
      </div>
      )}
    </div>
  );
}


// ---------- the crew lead's list of jobs ----------

function JobPicker({ me, jobs, loaded, onOpen, onRefresh }) {
  useEffect(() => void onRefresh(), []); // eslint-disable-line react-hooks/exhaustive-deps
  const lead = me.role === "crew_lead";
  const order = (j) => (j.status === "active" ? 0 : 1);
  const list = [...jobs].sort((a, b) => order(a) - order(b) || ((a.start_date ?? "9999") < (b.start_date ?? "9999") ? -1 : 1));
  return (
    <div className="field">
      <InstallHint />
      <h2 className="detail-title">{lead ? "Your jobs" : "Open jobs"}</h2>
      {!list.length && !loaded ? (
        <p className="empty">Loading your jobs…</p>
      ) : !list.length ? (
        <p className="empty">{lead ? "No jobs sent to you yet. When the office sends you one, it shows up here." : "No open jobs."}</p>
      ) : (
        <ul className="joblist">
          {list.map((j) => (
            <li key={j.id}>
              <button className="jobrow field-jobrow" onClick={() => onOpen(j.id)}>
                <span className="jobrow-head">
                  <span className="jobrow-name">{j.name}</span>
                  <span className={`chip chip-${j.status}`}>{j.status === "active" ? "In progress" : "Not started"}</span>
                </span>
                <span className="jobrow-foot">
                  {j.address && <span>{j.address}</span>}
                  <span>{lead ? (j.started_at ? `Started ${fmtLocalDay(j.started_at)}` : j.start_date ? `Starts ${fmtDay(j.start_date)}` : "") : crewLine(j)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------- on site: clock in first, then walk the site ----------

const SETUP_TASK = "Site walk and setup";
const hrs = (v) => fmt(v, 1);

// "3 people × 8 hrs = 24 labor hrs" — hours on a task are everyone's hours added up.
function planText(t) {
  const est = t.estimated_hours || 0;
  if (!est) return "";
  const n = t.crew_size || 0;
  return n > 1 ? `Planned: ${n} people × ${hrs(est / n)} hrs = ${hrs(est)} labor hrs` : `Planned: ${hrs(est)} labor hrs`;
}

function OnSite({ job, crew, selected, toggle, setSelected, onShowAll, showAll, onStarted }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function go() {
    setError(null);
    setBusy(true);
    try {
      const pos = job.lat == null ? await getPosition(15000) : null;
      const started = await api(`/api/jobs/${job.id}/start`, { method: "POST", body: pos ?? {} });
      await onStarted(started);
    } catch (e) {
      setError(e.status === 0 ? "No signal. Try again in a minute." : e.message);
      setBusy(false);
    }
  }
  return (
    <section className="panel on-site">
      <h2>At the job?</h2>
      <p className="help">
        Clock your crew in first, then walk the site. Everyone you pick goes on the clock for the site walk and setup.
        {job.lat == null && " This also sets the site pin where you're standing."}
      </p>
      <div className="panel-head">
        <h3>Who's here?</h3>
        <button className="link" onClick={() => setSelected(selected.size === crew.length ? new Set() : new Set(crew.map((c) => c.id)))}>
          {selected.size === crew.length ? "Clear" : "Select all"}
        </button>
      </div>
      <ul className="crew">
        {crew.map((c) => (
          <li key={c.id}>
            <label className={`crew-row ${selected.has(c.id) ? "is-picked" : ""}`}>
              <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
              <span className="crew-name">{c.name}</span>
            </label>
          </li>
        ))}
      </ul>
      {onShowAll && (
        <button className="link" onClick={onShowAll}>
          {showAll ? "Just this job's crew" : "Someone else here today? Show everyone"}
        </button>
      )}
      {error && <p className="err">{error}</p>}
      <button className="btn btn-big" onClick={go} disabled={busy || !selected.size}>
        {busy ? "Clocking in…" : selected.size ? `We're here: clock in ${selected.size}` : "Pick who's here"}
      </button>
    </section>
  );
}

// What the estimate says is to be done, for checking against the site.
function EstimateSummary({ job, costByTask, collapsible = false }) {
  const [open, setOpen] = useState(!collapsible);
  const tasks = job.tasks.filter((t) => t.kind !== "sub" && t.name !== SETUP_TASK);
  const subs = job.tasks.filter((t) => t.kind === "sub");
  const total = tasks.reduce((s, t) => s + (t.estimated_hours || 0), 0);
  const body = (
    <>
      {job.scope_text && <p className="scope-text">{job.scope_text}</p>}
      <ol className="scope-list">
        {tasks.map((t) => (
          <li key={t.id}>
            <b>{t.name}</b>
            {amountText(t) && <span> · {amountText(t)}</span>}
            {planText(t) && <span className="sub">{planText(t)}</span>}
          </li>
        ))}
      </ol>
      {subs.length > 0 && <p className="help">By a subcontractor: {subs.map((t) => t.name).join(", ")}</p>}
      <p className="help">
        {hrs(total)} labor hours planned in all. Materials planned for this job are under Materials below.
      </p>
    </>
  );
  if (!collapsible) return body;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>What's on the estimate</h2>
        <button className="link" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Hide" : "Show"}
        </button>
      </div>
      {open && body}
    </section>
  );
}

function SiteWalk({ job, costByTask, onDone }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  async function done() {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/jobs/${job.id}/walked`, { method: "POST" });
      await onDone();
    } catch (e) {
      setError(e.status === 0 ? "No signal. Try again in a minute." : e.message);
      setBusy(false);
    }
  }
  return (
    <section className="panel site-walk">
      <h2>Walk the site</h2>
      <p className="help">
        Your crew is on the clock for the site walk. Check the site against what's on the estimate and check the material
        is all here. Note anything that's different, damaged or missing, and take photos.
      </p>
      <h3>What's on the estimate</h3>
      <EstimateSummary job={job} costByTask={costByTask} />
      <h3>Material on site</h3>
      <MaterialCheck jobId={job.id} kind="on_site" />
      <h3>What you found</h3>
      <ReportBox jobId={job.id} bare />
      {error && <p className="err">{error}</p>}
      <button className="btn btn-big" onClick={done} disabled={busy}>
        {busy ? "Saving…" : "Done walking: start the work"}
      </button>
      <p className="help">Then put the crew on their tasks below.</p>
    </section>
  );
}

// ---------- how far along a task is ----------

const PCTS = [25, 50, 75, 100];
const pctWord = (p) => (p === 100 ? "Done" : `${p}% done`);

function TaskProgress({ job, t, c, onSaved }) {
  const [open, setOpen] = useState(false);
  const [pct, setPct] = useState(t.progress_pct ?? 100);
  const [note, setNote] = useState(t.progress_note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const now = t.progress_pct ?? 0;
  async function save(value = pct) {
    setBusy(true);
    setError(null);
    try {
      await api(`/api/jobs/${job.id}/tasks/${t.id}/progress`, { method: "POST", body: { pct: value, note: note.trim() } });
      await onSaved();
      setOpen(false);
    } catch (e) {
      setError(e.status === 0 ? "No signal. Try again in a minute." : e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="progress">
      <div className="progress-line">
        {now > 0 && <span className={`chip chip-${now === 100 ? "done" : "active"}`}>{pctWord(now)}</span>}
        {now > 0 && c && <Pace pct={now} estimated={c.estimated_hours} used={c.actual_hours + c.open_hours} />}
        <button className="link" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Close" : now ? "Update" : "How far along?"}
        </button>
      </div>
      {t.progress_note && !open && <p className="sub progress-note">{t.progress_note}</p>}
      {open && (
        <div className="progress-form">
          <div className="seg pct-seg" role="group" aria-label="How far along">
            {PCTS.map((p) => (
              <button type="button" key={p} aria-pressed={pct === p} onClick={() => setPct(p)}>
                {p === 100 ? "Done" : `${p}%`}
              </button>
            ))}
          </div>
          <label>
            Or type it (%)
            <input type="number" inputMode="numeric" min="1" max="100" step="1" value={pct}
              onChange={(e) => setPct(Math.max(0, Math.min(100, Math.round(Number(e.target.value) || 0))))} />
          </label>
          <label>
            Note
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
              placeholder={pct < 100 ? "e.g. North half done, south half after it dries" : "Optional"} />
          </label>
          <Photos kind="task" id={t.id} title={pct === 100 ? "Photos of the finished work" : "Photos of the work"} />
          {error && <p className="err">{error}</p>}
          <div className="note-buttons">
            {now > 0 && (
              <button className="btn-ghost" onClick={() => save(0)} disabled={busy}>
                Not started after all
              </button>
            )}
            <button className="btn" onClick={() => save()} disabled={busy || !pct}>
              {busy ? "Saving…" : `Save: ${pctWord(pct).toLowerCase()}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- asking for more material, signed by the crew lead ----------

const REQ_WORD = { open: "Waiting on the shop", sent: "Sent", declined: "Declined" };

function MaterialAsk({ me, job }) {
  const [list, setList] = useState(null);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const blank = { description: "", item_id: null, quantity: "", unit: "", reason: "", signed_name: "", i_am_responsible: false };
  const [f, setF] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const load = useCallback(() => {
    api(`/api/jobs/${job.id}/material-requests`).then(setList).catch(() => setList((l) => l ?? []));
  }, [job.id]);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);
  useEffect(() => {
    if (open && !items.length) api("/api/items").then(setItems).catch(() => {});
  }, [open, items.length]);
  const set = (k) => (e) => {
    const v = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setF((x) => {
      const n = { ...x, [k]: v };
      if (k === "description") {
        const hit = items.find((i) => i.name.toLowerCase() === v.trim().toLowerCase());
        n.item_id = hit?.id ?? null;
        if (hit && !x.unit) n.unit = hit.unit ?? "";
      }
      return n;
    });
  };
  async function send(e) {
    e.preventDefault();
    setError(null);
    if (!f.i_am_responsible) return setError("Tick the box to sign for it.");
    setBusy(true);
    try {
      await api(`/api/jobs/${job.id}/material-requests`, { method: "POST", body: { ...f, quantity: Number(f.quantity) } });
      setF(blank);
      setOpen(false);
      load();
    } catch (err) {
      setError(err.status === 0 ? "No signal. Try again in a minute; what you wrote is still here." : err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Need more material?</h2>
        {!open && (
          <button className="btn-ghost" onClick={() => setOpen(true)}>
            Ask for more
          </button>
        )}
      </div>
      {open && (
        <form className="mat-ask" onSubmit={send} onKeyDown={noEnterSubmit}>
          <label>
            What
            <input list={`items-${job.id}`} required value={f.description} onChange={set("description")} placeholder="e.g. Color concentrate, green" />
            <datalist id={`items-${job.id}`}>
              {items.map((i) => (
                <option key={i.id} value={i.name} />
              ))}
            </datalist>
          </label>
          <div className="grid two">
            <label>
              How many
              <input type="number" inputMode="decimal" min="0" step="any" required value={f.quantity} onChange={set("quantity")} />
            </label>
            <label>
              Unit
              <input value={f.unit} onChange={set("unit")} placeholder="pail, bag, gal…" />
            </label>
          </div>
          <label>
            Why is it needed?
            <textarea rows={2} required minLength={3} value={f.reason} onChange={set("reason")} placeholder="e.g. Cracks were wider than the estimate, ran short on filler" />
          </label>
          <div className="sign-box">
            <p>Sign with your full name to confirm this is needed for this job.</p>
            <label>
              Your full name
              <input required minLength={2} autoComplete="name" value={f.signed_name} onChange={set("signed_name")} placeholder={me?.name ?? ""} />
            </label>
            <label className="check">
              <input type="checkbox" checked={f.i_am_responsible} onChange={set("i_am_responsible")} />
              I'm asking for this and I'm responsible for it
            </label>
          </div>
          {error && <p className="err">{error}</p>}
          <div className="note-buttons">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); setError(null); }}>
              Cancel
            </button>
            <button className="btn" disabled={busy}>
              {busy ? "Sending…" : "Sign and send"}
            </button>
          </div>
        </form>
      )}
      {list?.length > 0 && (
        <ul className="reports">
          {list.map((r) => (
            <li key={r.id} className={r.status === "open" ? "is-waiting" : ""}>
              <p>
                <b>{fmt(r.quantity)} {r.unit} {r.description}</b>
                <span className={`chip chip-req-${r.status}`}>{REQ_WORD[r.status]}</span>
              </p>
              <p className="sub">{r.reason}</p>
              <p className="sub">
                Signed {r.signed_name} · {fmtWhen(r.at)}
              </p>
              {r.status !== "open" && (
                <p className={r.status === "sent" ? "r-resolved" : "err"}>
                  {r.status === "sent" ? "Sent" : "Declined"} by {r.handled_by} {fmtWhen(r.handled_at)}
                  {r.handled_note ? `: ${r.handled_note}` : ""}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
      {list && !list.length && !open && <p className="help">Running short? Ask here and the shop sees it right away.</p>}
    </section>
  );
}

// ---------- the crew's hours, which the crew lead can fix ----------

function CrewHours({ me, jobId, tasks, crewIds, onChanged }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="panel crew-hours">
      <div className="panel-head">
        <h2>Crew hours</h2>
        <button className="link" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "Hide" : "Check or fix hours"}
        </button>
      </div>
      {open && (
        <>
          <p className="help">
            Someone forgot to clock out, or got put on the wrong task? Fix it here. Every change needs a reason, and the
            office sees what was changed, when, by whom and why. Time older than a week, or that the office already
            corrected, can only be changed by the office.
          </p>
          <TimeLog me={me} jobId={jobId} tasks={tasks} crewIds={crewIds} onChanged={onChanged} bare />
        </>
      )}
    </section>
  );
}

// ---------- reporting a problem from the site ----------

function ReportBox({ jobId, bare = false, onSaved }) {
  const [sent, setSent] = useState(null);
  const loadSent = useCallback(() => {
    api(`/api/jobs/${jobId}/reports`).then((d) => setSent(d.reports)).catch(() => setSent((s) => s ?? []));
  }, [jobId]);
  useEffect(() => {
    loadSent();
    const t = setInterval(loadSent, 60000);
    return () => clearInterval(t);
  }, [loadSent]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  async function save(kind) {
    if (text.trim().length < 3) return setMsg({ err: true, text: "Write a few words about it first." });
    setBusy(true);
    setMsg(null);
    try {
      await api(`/api/jobs/${jobId}/reports`, { method: "POST", body: { kind, text: text.trim() } });
      setText("");
      setMsg({ text: kind === "problem" ? "Sent to the office. It's on the job for the GM and PM." : "Note saved on the job." });
      loadSent();
      onSaved?.();
    } catch (e) {
      setMsg({ err: true, text: e.status === 0 ? "No signal. Try again in a minute; what you wrote is still here." : e.message });
    } finally {
      setBusy(false);
    }
  }
  const body = (
    <div className="report-box">
      <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Crack along the north fence is wider than the estimate says. Gate lock is broken." />
      <div className="note-buttons">
        <button className="btn-ghost" onClick={() => save("note")} disabled={busy}>
          Save as a note
        </button>
        <button className="btn" onClick={() => save("problem")} disabled={busy}>
          Report a problem
        </button>
      </div>
      {msg && <p className={msg.err ? "err" : "help"} role="status">{msg.text}</p>}
      {sent?.length > 0 && (
        <>
          <h3 className="sent-title">What you've reported</h3>
          <ul className="reports">
            {sent.map((r) => (
              <li key={r.id} className={r.kind === "problem" && !r.resolved_at ? "is-open" : ""}>
                <p>
                  <b>{r.kind === "problem" ? "Problem" : "Note"}:</b> {r.text}
                </p>
                <p className="sub">
                  {r.by} · {fmtWhen(r.at)}
                  {r.kind === "problem" && !r.resolved_at && " · Sent to the office"}
                </p>
                {r.resolved_at && (
                  <p className="r-resolved">
                    Office: {r.resolution} ({r.resolved_by}, {fmtWhen(r.resolved_at)})
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      <Photos kind="job" id={jobId} title="Site photos" />
    </div>
  );
  if (bare) return body;
  return (
    <section className="panel">
      <h2>Notes and problems</h2>
      <p className="help">
        Anything the office needs to know: damage, something different from the estimate, an extra the client asked for.
        A problem goes to the GM and PM; a note is just kept on the job.
      </p>
      {body}
    </section>
  );
}
