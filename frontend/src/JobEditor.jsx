import { useEffect, useMemo, useState } from "react";
import { DEMO, api, safeGet, safeSet } from "./api";
import { getPosition } from "./fieldStore";
import NumInput from "./NumInput";

export const COURT_TYPES = [
  ["tennis", "Tennis"],
  ["pickleball", "Pickleball"],
  ["basketball", "Basketball"],
  ["multi_court", "Multi-court"],
  ["turf_field", "Turf field"],
];
export const SCOPE_TYPES = [
  ["resurfacing", "Resurfacing"],
  ["repair", "Repair"],
  ["new_construction", "New construction"],
];
const TASK_TYPES = [
  ["prep", "Prep"],
  ["crack_fill", "Crack fill"],
  ["resurfacer", "Resurfacer"],
  ["color_coat", "Color coat"],
  ["lines", "Lines"],
  ["fence", "Fence"],
  ["nets_posts", "Nets & posts"],
  ["lighting", "Lighting"],
  ["other", "Other"],
];

// Starter task lists. Hours are left blank on purpose: they come from the
// estimator, and later (Phase 3) from actuals on closed jobs.
const STARTERS = {
  resurfacing: [
    ["prep", "Pressure wash & prep"],
    ["crack_fill", "Crack repair"],
    ["resurfacer", "Acrylic resurfacer"],
    ["color_coat", "Color coats"],
    ["lines", "Line striping"],
    ["nets_posts", "Nets & posts"],
  ],
  repair: [
    ["prep", "Clean & prep"],
    ["crack_fill", "Crack fill & low-spot patch"],
    ["color_coat", "Spot color & blend"],
    ["lines", "Re-stripe"],
  ],
  new_construction: [
    ["prep", "Base check & flood test"],
    ["resurfacer", "Resurfacer"],
    ["color_coat", "Color coats"],
    ["lines", "Lines"],
    ["fence", "Fence"],
    ["nets_posts", "Posts & nets"],
  ],
};
const TURF_STARTER = [
  ["prep", "Base grading & compaction"],
  ["other", "Turf install & seaming"],
  ["other", "Infill"],
  ["lines", "Inlaid lines"],
  ["fence", "Fence & netting"],
];

const starterTasks = (court, scope) =>
  (court === "turf_field" ? TURF_STARTER : STARTERS[scope]).map(([task_type, name]) => ({
    key: crypto.randomUUID?.() ?? String(Math.random()),
    task_type,
    name,
    estimated_hours: "",
  }));

const blankJob = () => ({
  name: "",
  client: "",
  address: "",
  parcel_id: "",
  lat: null,
  lng: null,
  court_type: "pickleball",
  scope_type: "resurfacing",
  contract_amount: "",
  estimated_labor_rate: "",
  sales_tax_pct: "",
  tasks: starterTasks("pickleball", "resurfacing"),
  cost_lines: [],
});

export const COST_CATEGORIES = [
  ["material", "Material"],
  ["equipment", "Rental"],
  ["subcontractor", "Sub"],
  ["other", "Other"],
];
const UNITS = ["pail", "gal", "drum", "bag", "lb", "ton", "SF", "LF", "roll", "each", "set", "day", "hr", "job"];
const newKey = () => crypto.randomUUID?.() ?? String(Math.random());
const blankLine = (category = "material") => ({ key: newKey(), category, description: "", quantity: "", unit: category === "material" ? "pail" : category === "equipment" ? "day" : "job", unit_cost: "", task_key: "" });

export function estimateOf(job) {
  const n = (v) => (v === "" || v == null ? 0 : Number(v));
  const hours = job.tasks.reduce((s, t) => s + n(t.estimated_hours), 0);
  const labor = hours * n(job.estimated_labor_rate);
  const cat = { material: 0, equipment: 0, subcontractor: 0, other: 0 };
  for (const c of job.cost_lines ?? []) cat[c.category] += n(c.quantity) * n(c.unit_cost);
  const sales_tax = (cat.material * n(job.sales_tax_pct)) / 100;
  const total_cost = labor + cat.material + sales_tax + cat.equipment + cat.subcontractor + cat.other;
  const contract = n(job.contract_amount);
  const profit = contract - total_cost;
  return { hours, labor, ...cat, sales_tax, total_cost, contract, profit, margin_pct: contract > 0 ? profit / contract : null };
}

