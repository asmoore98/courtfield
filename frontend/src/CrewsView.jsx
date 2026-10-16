// Where crews are: a live map of every crew on the clock, and a daily report
// per person splitting clocked time into on the job, travel, and can't tell.
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, download } from "./api";
import CrewMap from "./CrewMap";

const hrs = (h) => (h ? (Math.round(h * 100) / 100).toFixed(2) : "0.00");
const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "");
const ago = (min) => (min < 1 ? "just now" : min < 60 ? `${min} min ago` : `${Math.floor(min / 60)} h ${min % 60} min ago`);
const short = (name) => name.split(" – ")[0];
const distance = (m) => {
  const mi = m / 1609.34;
  return mi < 0.1 ? `${Math.round(m * 3.281)} ft` : `${mi < 10 ? mi.toFixed(1) : Math.round(mi)} mi`;
};
const isoDay = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
const shift = (iso, n) => { const d = parse(iso); d.setDate(d.getDate() + n); return isoDay(d); };
const STATE = { on_job: "On the job", travel: "Travel", unknown: "Can't tell" };

// ---------- live ----------

function where(c) {
  if (!c.last) return "No location yet";
  if (c.on_site === null) return `${short(c.job_name)} has no site pin`;
  return c.on_site ? `On site at ${short(c.job_name)}` : `${distance(c.distance_m)} from ${short(c.job_name)}`;
}

