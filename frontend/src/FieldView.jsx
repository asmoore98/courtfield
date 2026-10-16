import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DEMO, api, safeGet, safeSet } from "./api";
import { getPosition, useFieldTime } from "./fieldStore";
import HoursBar, { HoursText } from "./HoursBar";
import InstallHint from "./InstallHint";
import JobMaterials from "./JobMaterials";
import { useLocationSharing } from "./locationShare";

const JOBS_KEY = "cf.jobs";
const CREW_KEY = "cf.crew";
const JOB_KEY = "cf.job";

function useCached(key, path) {
  const [data, setData] = useState(() => safeGet(key, []));
  const load = useCallback(async () => {
    try {
      const d = await api(path);
      setData(d);
      safeSet(key, d);
    } catch {}
  }, [key, path]);
  useEffect(() => void load(), [load]);
  return [data, load];
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
  const [jobs, reloadJobs] = useCached(JOBS_KEY, "/api/jobs");
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
  useEffect(() => {
    if (!job && jobs.length) {
      const first = jobs.find((j) => j.status === "active") ?? jobs[0];
      setJobId(first.id);
    }
  }, [job, jobs]);
  useEffect(() => safeSet(JOB_KEY, jobId), [jobId]);

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

  if (!jobs.length) {
    return <p className="empty">No open jobs yet. Once the office schedules a job it shows up here.</p>;
  }

  const costByTask = Object.fromEntries((costing?.tasks ?? []).map((t) => [t.task_id, t]));
  const crewName = (id) => crew.find((c) => c.id === id)?.name ?? "A crew member";

  return (
    <div className="field">
      <InstallHint />
      <div className="field-top">
        <label className="job-pick">
          <span className="sr-only">Job</span>
          <select value={jobId ?? ""} onChange={(e) => setJobId(e.target.value)}>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>
                {j.name}
              </option>
            ))}
          </select>
        </label>
        <SyncStatus {...field} onSync={field.sync} />
      </div>

      {!noticed && <LocationNotice me={me} onDone={() => setNoticed(true)} />}
      {noticed && !DEMO && <LocationStatus share={share} active={field.myCrewOnClock} />}
      {!DEMO && job && job.lat == null && (
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

      <section className="panel">
        <div className="panel-head">
          <h2>Crew</h2>
          <button className="link" onClick={() => setSelected(selected.size === crew.length ? new Set() : new Set(crew.map((c) => c.id)))}>
            {selected.size === crew.length ? "Clear" : "Select all"}
          </button>
        </div>
        <ul className="crew">
          {crew.map((c) => {
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
      </section>

      <section className="panel">
        <div className="panel-head">
          <h2>Tasks</h2>
          <span className="hint">
            {selected.size ? `Tap a task to put ${selected.size} on it` : "Pick crew above, then tap a task"}
          </span>
        </div>
        <ul className="tasks">
          {job?.tasks.map((t) => {
            const c = costByTask[t.id];
            const here = crew.filter((w) => field.openFor(w.id)?.task_id === t.id).length;
            return (
              <li key={t.id}>
                <button
                  className="task"
                  disabled={!selected.size || working}
                  onClick={() => run(() => field.startTask(selectedIds, jobId, t.id))}
                >
                  <span className="task-line">
                    <span className="task-name">{t.name}</span>
                    {c && <HoursText estimated={c.estimated_hours} actual={c.actual_hours} open={c.open_hours} />}
                  </span>
                  {c && <HoursBar estimated={c.estimated_hours} actual={c.actual_hours} open={c.open_hours} />}
                  {here > 0 && <span className="here">{here} on it now</span>}
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      {me && jobId && !DEMO && (
        <section className="panel">
          <div className="panel-head">
            <h2>Materials</h2>
            <button className="link" onClick={() => setShowMats((v) => !v)} aria-expanded={showMats}>
              {showMats ? "Hide" : "Show what's planned and sent"}
            </button>
          </div>
          {showMats && <JobMaterials key={jobId} jobId={jobId} me={me} compact />}
        </section>
      )}

      <div className={`actionbar ${selectedOnClock.length ? "show" : ""}`} aria-hidden={!selectedOnClock.length}>
        <button className="btn-stop" disabled={working || !selectedOnClock.length} onClick={() => run(() => field.clockOut(selectedOnClock))}>
          Clock out {shownCount.current}
        </button>
      </div>
    </div>
  );
}