const num = (v) => (v === "" || v == null ? 0 : Number(v));
const money = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const money2 = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
const CATEGORY_LABEL = Object.fromEntries(COST_CATEGORIES.map(([v, l]) => [v, l]));

// Unsaved work is kept on this device until it's saved or thrown away, so
// tapping another tab (or the phone killing the app) doesn't lose it.
const draftKey = (jobId) => `cf.draft.job.${jobId ?? "new"}`;
const savedAtText = (t) => new Date(t).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

// Cost breakdown and expected profit. Shared by the editor and the job page.
export function EstimateTable({ est, taxPct }) {
  const rows = [
    ["Labor", est.labor, `${Math.round(est.hours * 10) / 10} crew hours`],
    ["Materials", est.material],
    ["Sales tax on materials", est.sales_tax, taxPct ? `${taxPct}%` : null],
    ["Equipment rentals", est.equipment],
    ["Subcontractors", est.subcontractor],
    ["Other costs", est.other],
  ].filter(([, v], i) => i < 2 || v > 0);
  const tone = est.margin_pct == null ? "" : est.profit < 0 ? "t-over" : est.margin_pct < 0.15 ? "t-near" : "t-under";
  return (
    <table className="est-table">
      <tbody>
        {rows.map(([label, v, note]) => (
          <tr key={label}>
            <th scope="row">{label}{note && <span className="sub-inline"> · {note}</span>}</th>
            <td className="num">{money(v)}</td>
            <td className="num est-share">{est.total_cost > 0 ? `${Math.round((v / est.total_cost) * 100)}%` : ""}</td>
          </tr>
        ))}
        <tr className="est-total">
          <th scope="row">Total estimated cost</th>
          <td className="num">{money(est.total_cost)}</td>
          <td />
        </tr>
        <tr>
          <th scope="row">Contract</th>
          <td className="num">{est.contract ? money(est.contract) : "Not set"}</td>
          <td />
        </tr>
        <tr className={`est-profit ${tone}`}>
          <th scope="row">
            Expected profit
            {est.margin_pct != null && <span className="sub-inline est-margin-m">{Math.round(est.margin_pct * 1000) / 10}% margin</span>}
          </th>
          <td className="num">{est.contract ? money(est.profit) : ""}</td>
          <td className="num">{est.margin_pct != null ? `${Math.round(est.margin_pct * 1000) / 10}% margin` : ""}</td>
        </tr>
      </tbody>
    </table>
  );
}

