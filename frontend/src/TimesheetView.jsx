// Weekly timesheet for payroll: each person's hours by day, regular and
// overtime, and anything payroll should look at before paying.
import { useEffect, useState } from "react";
import { DEMO, api, download } from "./api";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const ROLE_LABEL = { crew: "Crew", crew_lead: "Crew lead", gm: "GM", estimator: "Estimator", owner: "Owner", warehouse: "Warehouse" };
const money = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
const hrs = (h) => (h ? (Math.round(h * 100) / 100).toFixed(2).replace(/\.?0+$/, "") : "");
const parse = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };
const fmtDay = (iso, opts = { month: "short", day: "numeric" }) => parse(iso).toLocaleDateString(undefined, opts);
const shift = (iso, days) => { const d = parse(iso); d.setDate(d.getDate() + days); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

function Flags({ f }) {
  const items = [
    f.open_entries && [`${f.open_entries} still on the clock`, "warn"],
    f.long_days && [`${f.long_days} day${f.long_days > 1 ? "s" : ""} over 12 h`, "warn"],
    f.corrected && [`${f.corrected} corrected`, "info"],
    f.off_site && [`${f.off_site} off site`, "warn"],
  ].filter(Boolean);
  if (!items.length) return null;
  return (
    <span className="ts-flags">
      {items.map(([t, tone]) => (
        <span key={t} className={`flag flag-${tone}`}>{t}</span>
      ))}
    </span>
  );
}

export default function TimesheetView({ me }) {
  const [week, setWeek] = useState(null); // any date in the week; null = this week
  const [sheet, setSheet] = useState(null);
  const [company, setCompany] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setError(null);
    api(`/api/reports/timesheet${week ? `?week=${week}` : ""}`)
      .then(setSheet)
      .catch((e) => setError(e.message));
  }, [week, company?.week_start]);
  useEffect(() => {
    api("/api/company").then(setCompany).catch(() => {});
  }, []);

  async function setWeekStart(v) {
    try {
      setCompany(await api("/api/company", { method: "PATCH", body: { week_start: Number(v) } }));
    } catch (e) {
      setError(e.message);
    }
  }

  async function exportCsv() {
    setBusy(true);
    setError(null);
    try {
      await download(`/api/reports/timesheet.csv?week=${sheet.week_start}`, `timesheet-${sheet.week_start}.csv`);
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  }

  if (!sheet) return <p className="empty">{error ? `Couldn't load the timesheet: ${error}` : "Loading timesheet…"}</p>;
  const thisWeek = week === null;
  const openTotal = sheet.people.reduce((s, p) => s + p.flags.open_entries, 0);

  return (
    <div className="timesheet">
      <div className="detail-head">
        <h2 className="detail-title">
          Timesheet, {fmtDay(sheet.week_start)} to {fmtDay(sheet.week_end, { month: "short", day: "numeric", year: "numeric" })}
        </h2>
        <div className="detail-actions">
          <button className="btn-ghost" onClick={() => setWeek(shift(sheet.week_start, -7))}>Previous week</button>
          {!thisWeek && <button className="btn-ghost" onClick={() => setWeek(null)}>This week</button>}
          <button className="btn-ghost" onClick={() => setWeek(shift(sheet.week_start, 7))}>Next week</button>
        </div>
      </div>

      <div className="ts-meta">
        {company && (
          me.role === "gm" ? (
            <label className="inline-select">
              Pay week starts on
              <select value={company.week_start} onChange={(e) => setWeekStart(e.target.value)}>
                {DAY_NAMES.map((d, i) => (
                  <option key={d} value={i}>{d}</option>
                ))}
              </select>
            </label>
          ) : (
            <span>Pay week starts on {DAY_NAMES[company.week_start]}</span>
          )
        )}
        <span>Times in {sheet.timezone.replace("_", " ")}</span>
      </div>

      {openTotal > 0 && (
        <p className="alert" role="status">
          {openTotal} {openTotal === 1 ? "entry is" : "entries are"} still on the clock this week and not counted yet. Clock them out or fix them in the job's time log before running payroll.
        </p>
      )}
      {error && <p className="alert" role="alert">{error}</p>}

      <section className="panel">
        {!sheet.people.length ? (
          <p className="empty">No time logged this week.</p>
        ) : (
          <div className="table-scroll">
            <table className="ts-table">
              <thead>
                <tr>
                  <th scope="col">Person</th>
                  {sheet.days.map((d) => (
                    <th key={d.date} scope="col" className="num">
                      {d.label}<span className="sub">{fmtDay(d.date, { day: "numeric" })}</span>
                    </th>
                  ))}
                  <th scope="col" className="num ts-sum">Regular</th>
                  <th scope="col" className="num ts-sum">Overtime</th>
                  <th scope="col" className="num ts-sum">Total</th>
                  <th scope="col" className="num">Labor cost</th>
                </tr>
              </thead>
              <tbody>
                {sheet.people.map((p) => (
                  <tr key={p.worker_id}>
                    <th scope="row">
                      {p.name}
                      <span className="sub">{ROLE_LABEL[p.role] ?? p.role}{p.jobs.length ? ` · ${p.jobs.map((j) => j.job.split(" – ")[0]).join(", ")}` : ""}</span>
                      <Flags f={p.flags} />
                    </th>
                    {p.days.map((h, i) => (
                      <td key={i} className={`num ${h > 12 ? "t-near" : ""}`}>{hrs(h)}</td>
                    ))}
                    <td className="num ts-sum">{hrs(p.regular_hours) || "0"}</td>
                    <td className={`num ts-sum ${p.overtime_hours ? "t-over" : ""}`}>{p.overtime_tracked ? hrs(p.overtime_hours) || "0" : "n/a"}</td>
                    <td className="num ts-sum"><b>{hrs(p.total_hours) || "0"}</b></td>
                    <td className="num">{money(p.labor_cost)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Everyone</th>
                  {sheet.totals.days.map((h, i) => (
                    <td key={i} className="num">{hrs(h)}</td>
                  ))}
                  <td className="num ts-sum">{hrs(sheet.totals.regular_hours) || "0"}</td>
                  <td className="num ts-sum">{hrs(sheet.totals.overtime_hours) || "0"}</td>
                  <td className="num ts-sum"><b>{hrs(sheet.totals.total_hours) || "0"}</b></td>
                  <td className="num">{money(sheet.totals.labor_cost)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </section>

      <div className="ts-export">
        {DEMO ? (
          <p className="help">In the real app, Download for payroll saves this week as a spreadsheet file (CSV). Downloads are turned off in this preview.</p>
        ) : (
          <button className="btn" onClick={exportCsv} disabled={busy || !sheet.people.length}>
            {busy ? "Preparing…" : "Download for payroll (CSV)"}
          </button>
        )}
        <p className="help">
          Overtime is hours over 40 in the pay week, split out for crew and crew leads only. Labor cost counts overtime hours at 1.5×. Entries count on the day they started. Confirm overtime eligibility with payroll.
        </p>
      </div>
    </div>
  );
}