function Live() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [at, setAt] = useState(null);
  const load = useCallback(async () => {
    try {
      setData(await api("/api/crews/live"));
      setAt(new Date());
      setError(null);
    } catch (e) {
      setError(e.status === 0 ? "No connection. Showing the last update." : e.message);
    }
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  const markers = useMemo(
    () =>
      (data?.crews ?? [])
        .filter((c) => c.last)
        .map((c) => ({
          lat: c.last.lat, lng: c.last.lng, label: c.lead_name.split(" ")[0],
          tone: c.stale ? "stale" : c.on_site === false ? "away" : "on",
          popup: `${c.lead_name}: ${where(c)}, ${ago(c.last.age_min)}`,
        })),
    [data]
  );
  if (!data) return <p className="empty">{error ?? "Loading crews…"}</p>;

  return (
    <div className="live">
      <div className="live-bar">
        <span className="help">
          {data.crews.length ? `${data.crews.length} ${data.crews.length === 1 ? "crew" : "crews"} on the clock` : "Nobody is on the clock right now."}
          {at && ` · Updated ${clock(at.toISOString())}`}
        </span>
        <button className="btn-ghost" onClick={load}>Refresh</button>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="live-layout">
        <CrewMap jobs={data.jobs} markers={markers} radius={data.radius_m} label="Map of crews and job sites" />
        <ul className="live-list">
          {data.crews.map((c) => (
            <li key={c.lead_id} className="panel live-card">
              <div className="live-head">
                <span className={`live-dot ${c.stale ? "stale" : c.on_site === false ? "away" : "on"}`} aria-hidden="true" />
                <h3>{c.lead_name}</h3>
              </div>
              <p className="live-where">{where(c)}</p>
              <p className="sub">
                {c.last ? `Location ${ago(c.last.age_min)}` : "This phone hasn't sent a location since clocking in"}
                {c.last && c.stale && ". The app is probably closed or the phone locked; it updates when they open it."}
              </p>
              <ul className="live-crew">
                {c.crew.map((m) => (
                  <li key={m.worker_id}>
                    <span>{m.name}</span>
                    <span className="sub-inline">{m.task} · since {clock(m.since)}</span>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </div>
      <p className="help">
        Each dot is a crew lead's phone; the crew they clocked in is with them. Dashed circles are job sites (within {(data.radius_m / 1609.34).toFixed(2)} mi
        of the pin counts as on site). Phones only report while the app is open, so a gray dot means it hasn't checked in for 15 minutes or more.
      </p>
    </div>
  );
}

// ---------- daily report ----------

function Timeline({ segments, from, to }) {
  const a = new Date(from).getTime();
  const b = new Date(to ?? Date.now()).getTime();
  const span = Math.max(1, b - a);
  return (
    <div className="tl" role="img" aria-label="Timeline of the day: on the job, travel, and can't tell">
      {segments.map((s, i) => {
        const left = ((new Date(s.start).getTime() - a) / span) * 100;
        const width = ((new Date(s.end).getTime() - new Date(s.start).getTime()) / span) * 100;
        return <span key={i} className={`tl-seg tl-${s.state}`} style={{ left: `${left}%`, width: `${Math.max(width, 0.4)}%` }} title={`${clock(s.start)}–${clock(s.end)} ${STATE[s.state]}`} />;
      })}
      <span className="tl-tick tl-start">{clock(from)}</span>
      <span className="tl-tick tl-end">{to ? clock(to) : "now"}</span>
    </div>
  );
}

function Detail({ day, person, onClose }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    setD(null);
    api(`/api/reports/daily/${person.worker_id}?date=${day}`).then(setD).catch((e) => setError(e.message));
  }, [day, person.worker_id]);
  const route = useMemo(() => (d?.points ?? []).map((p) => ({ ...p, label: `${clock(p.t)}${p.on_site === false ? " · away" : ""}` })), [d]);
  if (error) return <p className="alert" role="alert">{error}</p>;
  if (!d) return <p className="help">Loading {person.name}'s day…</p>;
  const s = d.summary;
  const end = s.last_out ?? null;
  return (
    <section className="panel daily-detail" aria-labelledby="dd-h">
      <div className="panel-head">
        <h3 id="dd-h">{s.name}, {parse(day).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</h3>
        <button className="link" onClick={onClose}>Close</button>
      </div>
      <dl className="dd-figs">
        <div><dt>Clocked</dt><dd>{hrs(s.clocked_hours)}</dd></div>
        <div><dt><span className="key key-on_job" />On the job</dt><dd>{hrs(s.on_job_hours)}</dd></div>
        <div><dt><span className="key key-travel" />Travel</dt><dd>{hrs(s.travel_hours)}</dd></div>
        <div><dt><span className="key key-unknown" />Can't tell</dt><dd>{hrs(s.unknown_hours)}</dd></div>
        <div><dt>Unclocked between entries</dt><dd>{hrs(s.between_entries_hours)}</dd></div>
      </dl>
      <Timeline segments={d.segments} from={s.first_in} to={end} />
      {s.flags.length > 0 && (
        <ul className="dd-flags">
          {s.flags.map((f) => <li key={f} className="flag flag-warn">{f}</li>)}
        </ul>
      )}
      <div className="dd-layout">
        <div className="table-scroll">
          <table className="dd-table">
            <thead>
              <tr><th scope="col">From</th><th scope="col">To</th><th scope="col" className="num">Hours</th><th scope="col">Where</th><th scope="col">Job and task</th></tr>
            </thead>
            <tbody>
              {d.segments.map((x, i) => (
                <tr key={i}>
                  <td>{clock(x.start)}</td>
                  <td>{clock(x.end)}</td>
                  <td className="num">{hrs(x.hours)}</td>
                  <td><span className={`key key-${x.state}`} />{STATE[x.state]}</td>
                  <td>{short(x.job)}<span className="sub">{x.task}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {route.length > 0 ? (
          <CrewMap jobs={d.jobs} route={route} radius={d.jobs[0]?.radius_m ?? 400} height={340} label={`Map of ${s.name}'s locations`} />
        ) : (
          <p className="help">No locations were recorded for this day.</p>
        )}
      </div>
    </section>
  );
}

function Daily() {
  const [day, setDay] = useState(() => isoDay(new Date()));
  const [rep, setRep] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setError(null);
    setOpen(null);
    api(`/api/reports/daily?date=${day}`).then(setRep).catch((e) => setError(e.message));
  }, [day]);
  const today = isoDay(new Date());

  async function csv() {
    setBusy(true);
    try {
      await download(`/api/reports/daily.csv?date=${day}`, `daily-report-${day}.csv`);
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  return (
    <div className="daily">
      <div className="detail-head">
        <h2 className="detail-title">Daily report, {parse(day).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", year: "numeric" })}</h2>
        <div className="detail-actions">
          <button className="btn-ghost" onClick={() => setDay(shift(day, -1))}>Previous day</button>
          {day !== today && <button className="btn-ghost" onClick={() => setDay(today)}>Today</button>}
          {day < today && <button className="btn-ghost" onClick={() => setDay(shift(day, 1))}>Next day</button>}
          <label className="sr-only" htmlFor="daily-date">Pick a day</label>
          <input id="daily-date" type="date" value={day} max={today} onChange={(e) => e.target.value && setDay(e.target.value)} />
        </div>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      {!rep ? (
        !error && <p className="empty">Loading…</p>
      ) : !rep.people.length ? (
        <p className="empty">Nobody was on the clock this day.</p>
      ) : (
        <section className="panel">
          <div className="table-scroll">
            <table className="daily-table">
              <thead>
                <tr>
                  <th scope="col">Person</th>
                  <th scope="col" className="d-wide">In</th>
                  <th scope="col" className="d-wide">Out</th>
                  <th scope="col" className="num">Clocked</th>
                  <th scope="col" className="num"><span className="key key-on_job" />On the job</th>
                  <th scope="col" className="num"><span className="key key-travel" />Travel</th>
                  <th scope="col" className="num d-wide"><span className="key key-unknown" />Can't tell</th>
                  <th scope="col" className="num d-wide">Unclocked gaps</th>
                </tr>
              </thead>
              <tbody>
                {rep.people.map((p) => (
                  <tr key={p.worker_id} className={open?.worker_id === p.worker_id ? "is-open" : ""}>
                    <th scope="row">
                      <button className="link row-link" onClick={() => setOpen(open?.worker_id === p.worker_id ? null : { ...p, day })} aria-expanded={open?.worker_id === p.worker_id}>
                        {p.name}
                      </button>
                      <span className="sub">{p.jobs.map(short).join(", ")}</span>
                      {p.flags.length > 0 && (
                        <span className="ts-flags">
                          {p.flags.map((f) => <span key={f} className="flag flag-warn">{f}</span>)}
                        </span>
                      )}
                    </th>
                    <td className="d-wide">{clock(p.first_in)}</td>
                    <td className="d-wide">{p.still_on_clock ? <span className="t-near">On the clock</span> : clock(p.last_out)}</td>
                    <td className="num">{hrs(p.clocked_hours)}</td>
                    <td className="num">{hrs(p.on_job_hours)}</td>
                    <td className={`num ${p.travel_hours ? "t-near" : ""}`}>{hrs(p.travel_hours)}</td>
                    <td className="num d-wide">{p.unknown_hours ? hrs(p.unknown_hours) : ""}</td>
                    <td className="num d-wide">{p.between_entries_hours ? hrs(p.between_entries_hours) : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Everyone</th>
                  <td className="d-wide" /><td className="d-wide" />
                  <td className="num">{hrs(rep.totals.clocked_hours)}</td>
                  <td className="num">{hrs(rep.totals.on_job_hours)}</td>
                  <td className="num">{hrs(rep.totals.travel_hours)}</td>
                  <td className="num d-wide">{rep.totals.unknown_hours ? hrs(rep.totals.unknown_hours) : ""}</td>
                  <td className="num d-wide">{rep.totals.between_entries_hours ? hrs(rep.totals.between_entries_hours) : ""}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </section>
      )}
      {open && open.day === day && <Detail day={day} person={open} onClose={() => setOpen(null)} />}
      <div className="ts-export">
        {rep?.people.length > 0 && (
          <div className="add-row">
            <button className="btn" onClick={csv} disabled={busy}>{busy ? "Preparing…" : "Download (CSV)"}</button>
            <button className="btn-ghost" onClick={() => window.print()}>Print</button>
          </div>
        )}
        <p className="help">
          A crew member's location is their crew lead's phone. On the job: the phone was within the job's site circle. Travel: it was away
          from the site while they were clocked in (driving in, between jobs, supply runs). Can't tell: the job has no site pin, or the phone
          sent no location for more than 30 minutes at the start or end of the time. Phones only report while the app is open, so a stretch
          with the phone locked counts as on the job if it was on site before and after. Unclocked gaps are time between one clock-out and
          the next clock-in. Times in {rep?.timezone.replace("_", " ") ?? "the company's time zone"}.
        </p>
      </div>
    </div>
  );
}

export default function CrewsView() {
  const [tab, setTab] = useState("live");
  return (
    <div className="crews">
      <nav className="subtabs" aria-label="Crews">
        <button aria-pressed={tab === "live"} onClick={() => setTab("live")}>Live map</button>
        <button aria-pressed={tab === "daily"} onClick={() => setTab("daily")}>Daily report</button>
      </nav>
      {tab === "live" ? <Live /> : <Daily />}
    </div>
  );
}