export default function JobEditor({ jobId, onDone, onCancel }) {
  const key = draftKey(jobId);
  const [draft] = useState(() => safeGet(key));
  const [job, setJob] = useState(() => (jobId ? null : draft?.job ?? blankJob()));
  const [touchedTasks, setTouchedTasks] = useState(() => (jobId ? true : !!draft?.touchedTasks));
  const [restoredAt, setRestoredAt] = useState(() => (!jobId && draft ? draft.savedAt : null));
  const [dirty, setDirty] = useState(false);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState(null);
  const [bad, setBad] = useState(null); // key of the task or cost line the error points at
  const [saving, setSaving] = useState(false);
  const [locating, setLocating] = useState(false);
  const [finding, setFinding] = useState(false);
  const [locMsg, setLocMsg] = useState(null); // { tone: "ok" | "err", text }
  const [items, setItems] = useState([]);

  useEffect(() => {
    api("/api/items").then(setItems).catch(() => {}); // price list; optional
  }, []);

  useEffect(() => {
    if (!jobId) return;
    api(`/api/jobs/${jobId}/edit`)
      .then((j) => {
        const saved = reload === 0 ? safeGet(key) : null;
        if (saved?.job) {
          setJob(saved.job);
          setRestoredAt(saved.savedAt);
          return;
        }
        setJob({
          ...j,
          parcel_id: j.parcel_id ?? "",
          contract_amount: j.contract_amount ?? "",
          estimated_labor_rate: j.estimated_labor_rate ?? "",
          sales_tax_pct: j.sales_tax_pct || "",
          tasks: j.tasks.map((t) => ({ ...t, key: t.id })),
          cost_lines: (j.cost_lines ?? []).map((c) => ({ ...c, key: c.id, task_key: c.task_id ?? "" })),
        });
      })
      .catch((e) => setError(e.message));
  }, [jobId, reload]);

  // Keep a copy of unsaved work on this device after every change.
  useEffect(() => {
    if (dirty && job) safeSet(key, { job, touchedTasks, savedAt: Date.now() });
  }, [dirty, job, touchedTasks]);

  const est = useMemo(() => (job ? estimateOf(job) : null), [job]);

  if (!job) return <p className="empty">{error ? `Couldn't load the job: ${error}` : "Loading job…"}</p>;

  // Every edit goes through here so it's marked unsaved and kept as a draft.
  const change = (fn) => {
    setDirty(true);
    setJob(fn);
  };
  const clearBad = (k) => {
    if (bad === k) {
      setBad(null);
      setError(null);
    }
  };

  function startOver() {
    safeSet(key, null);
    setRestoredAt(null);
    setDirty(false);
    setBad(null);
    setError(null);
    setLocMsg(null);
    if (jobId) {
      setJob(null);
      setReload((n) => n + 1);
    } else {
      setTouchedTasks(false);
      setJob(blankJob());
    }
  }

  const set = (k, v) => change((j) => ({ ...j, [k]: v }));
  const setTask = (i, k, v) => {
    setTouchedTasks(true);
    if (k === "name") clearBad(job.tasks[i].key);
    change((j) => ({ ...j, tasks: j.tasks.map((t, n) => (n === i ? { ...t, [k]: v } : t)) }));
  };
  const moveTask = (i, d) =>
    change((j) => {
      const tasks = [...j.tasks];
      [tasks[i], tasks[i + d]] = [tasks[i + d], tasks[i]];
      return { ...j, tasks };
    });
  const removeTask = (i) => change((j) => ({ ...j, tasks: j.tasks.filter((_, n) => n !== i) }));
  const addTask = () => {
    setTouchedTasks(true);
    change((j) => ({
      ...j,
      tasks: [...j.tasks, { key: newKey(), task_type: "other", name: "", estimated_hours: "" }],
    }));
  };

  const setLine = (i, k, v) => change((j) => ({ ...j, cost_lines: j.cost_lines.map((c, n) => (n === i ? { ...c, [k]: v } : c)) }));
  // Typing or picking a price-list name fills in its type, unit and cost.
  const setLineName = (i, v) => {
    clearBad(job.cost_lines[i].key);
    change((j) => ({
      ...j,
      cost_lines: j.cost_lines.map((c, n) => {
        if (n !== i) return c;
        const item = items.find((it) => it.name.toLowerCase() === v.trim().toLowerCase());
        if (item && item.id !== c.item_id)
          return { ...c, description: item.name, item_id: item.id, category: item.category, unit: item.unit, unit_cost: item.unit_cost ?? c.unit_cost };
        if (!item && c.item_id) return { ...c, description: v, item_id: null };
        return { ...c, description: v };
      }),
    }));
  };
  const itemById = Object.fromEntries(items.map((it) => [it.id, it]));
  const removeLine = (i) => change((j) => ({ ...j, cost_lines: j.cost_lines.filter((_, n) => n !== i) }));
  const addLine = (category) => change((j) => ({ ...j, cost_lines: [...j.cost_lines, blankLine(category)] }));

  // On a new job, picking court type or scope swaps in the matching starter
  // list until someone edits the tasks by hand.
  const setKind = (k, v) => {
    change((j) => {
      const next = { ...j, [k]: v };
      if (!jobId && !touchedTasks) next.tasks = starterTasks(next.court_type, next.scope_type);
      return next;
    });
  };

  const setPin = (lat, lng) => change((j) => ({ ...j, lat: Math.round(lat * 1e6) / 1e6, lng: Math.round(lng * 1e6) / 1e6 }));

  async function useMyLocation() {
    setLocMsg(null);
    setLocating(true);
    const pos = await getPosition(8000);
    setLocating(false);
    if (pos) {
      setPin(pos.lat, pos.lng);
      setLocMsg({ tone: "ok", text: "Pin set where this phone is now." });
    } else setLocMsg({ tone: "err", text: "Couldn't get this device's location. Check location permission, or find the address instead." });
  }

  async function findAddress() {
    setLocMsg(null);
    if (job.address.trim().length < 5) return setLocMsg({ tone: "err", text: "Type the street address, city and ZIP first." });
    setFinding(true);
    try {
      const hit = await api(`/api/geocode?address=${encodeURIComponent(job.address.trim())}`);
      setPin(hit.lat, hit.lng);
      setLocMsg({ tone: "ok", text: `Pin set at ${hit.matched_address || "that address"}. Check it on the map.` });
    } catch (e) {
      setLocMsg({ tone: "err", text: e.status === 0 ? "No connection. Finding an address needs signal." : e.message });
    } finally {
      setFinding(false);
    }
  }

  // Point at the row that's wrong: mark it red, scroll to it, put the cursor in it.
  function flag(rowKey, message) {
    setBad(rowKey);
    setError(message);
    requestAnimationFrame(() => {
      const row = document.getElementById(`row-${rowKey}`);
      row?.scrollIntoView({ behavior: "smooth", block: "center" });
      row?.querySelector("input")?.focus({ preventScroll: true });
    });
  }

  async function save(e) {
    e.preventDefault();
    setError(null);
    setBad(null);
    const missing = job.tasks.findIndex((t) => !t.name.trim());
    if (missing >= 0) return flag(job.tasks[missing].key, `Task ${missing + 1} needs a name. It's marked in red above.`);
    const noDesc = job.cost_lines.findIndex((c) => !c.description.trim());
    if (noDesc >= 0)
      return flag(job.cost_lines[noDesc].key, `Line ${noDesc + 1} (${CATEGORY_LABEL[job.cost_lines[noDesc].category]}) needs a name. It's marked in red above.`);
    setSaving(true);
    const body = {
      name: job.name.trim(),
      client: job.client.trim(),
      address: job.address.trim(),
      parcel_id: (job.parcel_id ?? "").trim(),
      lat: job.lat === "" ? null : job.lat,
      lng: job.lng === "" ? null : job.lng,
      court_type: job.court_type,
      scope_type: job.scope_type,
      contract_amount: num(job.contract_amount),
      estimated_labor_rate: num(job.estimated_labor_rate),
      sales_tax_pct: num(job.sales_tax_pct),
      cost_lines: job.cost_lines.map((c) => {
        const ti = c.task_key ? job.tasks.findIndex((t) => t.key === c.task_key) : -1;
        return {
          ...(c.id ? { id: c.id } : {}),
          category: c.category,
          description: c.description.trim(),
          quantity: num(c.quantity),
          unit: (c.unit ?? "").trim(),
          unit_cost: num(c.unit_cost),
          task_index: ti >= 0 ? ti : null,
          item_id: c.item_id || null,
        };
      }),
      tasks: job.tasks.map((t) => ({
        ...(t.id ? { id: t.id } : {}),
        task_type: t.task_type,
        name: t.name.trim(),
        estimated_hours: num(t.estimated_hours),
      })),
    };
    try {
      const saved = jobId
        ? await api(`/api/jobs/${jobId}`, { method: "PUT", body })
        : await api("/api/jobs", { method: "POST", body });
      safeSet(key, null);
      onDone(saved.id);
    } catch (err) {
      setError(err.status === 0 ? "No connection. Your work is kept on this phone; save again when you have signal." : err.message);
      setSaving(false);
    }
  }

  const noHours = job.tasks.filter((t) => num(t.estimated_hours) === 0).length;
  const hasPin = job.lat != null && job.lat !== "" && job.lng != null && job.lng !== "";

  return (
    <form className="editor" onSubmit={save}>
      <button type="button" className="link back" onClick={onCancel}>
        {jobId ? "Back to job" : "All jobs"}
      </button>
      <h2 className="detail-title">{jobId ? "Edit job" : "New job"}</h2>

      {restoredAt && (
        <div className="restored" role="status">
          <span>Picked up your unsaved work from {savedAtText(restoredAt)}.</span>
          <button type="button" className="link" onClick={startOver}>
            {jobId ? "Throw it away" : "Start over"}
          </button>
        </div>
      )}

      <section className="panel">
        <h3>Job</h3>
        <div className="grid">
          <label className="span-2">
            Job name
            <input required value={job.name} onChange={(e) => set("name", e.target.value)} placeholder="Client – court count and work" />
          </label>
          <label className="span-2">
            Client
            <input value={job.client} onChange={(e) => set("client", e.target.value)} />
          </label>
          <label>
            Court type
            <select value={job.court_type} onChange={(e) => setKind("court_type", e.target.value)}>
              {COURT_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Scope
            <select value={job.scope_type} onChange={(e) => setKind("scope_type", e.target.value)}>
              {SCOPE_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Contract amount
            <span className="affix">
              <span aria-hidden="true">$</span>
              <NumInput value={job.contract_amount} onChange={(v) => set("contract_amount", v)} placeholder="0" />
            </span>
          </label>
          <label>
            Labor rate used in the estimate
            <span className="affix">
              <span aria-hidden="true">$</span>
              <NumInput value={job.estimated_labor_rate} onChange={(v) => set("estimated_labor_rate", v)} placeholder="0.00" />
              <span aria-hidden="true">/ hr</span>
            </span>
          </label>
        </div>

        <fieldset className="where">
          <legend>Job location</legend>
          <p className="help">The pin flags clock-ins made away from the site. Find it from the address, or stand on the court and use your location.</p>
          <div className="grid">
            <label className="span-2">
              Street address
              <input value={job.address} onChange={(e) => set("address", e.target.value)} placeholder="Street, city, ZIP" autoComplete="off" />
            </label>
            <label className="span-2">
              <span>
                Parcel ID <span className="optional">(optional)</span>
              </span>
              <input value={job.parcel_id ?? ""} onChange={(e) => set("parcel_id", e.target.value)} placeholder="For new lots without an address yet" autoComplete="off" maxLength={60} />
            </label>
          </div>
          <div className="where-buttons">
            {!DEMO && (
              <button type="button" className="btn-ghost" onClick={findAddress} disabled={finding}>
                {finding ? "Finding address…" : "Find this address"}
              </button>
            )}
            <button type="button" className="btn-ghost" onClick={useMyLocation} disabled={locating}>
              {locating ? "Finding location…" : "Use my current location"}
            </button>
          </div>
          {locMsg && (
            <p className={locMsg.tone === "err" ? "loc-msg err" : "loc-msg"} role={locMsg.tone === "err" ? "alert" : "status"}>
              {locMsg.text}
            </p>
          )}
          <div className="where-row">
            <label>
              Latitude
              <input type="number" step="any" min="-90" max="90" value={job.lat ?? ""} onChange={(e) => set("lat", e.target.value === "" ? null : Number(e.target.value))} />
            </label>
            <label>
              Longitude
              <input type="number" step="any" min="-180" max="180" value={job.lng ?? ""} onChange={(e) => set("lng", e.target.value === "" ? null : Number(e.target.value))} />
            </label>
          </div>
          <p className="help pin-status">
            {hasPin ? (
              <>
                Pin is set.{" "}
                <a href={`https://www.google.com/maps/search/?api=1&query=${job.lat},${job.lng}`} target="_blank" rel="noopener noreferrer">
                  Check it on the map
                </a>
              </>
            ) : (
              "No pin yet. Clock-ins can't be checked against the site until it's set."
            )}
          </p>
        </fieldset>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Tasks and estimated hours</h3>
          {!jobId && !touchedTasks && <span className="hint">Starter list for this court type and scope</span>}
        </div>
        <ol className="task-edit">
          {job.tasks.map((t, i) => (
            <li key={t.key} id={`row-${t.key}`} className={bad === t.key ? "is-invalid" : undefined}>
              <span className="task-num" aria-hidden="true">
                {i + 1}
              </span>
              <label className="te-name">
                <span className="sr-only">Task {i + 1} name</span>
                <input value={t.name} onChange={(e) => setTask(i, "name", e.target.value)} placeholder="Task name" aria-invalid={bad === t.key || undefined} />
              </label>
              <label className="te-type">
                <span className="sr-only">Task {i + 1} type</span>
                <select value={t.task_type} onChange={(e) => setTask(i, "task_type", e.target.value)}>
                  {TASK_TYPES.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </label>
              <label className="te-hours">
                <span className="sr-only">Task {i + 1} estimated hours</span>
                <NumInput value={t.estimated_hours} onChange={(v) => setTask(i, "estimated_hours", v)} placeholder="0" />
                <span aria-hidden="true">h</span>
              </label>
              <span className="te-tools">
                <button type="button" className="icon" onClick={() => moveTask(i, -1)} disabled={i === 0} aria-label={`Move task ${i + 1} up`}>
                  ▲
                </button>
                <button type="button" className="icon" onClick={() => moveTask(i, 1)} disabled={i === job.tasks.length - 1} aria-label={`Move task ${i + 1} down`}>
                  ▼
                </button>
                <button
                  type="button"
                  className="icon remove"
                  onClick={() => removeTask(i)}
                  disabled={t.has_time}
                  title={t.has_time ? "Crew time is logged on this task" : ""}
                  aria-label={`Remove task ${i + 1}`}
                >
                  ✕
                </button>
              </span>
            </li>
          ))}
        </ol>
        <button type="button" className="btn-ghost add" onClick={addTask}>
          Add task
        </button>

        <p className="subtotal">
          <b>{Math.round(est.hours * 10) / 10} crew hours</b> at {money2(num(job.estimated_labor_rate))}/hr = <b>{money(est.labor)}</b> labor
        </p>
        {noHours > 0 && (
          <p className="help">
            {noHours === 1 ? "1 task has" : `${noHours} tasks have`} no estimated hours yet, so crew time on it won't have an estimate to compare against.
          </p>
        )}
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Materials and other costs</h3>
          <label className="inline-field">
            Sales tax on materials
            <span className="affix">
              <input type="number" inputMode="decimal" min="0" max="20" step="0.25" value={job.sales_tax_pct} onChange={(e) => set("sales_tax_pct", e.target.value)} placeholder="0" aria-label="Sales tax on materials, percent" />
              <span aria-hidden="true">%</span>
            </span>
          </label>
        </div>
        {job.cost_lines.length === 0 ? (
          <p className="help">
            No lines yet. Add the coatings, sand, line paint, nets and posts, rentals and subs this job needs.
            {" "}Material quantities here become the job's material list for the warehouse and crew lead.
          </p>
        ) : (
          <ol className="line-edit">
            <li className="line-head" aria-hidden="true">
              <span>Item</span><span>Type</span><span>Qty</span><span>Unit</span><span>Cost per unit</span><span>Total</span><span>For task</span><span />
            </li>
            {job.cost_lines.map((c, i) => (
              <li key={c.key} id={`row-${c.key}`} data-cat={c.category} className={bad === c.key ? "is-invalid" : undefined}>
                <label className="le-desc">
                  <span className="le-label">Line {i + 1} · {CATEGORY_LABEL[c.category]}</span>
                  <input list="cf-items" value={c.description} onChange={(e) => setLineName(i, e.target.value)} placeholder={items.length ? "Pick from the price list or type" : "e.g. Acrylic resurfacer"} aria-invalid={bad === c.key || undefined} />
                  {c.item_id && itemById[c.item_id] && (
                    <span className="le-from">
                      Price list
                      {itemById[c.item_id].unit_cost != null && Number(c.unit_cost) !== itemById[c.item_id].unit_cost && (
                        <>
                          {" "}is {money2(itemById[c.item_id].unit_cost)}.{" "}
                          <button type="button" className="link" onClick={() => setLine(i, "unit_cost", itemById[c.item_id].unit_cost)}>Use it</button>
                        </>
                      )}
                    </span>
                  )}
                </label>
                <label className="le-cat">
                  <span className="le-label">Type</span>
                  <select value={c.category} onChange={(e) => setLine(i, "category", e.target.value)}>
                    {COST_CATEGORIES.map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                </label>
                <label className="le-qty">
                  <span className="le-label">Qty</span>
                  <NumInput decimals={3} value={c.quantity} onChange={(v) => setLine(i, "quantity", v)} placeholder="0" />
                </label>
                <label className="le-unit">
                  <span className="le-label">Unit</span>
                  <input list="cf-units" value={c.unit} onChange={(e) => setLine(i, "unit", e.target.value)} placeholder="unit" maxLength={20} />
                </label>
                <label className="le-cost">
                  <span className="le-label">Cost per unit</span>
                  <span className="affix">
                    <span aria-hidden="true">$</span>
                    <NumInput value={c.unit_cost} onChange={(v) => setLine(i, "unit_cost", v)} placeholder="0.00" />
                  </span>
                </label>
                <span className="le-total">
                  <span className="le-label">Line total</span>
                  <span>{money2(num(c.quantity) * num(c.unit_cost))}</span>
                </span>
                <label className="le-task">
                  <span className="le-label">For task</span>
                  <select value={c.task_key} onChange={(e) => setLine(i, "task_key", e.target.value)}>
                    <option value="">Whole job</option>
                    {job.tasks.map((t, ti) => (
                      <option key={t.key} value={t.key}>{t.name || `Task ${ti + 1}`}</option>
                    ))}
                  </select>
                </label>
                <span className="te-tools le-tools">
                  <button type="button" className="icon remove" onClick={() => removeLine(i)} aria-label={`Remove line ${i + 1}`}>✕</button>
                </span>
              </li>
            ))}
          </ol>
        )}
        <datalist id="cf-items">
          {items.map((it) => (
            <option key={it.id} value={it.name} />
          ))}
        </datalist>
        <datalist id="cf-units">
          {UNITS.map((u) => (
            <option key={u} value={u} />
          ))}
        </datalist>
        <div className="add-row">
          <button type="button" className="btn-ghost" onClick={() => addLine("material")}>Add material</button>
          <button type="button" className="btn-ghost" onClick={() => addLine("equipment")}>Add rental</button>
          <button type="button" className="btn-ghost" onClick={() => addLine("subcontractor")}>Add subcontractor</button>
          <button type="button" className="btn-ghost" onClick={() => addLine("other")}>Add other cost</button>
        </div>
      </section>

      <section className="panel">
        <h3>Estimate</h3>
        <EstimateTable est={est} taxPct={num(job.sales_tax_pct)} />
      </section>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn" type="submit" disabled={saving}>
          {saving ? "Saving…" : jobId ? "Save changes" : "Create job"}
        </button>
      </div>
      {dirty && <p className="help draft-note">Unsaved changes are kept on this device until you save or start over.</p>}
    </form>
  );
}
