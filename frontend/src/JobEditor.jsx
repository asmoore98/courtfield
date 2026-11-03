import { useEffect, useMemo, useState } from "react";
import { DEMO, api, safeGet, safeSet } from "./api";
import { getPosition } from "./fieldStore";
import NumInput from "./NumInput";
import Picker from "./Picker";
import { AddressFields, LinkList, addressBody, addressFrom, blankAddress, composeAddress, noEnterSubmit } from "./bits";
import { TASK_TYPES, TASK_TYPE_LABEL, fromTemplate, reloadLibrary, useLibrary } from "./library";
import { sameName } from "./search";
import { CourtSizeFields, blankCourt } from "./Checklist";
import { FOLLOWS_LABEL, PER_HOUR, UNITS as TASK_UNITS, UNIT_SHORT, courtAreas, defaultFollows, fmt, lineQty, quantityOf, rateLabel, taskNums } from "./qty";

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

// Starter task lists by court type and scope, named as in the task library so
// they pick up its rates. Hours are left blank: they come from the estimator.
const STARTERS = {
  resurfacing: [
    ["prep", "Pressure wash"],
    ["crack_fill", "Crack fill"],
    ["resurfacer", "Acrylic resurfacer"],
    ["color_coat", "Color coat"],
    ["lines", "Line painting"],
    ["nets_posts", "Install nets and center straps"],
  ],
  repair: [
    ["prep", "Pressure wash"],
    ["crack_fill", "Crack fill"],
    ["crack_fill", "Low-spot patch"],
    ["color_coat", "Color coat"],
    ["lines", "Line painting"],
  ],
  new_construction: [
    ["site_work", "Clearing and grubbing, light brush"],
    ["site_work", "Rough grading"],
    ["site_work", "Base rock install"],
    ["site_work", "Fine grading"],
    ["prep", "Flood test (find low spots)"],
    ["resurfacer", "Acrylic resurfacer"],
    ["color_coat", "Color coat"],
    ["lines", "Line painting"],
    ["nets_posts", "Install net posts"],
    ["fence", "Chain-link fence, new"],
  ],
};
const TURF_STARTER = [
  ["site_work", "Fine grading"],
  ["site_work", "Base rock install"],
  ["turf", "Synthetic turf install"],
  ["turf", "Turf seaming"],
  ["turf", "Turf infill"],
  ["turf", "Inlaid lines and logos"],
];

const newKey = () => crypto.randomUUID?.() ?? String(Math.random());

const blankTask = (extra = {}) => ({
  key: newKey(),
  task_type: "other",
  name: "",
  kind: "crew",
  estimated_hours: "",
  cost_rate: "",
  charge_rate: "",
  sub_id: "",
  sub_price: "",
  sub_quote_link: "",
  template_id: null,
  unit: "hr",
  quantity: "",
  coats: "",
  production_rate: "",
  unit_price: "",
  follows: "",
  checklist_note: "",
  crew_size: "",
  site_hours: "",
  ...extra,
});

// A task by its library name, linked to the library entry when there is one.
export const taskFromLibrary = (name, lib, task_type = "other") => {
  const t = lib?.tasks.find((x) => x.active && sameName(x.name, name));
  return blankTask(t ? fromTemplate(t, lib.defaults) : { task_type, name });
};

// Starter tasks; when the library is loaded they link to its entries and rates.
// No net work on a basketball court or a turf field.
const NET_TASKS = ["Install nets and center straps", "Install net posts", "Core drill post sleeves", "Net post removal"];
export const starterTasks = (court, scope, lib) =>
  (court === "turf_field" ? TURF_STARTER : STARTERS[scope])
    .filter(([, name]) => !(["basketball", "turf_field"].includes(court) && NET_TASKS.includes(name)))
    .map(([task_type, name]) => taskFromLibrary(name, lib, task_type));

export const blankJob = (lib) => ({
  name: "",
  client: "",
  address: "",
  site: blankAddress(),
  parcel_id: "",
  lat: null,
  lng: null,
  court_type: "pickleball",
  scope_type: "resurfacing",
  contract_amount: "",
  estimated_labor_rate: "",
  sales_tax_pct: "",
  tasks: starterTasks("pickleball", "resurfacing", lib),
  cost_lines: [],
});

export const COST_CATEGORIES = [
  ["material", "Material"],
  ["equipment", "Equipment"],
  ["subcontractor", "Sub"],
  ["other", "Other"],
  ["fee", "Fee"],
];
const UNITS = ["pail", "gal", "drum", "bag", "lb", "ton", "SF", "LF", "roll", "each", "set", "day", "week", "hr", "job"];
const blankLine = (category = "material") => ({
  key: newKey(),
  category,
  description: "",
  quantity: "",
  unit: category === "material" ? "pail" : category === "equipment" ? "day" : category === "fee" ? "each" : "job",
  unit_cost: "",
  task_key: "",
  in_house: false,
  follows: "",
  coats: "",
  coverage: "",
});

export const num = (v) => (v === "" || v == null ? 0 : Number(v));
export const money = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
export const money2 = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
const CATEGORY_LABEL = Object.fromEntries(COST_CATEGORIES.map(([v, l]) => [v, l]));
export const savedAtText = (t) => new Date(t).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

const MARKUP_KEYS = ["material", "equipment", "subcontractor", "other"];
export const markupsFrom = (defaults) =>
  Object.fromEntries(MARKUP_KEYS.map((k) => [k, String(defaults?.[`markup_${k}`] ?? 0)]));

/* What the work costs us and, for estimates, what we charge. Mirrors
   totals() in backend/app/routers/estimates.py.
   Cost: crew hours x each task's cost rate, sub prices, cost lines, tax.
   Charge: crew work at its price per unit, or hours x charge rate;
   everything else plus its markup
   (materials marked up with their tax). Price = charge + adjustment. */
const blankNum = (v) => v === "" || v == null;
// This line's or sub's own markup, or the default for its kind.
export const markupOf = (item, kind, markups) => (blankNum(item.markup_pct) ? num(markups?.[kind]) : num(item.markup_pct));

export function estimateOf(job) {
  const n = num;
  const crew = job.tasks.filter((t) => t.kind !== "sub");
  const subs = job.tasks.filter((t) => t.kind === "sub");
  const fallback = n(job.estimated_labor_rate);
  const areas = courtAreas(job.court);
  const nums = crew.map((t) => taskNums(t, areas, fallback));
  const hours = nums.reduce((s, x) => s + x.hours, 0);
  const labor = nums.reduce((s, x) => s + x.cost, 0);
  const m = job.markups ?? {};
  const cat = { material: 0, equipment: 0, subcontractor: 0, other: 0, fee: 0 };
  const charge = { labor: nums.reduce((s, x) => s + x.charge, 0), material: 0, equipment: 0, subcontractor: 0, other: 0 };
  let sales_tax = 0;
  for (const c of job.cost_lines ?? []) {
    const cost = lineQty(c, areas) * n(c.unit_cost);
    if (c.category === "fee") {
      cat.fee += cost; // permits and city fees pass through at cost
      continue;
    }
    const tax = c.category === "material" ? (cost * n(job.sales_tax_pct)) / 100 : 0;
    cat[c.category] += cost;
    sales_tax += tax;
    charge[c.category] += (cost + tax) * (1 + markupOf(c, c.category, m) / 100);
  }
  for (const t of subs) {
    cat.subcontractor += n(t.sub_price);
    charge.subcontractor += n(t.sub_price) * (1 + markupOf(t, "subcontractor", m) / 100);
  }
  const total_cost = labor + cat.material + sales_tax + cat.equipment + cat.subcontractor + cat.other + cat.fee;
  const subtotal = Object.values(charge).reduce((s, v) => s + v, 0);
  const priced = job.priced === "built";
  const overall_markup = priced ? n(job.overall_markup) : 0;
  const overall_amount = (subtotal * overall_markup) / 100;
  const built_price = subtotal + overall_amount + cat.fee;
  const contract = priced ? Math.round((built_price + n(job.adjustment)) * 100) / 100 : n(job.contract_amount);
  const profit = contract - total_cost;
  return {
    hours, labor, ...cat, fees: cat.fee, sales_tax, total_cost, charge, subtotal, overall_markup, overall_amount, built_price,
    adjustment: priced ? n(job.adjustment) : 0, contract, price: contract, profit,
    margin_pct: contract > 0 ? profit / contract : null, markup_pct: total_cost > 0 ? profit / total_cost : null,
  };
}

// Cost breakdown and expected profit for a job (cost only; the contract is typed).
export function EstimateTable({ est, taxPct, priceLabel = "Contract" }) {
  const rows = [
    ["Labor", est.labor, `${Math.round(est.hours * 10) / 10} crew hours`],
    ["Materials", est.material],
    ["Sales tax on materials", est.sales_tax, taxPct ? `${taxPct}%` : null],
    ["Equipment", est.equipment],
    ["Subcontractors", est.subcontractor],
    ["Other costs", est.other],
    ["Permit and city fees", est.fee ?? 0],
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
          <th scope="row">{priceLabel}</th>
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

const pctText = (p) => (p == null || !isFinite(p) ? "—" : `${Math.round(p * 1000) / 10}%`);

/* Cost against price, kind by kind, for an estimate, with the markup each
   kind ends up at, the markup on the whole job, the adjustment, and the
   overall markup and margin. Our numbers only: never on the proposal. */
export function PriceTable({ est, taxPct, adjustmentReason }) {
  const rows = [
    ["labor", "Labor", est.labor, `${Math.round(est.hours * 10) / 10} crew hours`],
    ["material", "Materials + tax", est.material + est.sales_tax, taxPct ? `${taxPct}% tax on materials` : null],
    ["equipment", "Equipment", est.equipment],
    ["subcontractor", "Subs", est.subcontractor],
    ["other", "Other costs", est.other],
  ].filter(([k, , v]) => k === "labor" || k === "material" || v > 0 || (est.charge[k] ?? 0) > 0);
  const tone = est.margin_pct == null ? "" : est.profit < 0 ? "t-over" : est.margin_pct < 0.15 ? "t-near" : "t-under";
  return (
    <div className="table-scroll">
      <table className="price-table">
        <colgroup>
          <col className="c-what" />
          <col className="c-cost" />
          <col className="c-mark" />
          <col className="c-price" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">What</th>
            <th scope="col" className="num">Cost</th>
            <th scope="col" className="num">Markup</th>
            <th scope="col" className="num">Price</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([k, label, cost, note]) => (
            <tr key={k}>
              <th scope="row">
                {label}
                {note && <span className="sub">{note}</span>}
              </th>
              <td className="num">{money(cost)}</td>
              <td className="num">{cost > 0 ? pctText((est.charge[k] ?? 0) / cost - 1) : "—"}</td>
              <td className="num">{money(est.charge[k] ?? 0)}</td>
            </tr>
          ))}
          <tr className="est-total">
            <th scope="row">Subtotal</th>
            <td className="num">{money(est.total_cost - (est.fee ?? 0))}</td>
            <td className="num">{est.total_cost - (est.fee ?? 0) > 0 ? pctText(est.subtotal / (est.total_cost - (est.fee ?? 0)) - 1) : "—"}</td>
            <td className="num">{money(est.subtotal)}</td>
          </tr>
          {est.overall_markup !== 0 && (
            <tr>
              <th scope="row">On the whole job</th>
              <td />
              <td className="num">{pctText(est.overall_markup / 100)}</td>
              <td className="num">
                {est.overall_amount >= 0 ? "+" : "−"}
                {money(Math.abs(est.overall_amount))}
              </td>
            </tr>
          )}
          {(est.fee ?? 0) > 0 && (
            <tr>
              <th scope="row">
                Permit and city fees
                <span className="sub">At cost, no markup. Listed on the proposal.</span>
              </th>
              <td className="num">{money(est.fee)}</td>
              <td className="num">—</td>
              <td className="num">{money(est.fee)}</td>
            </tr>
          )}
          {est.adjustment !== 0 && (
            <tr>
              <th scope="row">
                Adjustment
                {adjustmentReason && <span className="sub">{adjustmentReason}</span>}
              </th>
              <td />
              <td />
              <td className="num">
                {est.adjustment > 0 ? "+" : "−"}
                {money(Math.abs(est.adjustment))}
              </td>
            </tr>
          )}
          <tr className="price-final">
            <th scope="row">Proposal price</th>
            <td className="num" colSpan={3}>
              {money(est.contract)}
            </td>
          </tr>
        </tbody>
      </table>
      <dl className="markup-summary">
        <div>
          <dt>Total markup over cost</dt>
          <dd className={tone}>{pctText(est.markup_pct)}</dd>
        </div>
        <div>
          <dt>Profit margin</dt>
          <dd className={tone}>{pctText(est.margin_pct)}</dd>
        </div>
        <div>
          <dt>Expected profit</dt>
          <dd className={tone}>{money(est.profit)}</dd>
        </div>
      </dl>
      <p className="help ours-only">Our numbers only. Costs, markups and profit never show on the proposal or to Sales.</p>
    </div>
  );
}

// Turn a saved job or estimate version into form state. Tasks saved before
// per-task rates get the old single labor rate as their cost rate.
export function formFrom(j) {
  const old = j.estimated_labor_rate ? Number(j.estimated_labor_rate) : null;
  return {
    ...j,
    parcel_id: j.parcel_id ?? "",
    address: j.address ?? "",
    site: addressFrom(j, "site", j.address),
    contract_amount: j.contract_amount ?? "",
    estimated_labor_rate: j.estimated_labor_rate ?? "",
    sales_tax_pct: j.sales_tax_pct || "",
    tasks: j.tasks.map((t) =>
      blankTask({
        ...t,
        key: t.id ?? newKey(),
        estimated_hours: t.estimated_hours ?? "",
        kind: t.kind ?? "crew",
        cost_rate: t.cost_rate ?? (t.kind !== "sub" && old != null ? old : ""),
        charge_rate: t.charge_rate ?? "",
        sub_id: t.sub_id ?? "",
        sub_price: t.sub_price ?? "",
        sub_quote_link: t.sub_quote_link ?? "",
        template_id: t.template_id ?? null,
        unit: t.unit ?? "hr",
        quantity: t.quantity ?? "",
        coats: t.coats ?? "",
        production_rate: t.production_rate ?? "",
        unit_price: t.unit_price ?? "",
        follows: t.follows ?? "",
        checklist_note: t.checklist_note ?? "",
        crew_size: t.crew_size ?? "",
        site_hours: t.crew_size && t.estimated_hours ? String(Math.round((t.estimated_hours / t.crew_size) * 100) / 100) : t.estimated_hours ?? "",
        fee_added: true, // a saved estimate's fee lines are as the estimator left them
      })
    ),
    cost_lines: (j.cost_lines ?? []).map((c) => ({
      ...c,
      in_house: !!c.in_house,
      follows: c.follows ?? "",
      coats: c.coats ?? "",
      coverage: c.coverage ?? "",
      key: c.id ?? newKey(),
      // Saved jobs link a line to a task by id; estimate versions by position.
      task_key: c.task_id ?? (c.task_index != null ? null : ""),
      _task_index: c.task_index,
    })),
  };
}

// Estimate versions point lines at tasks by position; give them the task keys.
function linkTaskKeys(f) {
  if (!f.cost_lines.some((c) => c.task_key === null)) return f;
  return { ...f, cost_lines: f.cost_lines.map((c) => (c.task_key === null ? { ...c, task_key: f.tasks[c._task_index]?.key ?? "" } : c)) };
}

const optNum = (v) => (v === "" || v == null ? null : Number(v));

// The body shared by jobs and estimates: site, kind of work, money, tasks, cost lines.
export function scopeBody(f) {
  const areas = courtAreas(f.court);
  return {
    name: f.name.trim(),
    ...addressBody(f.site ?? addressFrom({}, "site", f.address), "site", "address"),
    parcel_id: (f.parcel_id ?? "").trim(),
    lat: f.lat === "" ? null : f.lat,
    lng: f.lng === "" ? null : f.lng,
    court_type: f.court_type,
    scope_type: f.scope_type,
    contract_amount: num(f.contract_amount),
    estimated_labor_rate: num(f.estimated_labor_rate),
    sales_tax_pct: num(f.sales_tax_pct),
    cost_lines: f.cost_lines.map((c) => {
      const ti = c.task_key ? f.tasks.findIndex((t) => t.key === c.task_key) : -1;
      return {
        ...(c.id ? { id: c.id } : {}),
        category: c.category,
        description: c.description.trim(),
        quantity: lineQty(c, areas),
        unit: (c.unit ?? "").trim(),
        unit_cost: num(c.unit_cost),
        task_index: ti >= 0 ? ti : null,
        item_id: c.item_id || null,
        in_house: c.category === "equipment" && !!c.in_house,
        markup_pct: optNum(c.markup_pct),
        follows: c.follows && num(c.coverage) > 0 ? c.follows : "",
        coats: optNum(c.coats),
        coverage: optNum(c.coverage),
      };
    }),
    tasks: f.tasks.map((t) => {
      const sub = t.kind === "sub";
      const x = taskNums(t, areas, num(f.estimated_labor_rate));
      const unit = sub ? "hr" : x.unit;
      return {
      ...(t.id ? { id: t.id } : {}),
      task_type: t.task_type,
      name: t.name.trim(),
      kind: t.kind ?? "crew",
      estimated_hours: sub ? 0 : Math.round(x.hours * 100) / 100,
      unit,
      quantity: unit === "hr" ? null : x.qty,
      coats: unit === "sf_coat" ? optNum(t.coats) : null,
      production_rate: unit === "hr" ? null : optNum(t.production_rate),
      unit_price: unit === "hr" ? null : optNum(t.unit_price),
      follows: unit === "hr" || !areas ? "" : t.follows ?? "",
      checklist_note: t.checklist_note ?? "",
      crew_size: sub || blankNum(t.crew_size) ? null : Math.max(1, Math.round(num(t.crew_size))),
      cost_rate: t.kind === "sub" ? null : optNum(t.cost_rate),
      charge_rate: t.kind === "sub" ? null : optNum(t.charge_rate),
      sub_id: t.kind === "sub" ? t.sub_id || null : null,
      sub_price: t.kind === "sub" ? optNum(t.sub_price) : null,
      sub_quote_link: t.kind === "sub" ? (t.sub_quote_link ?? "").trim() : "",
      markup_pct: t.kind === "sub" ? optNum(t.markup_pct) : null,
      template_id: t.template_id || null,
      };
    }),
  };
}

/* A crew task's markup: what we charge over what it costs. Tasks priced by
   the unit carry it in their price per unit; hourly ones in the charge rate. */
const priceByUnit = (t, x) => (t.unit ?? "hr") !== "hr" && (!blankNum(t.unit_price) || (x.units > 0 && x.hours > 0 && blankNum(t.charge_rate)));
function taskMarkup(t, areas) {
  const x = taskNums(t, areas);
  if (priceByUnit(t, x)) return x.cost > 0 && !blankNum(t.unit_price) ? x.charge / x.cost - 1 : null;
  return num(t.cost_rate) > 0 && !blankNum(t.charge_rate) ? num(t.charge_rate) / num(t.cost_rate) - 1 : null;
}
function withMarkup(t, pct, areas) {
  const x = taskNums(t, areas);
  const k = 1 + num(pct) / 100;
  if (priceByUnit(t, x)) return x.cost > 0 && x.units > 0 ? { ...t, unit_price: String(Math.round(((x.cost * k) / x.units) * 1000) / 1000) } : t;
  return num(t.cost_rate) > 0 ? { ...t, charge_rate: String(Math.round(num(t.cost_rate) * k * 100) / 100) } : t;
}
const canMarkUp = (t, areas) => {
  const x = taskNums(t, areas);
  return priceByUnit(t, x) ? x.cost > 0 && x.units > 0 : num(t.cost_rate) > 0;
};

// Set every crew task to the same markup in one go (each can still be changed after).
function LaborMarkupAll({ tasks, areas, onApply }) {
  const [pct, setPct] = useState("");
  const crew = tasks.filter((t) => t.kind !== "sub" && canMarkUp(t, areas));
  if (!crew.length) return null;
  const marks = crew.map((t) => taskMarkup(t, areas)).filter((m) => m != null);
  const same = marks.length === crew.length && marks.every((m) => Math.abs(m - marks[0]) < 0.0005);
  return (
    <div className="labor-all">
      <label>
        Labor: set every crew task to
        <span className="affix">
          <NumInput decimals={1} value={pct} onChange={setPct} placeholder={same ? String(Math.round(marks[0] * 1000) / 10) : "—"} />
          <span aria-hidden="true">%</span>
        </span>
      </label>
      <button type="button" className="btn-ghost" disabled={pct === ""} onClick={() => onApply(pct)}>
        Apply to {crew.length} task{crew.length > 1 ? "s" : ""}
      </button>
      <span className="help">{same ? `All crew tasks are at ${pctText(marks[0])}.` : "Crew tasks have different markups right now."}</span>
    </div>
  );
}

// ---------- one task row ----------

function SubCard({ sub, quote, onOpen }) {
  return (
    <div className="sub-card">
      <p>
        <b>{sub.name}</b>
        {sub.trade && <span className="sub-inline"> · {sub.trade}</span>}
      </p>
      {(sub.contact_name || sub.phone || sub.email) && (
        <p>
          {sub.contact_name && <>{sub.contact_name} · </>}
          {sub.phone && <a href={`tel:${sub.phone}`}>{sub.phone}</a>}
          {sub.phone && sub.email && " · "}
          {sub.email && <a href={`mailto:${sub.email}`}>{sub.email}</a>}
        </p>
      )}
      {quote && (
        <p>
          Their quote for this job:{" "}
          <a href={quote} target="_blank" rel="noopener noreferrer">
            open it
          </a>
        </p>
      )}
      {sub.links && <LinkList text={sub.links} />}
      {sub.notes && <p className="pre sub">{sub.notes}</p>}
      {onOpen && (
        <button type="button" className="link" onClick={onOpen}>
          Open {sub.name}'s page
        </button>
      )}
    </div>
  );
}

function NewSubForm({ onSaved, onCancel }) {
  const [f, setF] = useState({ name: "", trade: "", phone: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    if (!f.name.trim()) return setError("Give the sub a name.");
    setBusy(true);
    setError(null);
    try {
      const s = await api("/api/library/subs", { method: "POST", body: f });
      await reloadLibrary();
      onSaved(s);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <div className="new-sub">
      <label>
        Sub's name
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus />
      </label>
      <label>
        Trade
        <input value={f.trade} onChange={(e) => setF({ ...f, trade: e.target.value })} placeholder="Fence, lighting, paving…" />
      </label>
      <label>
        Phone
        <input type="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
      </label>
      {error && <p className="err">{error}</p>}
      <div className="note-buttons">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className="btn" onClick={save} disabled={busy}>
          {busy ? "Adding…" : "Add sub"}
        </button>
      </div>
    </div>
  );
}

function TaskRow({ t, i, count, lib, pricing, markups, areas, canAddToLibrary, bad, set, setMany, move, remove, insert, go, lines = [], renderLine, onAddLine, lineMoney }) {
  const [showSub, setShowSub] = useState(false);
  const [addingSub, setAddingSub] = useState(false);
  const [libError, setLibError] = useState(null);
  const tasks = (lib?.tasks ?? []).filter((x) => x.active);
  const subs = (lib?.subs ?? []).filter((x) => x.active || x.id === t.sub_id);
  const sub = subs.find((s) => s.id === t.sub_id);
  const linked = t.template_id && tasks.some((x) => x.id === t.template_id);
  const isSub = t.kind === "sub";
  const n = num;
  const x = taskNums(t, areas);
  const cost = isSub ? n(t.sub_price) : x.cost;
  const charge = isSub ? null : x.charge;
  const unit = t.unit ?? "hr";
  const byUnit = unit !== "hr";
  const short = UNIT_SHORT[unit];
  // The court figure this task can follow, and whether it's following it now.
  const canFollow = areas ? t.follows || defaultFollows(unit, t.task_type) : "";
  const following = !!(t.follows && areas && areas[t.follows] != null);
  const markup = taskMarkup(t, areas);
  // Labor hours are everyone's hours together: 4 people for 8 hours is 32.
  const people = Math.max(1, Math.round(num(t.crew_size)) || 1);
  const siteHours = blankNum(t.site_hours) || x.worked ? x.hours / people : num(t.site_hours);
  const linesCost = lines.reduce((s2, [c]) => s2 + lineMoney(c).cost, 0);
  const linesCharge = lines.reduce((s2, [c]) => s2 + lineMoney(c).charge, 0);
  const subCharge = isSub ? cost * (1 + markupOf(t, "subcontractor", markups) / 100) : 0;
  const taskCost = cost + linesCost;
  const taskCharge = (isSub ? subCharge : charge) + linesCharge;
  const [showRate, setShowRate] = useState(() => !blankNum(t.production_rate)); // stays open while the rate is retyped
  const rateShown = showRate || !blankNum(t.production_rate);

  async function addToLibrary(name, close) {
    setLibError(null);
    try {
      const created = await api("/api/library/tasks", {
        method: "POST",
        body: {
          name, task_type: t.task_type, kind: t.kind, cost_rate: optNum(t.cost_rate), charge_rate: optNum(t.charge_rate),
          unit, production_rate: byUnit ? optNum(t.production_rate) : null, unit_price: byUnit ? optNum(t.unit_price) : null,
          coats: unit === "sf_coat" ? optNum(t.coats) : null,
        },
      });
      const fresh = await reloadLibrary();
      setMany(fromTemplate(created, fresh?.defaults ?? lib?.defaults));
      close();
    } catch (e) {
      setLibError(e.message);
    }
  }

  return (
    <li id={`row-${t.key}`} className={`task-row${bad ? " is-invalid" : ""}${isSub ? " is-sub" : ""}`}>
      <span className="task-num" aria-hidden="true">
        {i + 1}
      </span>
      <div className="tr-main">
        <div className="tr-name">
          {lib ? (
            <Picker
              value={t.name}
              label={`Task ${i + 1} name`}
              placeholder="Search tasks: grading, pressure wash…"
              invalid={bad}
              options={tasks}
              emptyHint="Type part of the task name, any order"
              onChange={(v) => setMany({ name: v, template_id: t.template_id && tasks.find((x) => x.id === t.template_id && sameName(x.name, v)) ? t.template_id : null })}
              onPick={(entry) => setMany(fromTemplate(entry, lib.defaults))}
              renderOption={(entry, via) => (
                <>
                  <span className="po-name">{entry.name}</span>
                  <span className="po-meta">
                    {via && <>“{via}” · </>}
                    {TASK_TYPE_LABEL[entry.task_type]}
                    {entry.kind === "sub" && " · usually a sub"}
                  </span>
                </>
              )}
              footer={(text, close) =>
                text && !tasks.some((x) => sameName(x.name, text)) ? (
                  <>
                    {canAddToLibrary && (
                      <button type="button" className="link" onPointerDown={(e) => e.preventDefault()} onClick={() => addToLibrary(text, close)}>
                        + Add “{text}” to the task library
                      </button>
                    )}
                    <button type="button" className="link muted" onPointerDown={(e) => e.preventDefault()} onClick={close}>
                      Use “{text}” just on this {pricing ? "estimate" : "job"}
                    </button>
                    {libError && <span className="err">{libError}</span>}
                  </>
                ) : null
              }
            />
          ) : (
            <input value={t.name} onChange={(e) => set("name", e.target.value)} placeholder="Task name" aria-label={`Task ${i + 1} name`} aria-invalid={bad || undefined} />
          )}
          {t.checklist_note && (
            <p className="tr-from-sales">
              <b>From the site checklist:</b> {t.checklist_note}
            </p>
          )}
          <span className="tr-badges">
            {linked ? (
              <span className="badge ok">{TASK_TYPE_LABEL[t.task_type]}</span>
            ) : lib && t.name.trim() ? (
              <span className="badge warn">Not in the library</span>
            ) : null}
          </span>
        </div>

        <div className="tr-kind" role="group" aria-label={`Task ${i + 1}: who does it`}>
          <button type="button" aria-pressed={!isSub} onClick={() => set("kind", "crew")}>
            Our crew
          </button>
          <button type="button" aria-pressed={isSub} onClick={() => set("kind", "sub")} disabled={t.has_time}>
            Sub
          </button>
        </div>

        {(!linked || !lib) && (
          <label className="tr-type">
            <span className="tr-label">Type of work</span>
            <select value={t.task_type} onChange={(e) => set("task_type", e.target.value)}>
              {TASK_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
        )}

        {!isSub ? (
          <>
            <div className="tr-measure">
              <label>
                <span className="tr-label">Measured in</span>
                <select
                  value={unit}
                  onChange={(e) => {
                    const u = e.target.value;
                    // a rate means something different in each unit, so it starts over
                    setMany({ unit: u, production_rate: "", unit_price: "", follows: areas ? defaultFollows(u, t.task_type) : "", coats: u === "sf_coat" ? t.coats || "2" : "" });
                  }}
                >
                  {TASK_UNITS.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </label>
              {byUnit && (
                <label>
                  <span className="tr-label">{unit === "sf_coat" ? "Area (SF)" : `Quantity (${short})`}</span>
                  <NumInput
                    decimals={2}
                    value={following ? String(areas[t.follows]) : t.quantity}
                    onChange={(v) => setMany({ quantity: v, follows: "" })}
                    placeholder={unit === "ls" ? "1" : "0"}
                    className={following ? "is-auto" : undefined}
                  />
                </label>
              )}
              {unit === "sf_coat" && (
                <label>
                  <span className="tr-label">Coats</span>
                  <NumInput decimals={1} value={t.coats} onChange={(v) => set("coats", v)} placeholder="1" />
                </label>
              )}
              {byUnit && rateShown && (
                <label>
                  <span className="tr-label">{rateLabel(unit)}</span>
                  <NumInput decimals={3} value={t.production_rate} onChange={(v) => set("production_rate", v)} placeholder={PER_HOUR.has(unit) ? "one person" : "hrs"} />
                </label>
              )}
              {byUnit && canFollow && (
                <p className="tr-follow help">
                  {following ? (
                    <>From the {FOLLOWS_LABEL[t.follows]} ({fmt(areas[t.follows], 0)}{t.follows === "courts" ? "" : " SF"}). Type a number to override it.</>
                  ) : areas[canFollow] != null ? (
                    <>
                      Typed in.{" "}
                      <button type="button" className="link" onClick={() => setMany({ follows: canFollow, quantity: "" })}>
                        Use the {FOLLOWS_LABEL[canFollow]} ({fmt(areas[canFollow], 0)})
                      </button>
                    </>
                  ) : t.follows ? (
                    <>Fills in from the {FOLLOWS_LABEL[t.follows]} once the court size is set.</>
                  ) : null}
                </p>
              )}
              {byUnit && !rateShown && (
                <button type="button" className="link tr-rate-link" onClick={() => setShowRate(true)}>
                  Work out the hours from a production rate
                </button>
              )}
            </div>
            <div className="tr-groups">
              <div className="tr-group">
                <span className="tr-cap">Our cost</span>
                <div className="tr-pair">
                  <label>
                    <span className="tr-label">People on it</span>
                    <NumInput
                      decimals={0}
                      value={t.crew_size ?? ""}
                      onChange={(v) => setMany({ crew_size: v, ...(x.worked ? {} : { estimated_hours: String(siteHours * (num(v) || 1)) }) })}
                      placeholder="1"
                    />
                  </label>
                  <label>
                    <span className="tr-label">Hours to finish</span>
                    {x.worked ? (
                      <span className="tr-calc" title="Worked out from the quantity and production rate">
                        {fmt(siteHours, 1)} <span className="sub-inline">from the rate</span>
                      </span>
                    ) : (
                      <NumInput
                        value={t.site_hours ?? ""}
                        onChange={(v) => setMany({ site_hours: v, estimated_hours: String(num(v) * people) })}
                        placeholder={blankNum(t.site_hours) && num(t.estimated_hours) > 0 ? fmt(siteHours, 1) : "0"}
                      />
                    )}
                  </label>
                  <p className="tr-calc-line">
                    = <b>{fmt(x.hours, 1)} labor hours</b>
                    {people > 1 && ` (${people} people × ${fmt(siteHours, 1)} hrs)`}
                  </p>
                  <label>
                    <span className="tr-label">Our cost / hr, each</span>
                    <span className="affix">
                      <span aria-hidden="true">$</span>
                      <NumInput value={t.cost_rate} onChange={(v) => set("cost_rate", v)} placeholder="0.00" />
                    </span>
                  </label>
                </div>
              </div>
              {pricing && (
                <div className="tr-group is-price">
                  <span className="tr-cap">
                    Customer price{lines.length ? ", labor" : ""} <span className="tr-cap-amt">{money2(charge)}</span>
                  </span>
                  <div className="tr-pair">
                    {byUnit ? (
                      <label>
                        <span className="tr-label">Price / {unit === "sf_coat" ? "SF a coat" : short}</span>
                        <span className="affix">
                          <span aria-hidden="true">$</span>
                          <NumInput
                            decimals={3}
                            value={t.unit_price}
                            onChange={(v) => set("unit_price", v)}
                            placeholder={x.units > 0 && n(t.charge_rate) > 0 ? fmt((x.hours * n(t.charge_rate)) / x.units, 3) : "0.00"}
                          />
                        </span>
                      </label>
                    ) : (
                      <label>
                        <span className="tr-label">Price / hr</span>
                        <span className="affix">
                          <span aria-hidden="true">$</span>
                          <NumInput value={t.charge_rate} onChange={(v) => set("charge_rate", v)} placeholder="0.00" />
                        </span>
                      </label>
                    )}
                    <label>
                      <span className="tr-label">Labor markup</span>
                      <span className="affix">
                        <NumInput
                          decimals={1}
                          value={markup == null ? "" : String(Math.round(markup * 1000) / 10)}
                          onChange={(v) => setMany(withMarkup(t, v, areas))}
                          placeholder={canMarkUp(t, areas) ? "0" : "—"}
                          disabled={!canMarkUp(t, areas)}
                          title={canMarkUp(t, areas) ? "" : "Fill in our cost first"}
                        />
                        <span aria-hidden="true">%</span>
                      </span>
                    </label>
                  </div>
                </div>
              )}
            </div>
            {pricing && (
              <p className="help tr-explain">
                {byUnit
                  ? `Type the customer's price per ${unit === "sf_coat" ? "SF a coat" : short}, or our cost and a markup. Our cost can stay blank if you only price it by the ${short}; fill it in to see the profit.`
                  : "Type our cost and a markup, or the customer's price per hour. Either way the other one fills in."}
              </p>
            )}
          </>
        ) : (
          <div className="tr-sub">
            {addingSub ? (
              <NewSubForm
                onCancel={() => setAddingSub(false)}
                onSaved={(s) => {
                  setAddingSub(false);
                  set("sub_id", s.id);
                }}
              />
            ) : (
              <label>
                <span className="tr-label">Subcontractor</span>
                <select
                  value={t.sub_id ?? ""}
                  onChange={(e) => (e.target.value === "__new" ? setAddingSub(true) : set("sub_id", e.target.value))}
                >
                  <option value="">{lib ? "Pick a sub…" : "Sub list not available"}</option>
                  {lib && <option value="__new">+ New sub</option>}
                  {subs.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                      {s.trade ? ` (${s.trade})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              <span className="tr-label">Sub's price</span>
              <span className="affix">
                <span aria-hidden="true">$</span>
                <NumInput value={t.sub_price} onChange={(v) => set("sub_price", v)} placeholder="0.00" />
              </span>
            </label>
            {pricing && (
              <label>
                <span className="tr-label">Markup</span>
                <span className="affix">
                  <NumInput decimals={1} value={t.markup_pct ?? ""} onChange={(v) => set("markup_pct", v)} placeholder={`${num(markups?.subcontractor)} (default)`} />
                  <span aria-hidden="true">%</span>
                </span>
              </label>
            )}
            <label className="tr-wide">
              <span className="tr-label">Their quote (link)</span>
              <input value={t.sub_quote_link ?? ""} onChange={(e) => set("sub_quote_link", e.target.value)} placeholder="https://drive.google.com/…" />
            </label>
            {sub && (
              <button type="button" className="link tr-wide sub-toggle" onClick={() => setShowSub((x) => !x)} aria-expanded={showSub}>
                {showSub ? "Hide" : "Show"} {sub.name}'s info
              </button>
            )}
            {sub && showSub && (
              <div className="tr-wide">
                <SubCard sub={sub} quote={t.sub_quote_link} onOpen={go ? () => go("library", { view: "sub", id: sub.id }) : null} />
              </div>
            )}
          </div>
        )}

        {renderLine && (
          <div className="tr-lines">
            {lines.length > 0 && <ol className="line-edit in-task">{lines.map(([c, li]) => renderLine(c, li))}</ol>}
            <div className="tr-line-add">
              <button type="button" className="link" onClick={() => onAddLine("material")}>
                + Add material
              </button>
              <button type="button" className="link" onClick={() => onAddLine("equipment")}>
                + Add equipment
              </button>
              <button type="button" className="link" onClick={() => onAddLine("other")}>
                + Other cost
              </button>
            </div>
          </div>
        )}

        <div className="tr-total">
          <span className="tr-total-what">
            {byUnit && !isSub && x.units > 0 && (
              <>
                {fmt(x.units)} {short}
                {unit === "sf_coat" && n(t.coats) > 1 && ` (${n(t.coats)} coats)`}
                {" · "}
              </>
            )}
            {isSub ? "Sub's price" : `${fmt(x.hours, 1)} labor hrs`}
            {lines.length > 0 && ` + ${lines.length} material/other line${lines.length > 1 ? "s" : ""}`}
            {!isSub && x.hours > 0 && n(t.cost_rate) === 0 && <span className="t-near"> · no cost per hour</span>}
          </span>
          <span className="tr-total-figs">
            <span>
              Our cost <b>{money2(taskCost)}</b>
            </span>
            {pricing && (
              <span className="tr-total-price">
                Customer price <b>{money2(taskCharge)}</b>
              </span>
            )}
            {pricing && taskCharge > 0 && (
              <span className={taskCharge < taskCost ? "t-over" : (taskCharge - taskCost) / taskCharge < 0.15 ? "t-near" : ""}>
                {Math.round(((taskCharge - taskCost) / taskCharge) * 100)}% margin
              </span>
            )}
            {pricing && taskCharge === 0 && (x.hours > 0 || x.units > 0 || linesCost > 0) && <span className="t-near">no customer price yet</span>}
          </span>
        </div>
      </div>

      <span className="te-tools tr-tools">
        <button type="button" className="icon" onClick={() => move(-1)} disabled={i === 0} aria-label={`Move task ${i + 1} up`}>
          ▲
        </button>
        <button type="button" className="icon add-here" onClick={insert} aria-label={`Add a task after task ${i + 1}`} title="Add a task right below this one">
          +
        </button>
        <button type="button" className="icon" onClick={() => move(1)} disabled={i === count - 1} aria-label={`Move task ${i + 1} down`}>
          ▼
        </button>
        <button
          type="button"
          className="icon remove"
          onClick={remove}
          disabled={t.has_time}
          title={t.has_time ? "Crew time is logged on this task" : ""}
          aria-label={`Remove task ${i + 1}`}
        >
          ✕
        </button>
      </span>
    </li>
  );
}

/* The form for a job or an estimate: who and where, kind of work, tasks and
   hours, materials and other costs, and the money. Wrappers (JobEditor,
   EstimateEditor) supply how it loads and saves and any fields of their own.
   `pricing` (estimates) adds charge rates, markups and the built price.

   Unsaved work is kept on this device (draftKey) until it's saved or thrown
   away, so tapping another tab or the phone closing the app doesn't lose it. */
export function ScopeEditor({
  me,
  go,
  pricing = false,
  draftKey,
  load, // async () => form state; omit for a brand-new form
  blank = blankJob, // (lib) => form state
  starter = (court, scope, lib) => starterTasks(court, scope, lib), // the starter task list for a new form
  title,
  backLabel,
  submitLabel,
  labels = {},
  clientField, // (form, set) => element in place of the plain client box
  extraTop, // (form, set) => element under the main fields
  intro, // (form, set) => panels after the first one (e.g. what sales found on site)
  extraPanels, // (form, set) => panels before the money
  footer, // (form, set) => element above the save button
  validate, // (form) => message or null, checked before saving
  submit, // async (form, body) => result
  onDone,
  onCancel,
}) {
  const isNew = !load;
  const lib = useLibrary();
  const L = { name: "Job name", namePlaceholder: "Client – court count and work", price: "Contract amount", priceRow: "Contract", ...labels };
  const [draft] = useState(() => safeGet(draftKey));
  const [job, setJob] = useState(() => (isNew ? draft?.job ?? blank(lib) : null));
  const [touchedTasks, setTouchedTasks] = useState(() => (isNew ? !!draft?.touchedTasks : true));
  const [restoredAt, setRestoredAt] = useState(() => (isNew && draft ? draft.savedAt : null));
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
    if (isNew) return;
    const saved = reload === 0 ? safeGet(draftKey) : null;
    if (saved?.job) {
      setJob(saved.job);
      setRestoredAt(saved.savedAt);
      return;
    }
    load()
      .then((f) => setJob(linkTaskKeys(f)))
      .catch((e) => setError(e.message));
  }, [draftKey, reload]);

  // When the library arrives after a new, untouched form opened, link the
  // starter tasks to it and fill in the default markups.
  useEffect(() => {
    if (!lib || !job) return;
    setJob((j) => {
      let next = j;
      if (isNew && !touchedTasks && !j.tasks.some((t) => t.template_id)) next = { ...next, tasks: starter(j.court_type, j.scope_type, lib) };
      if (pricing && !next.markups) next = { ...next, markups: markupsFrom(lib.defaults) };
      if (pricing && !next.court) next = { ...next, court: blankCourt() }; // drafts from before court sizes
      return next;
    });
  }, [lib, !!job]);

  // A permits task brings a fee line for the city's fees (passed through at
  // cost), so they're not forgotten. Remove the line and it stays removed.
  useEffect(() => {
    if (!job || !pricing || !lib) return; // the starter list is swapped in when the library arrives
    if (!job.tasks.some((t) => /permit/i.test(t.name) && !t.fee_added)) return;
    setJob((j) => {
      const need = j.tasks.filter((t) => /permit/i.test(t.name) && !t.fee_added);
      const keys = new Set(j.tasks.map((t) => t.key));
      return {
        ...j,
        tasks: j.tasks.map((t) => (need.includes(t) ? { ...t, fee_added: true } : t)),
        cost_lines: [
          // drop an untouched fee line left from a starter list that was swapped out
          ...j.cost_lines.filter((c) => !(c.auto_fee && !keys.has(c.task_key) && !num(c.unit_cost))),
          ...need
            .filter((t) => !j.cost_lines.some((c) => c.category === "fee" && c.task_key === t.key))
            .map((t) => ({ ...blankLine("fee"), description: "Permit and inspection fees (city / county)", quantity: "1", task_key: t.key, auto_fee: true })),
        ],
      };
    });
  }, [job?.tasks, lib]);

  // Keep a copy of unsaved work on this device after every change.
  useEffect(() => {
    if (dirty && job) safeSet(draftKey, { job, touchedTasks, savedAt: Date.now() });
  }, [dirty, job, touchedTasks]);

  const est = useMemo(() => (job ? estimateOf(job) : null), [job]);

  if (!job) return <p className="empty">{error ? `Couldn't load it: ${error}` : "Loading…"}</p>;

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
    safeSet(draftKey, null);
    setRestoredAt(null);
    setDirty(false);
    setBad(null);
    setError(null);
    setLocMsg(null);
    if (!isNew) {
      setJob(null);
      setReload((n) => n + 1);
    } else {
      setTouchedTasks(false);
      const b = blank(lib);
      setJob(pricing ? { ...b, markups: b.markups ?? markupsFrom(lib?.defaults) } : b);
    }
  }

  const set = (k, v) => change((j) => ({ ...j, [k]: v }));
  const setTaskFields = (i, fields) => {
    setTouchedTasks(true);
    if ("name" in fields) clearBad(job.tasks[i].key);
    change((j) => ({ ...j, tasks: j.tasks.map((t, n) => (n === i ? { ...t, ...fields } : t)) }));
  };
  const moveTask = (i, d) =>
    change((j) => {
      const tasks = [...j.tasks];
      [tasks[i], tasks[i + d]] = [tasks[i + d], tasks[i]];
      return { ...j, tasks };
    });
  const removeTask = (i) => change((j) => ({ ...j, tasks: j.tasks.filter((_, n) => n !== i) }));
  const addTaskAt = (at) => {
    setTouchedTasks(true);
    change((j) => ({ ...j, tasks: [...j.tasks.slice(0, at), blankTask(), ...j.tasks.slice(at)] }));
  };
  const addLineFor = (taskKey, category) =>
    change((j) => ({ ...j, cost_lines: [...j.cost_lines, { ...blankLine(category), task_key: taskKey }] }));
  const addTask = () => {
    setTouchedTasks(true);
    change((j) => ({ ...j, tasks: [...j.tasks, blankTask()] }));
  };

  const setLine = (i, k, v) => change((j) => ({ ...j, cost_lines: j.cost_lines.map((c, n) => (n === i ? { ...c, [k]: v } : c)) }));
  const setLineFields = (i, fields) => {
    if ("description" in fields) clearBad(job.cost_lines[i].key);
    change((j) => ({ ...j, cost_lines: j.cost_lines.map((c, n) => (n === i ? { ...c, ...fields } : c)) }));
  };
  const pickItem = (i, item) =>
    setLineFields(i, { description: item.name, item_id: item.id, category: item.category, unit: item.unit, unit_cost: item.unit_cost ?? job.cost_lines[i].unit_cost });
  const itemById = Object.fromEntries(items.map((it) => [it.id, it]));
  const removeLine = (i) => change((j) => ({ ...j, cost_lines: j.cost_lines.filter((_, n) => n !== i) }));
  const addLine = (category) => change((j) => ({ ...j, cost_lines: [...j.cost_lines, blankLine(category)] }));

  // On a new form, picking court type or scope swaps in the matching starter
  // list until someone edits the tasks by hand.
  const setKind = (k, v) => {
    change((j) => {
      const next = { ...j, [k]: v };
      if (isNew && !touchedTasks) next.tasks = starter(next.court_type, next.scope_type, lib);
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
    const line = composeAddress(job.site ?? addressFrom({}, "site", job.address));
    if (line.length < 5) return setLocMsg({ tone: "err", text: "Type the street address, city and ZIP first." });
    setFinding(true);
    try {
      const hit = await api(`/api/geocode?address=${encodeURIComponent(line)}`);
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
      row?.querySelector("input, select, textarea")?.focus({ preventScroll: true });
    });
  }

  async function save(e) {
    e.preventDefault();
    setError(null);
    setBad(null);
    const own = validate?.(job, est);
    if (own) return own.key ? flag(own.key, own.message) : setError(own.message ?? own);
    const missing = job.tasks.findIndex((t) => !t.name.trim());
    if (missing >= 0) return flag(job.tasks[missing].key, `Task ${missing + 1} needs a name. It's marked in red above.`);
    const noSub = job.tasks.findIndex((t) => t.kind === "sub" && !t.sub_id && lib);
    if (noSub >= 0) return flag(job.tasks[noSub].key, `Task ${noSub + 1} is a sub task. Pick the sub, or switch it to Our crew.`);
    // A line added by mistake and never filled in is just dropped.
    const empty = (c) => !c.description.trim() && !num(c.quantity) && !num(c.unit_cost);
    const form = job.cost_lines.some(empty) ? { ...job, cost_lines: job.cost_lines.filter((c) => !empty(c)) } : job;
    if (form !== job) setJob(form);
    const noDesc = form.cost_lines.findIndex((c) => !c.description.trim());
    if (noDesc >= 0)
      return flag(form.cost_lines[noDesc].key, `Line ${noDesc + 1} (${CATEGORY_LABEL[form.cost_lines[noDesc].category]}) needs a name. It's marked in red above.`);
    setSaving(true);
    try {
      const result = await submit(form, scopeBody(form), est);
      safeSet(draftKey, null);
      onDone(result);
    } catch (err) {
      setError(err.status === 0 ? "No connection. Your work is kept on this device; save again when you have signal." : err.message);
      setSaving(false);
    }
  }

  const areas = courtAreas(job.court); // estimates only; jobs have no court size
  const lineFollows = (c) => !!(c.follows && num(c.coverage) > 0 && areas?.[c.follows] != null);
  const noHours = job.tasks.filter((t) => t.kind !== "sub" && taskNums(t, areas).hours === 0).length;
  const hasPin = job.lat != null && job.lat !== "" && job.lng != null && job.lng !== "";
  const offList = lib ? job.tasks.filter((t) => t.name.trim() && !(t.template_id && lib.tasks.some((x) => x.id === t.template_id))).length : 0;

  // What one cost line costs us (with tax on materials) and what we charge for it.
  const lineMoney = (c) => {
    const cost = lineQty(c, areas) * num(c.unit_cost);
    if (c.category === "fee") return { cost, charge: cost };
    const withTax = cost * (1 + (c.category === "material" ? num(job.sales_tax_pct) / 100 : 0));
    return { cost: withTax, charge: withTax * (1 + markupOf(c, c.category, job.markups) / 100) };
  };

  // A cost line tied to a task shows on that task; the rest are for the whole job.
  const onTask = (c) => c.task_key && job.tasks.some((t) => t.key === c.task_key);
  const jobLines = job.cost_lines.map((c, i) => [c, i]).filter(([c]) => !onTask(c));
  const renderLine = (c, i) => (
              <li key={c.key} id={`row-${c.key}`} data-cat={c.category} className={bad === c.key ? "is-invalid" : undefined}>
                <div className="le-desc">
                  <span className="le-label">
                    Line {i + 1} · {c.category === "equipment" ? (c.in_house ? "In-house equipment" : "Rental") : CATEGORY_LABEL[c.category]}
                  </span>
                  <Picker
                    value={c.description}
                    label={`Line ${i + 1} item`}
                    placeholder={items.length ? "Search the price list or type" : "e.g. Acrylic resurfacer"}
                    invalid={bad === c.key}
                    options={items.filter((it) => it.active !== false)}
                    emptyHint="Type part of the item name"
                    noMatchText="Not on the price list. It'll be used as typed."
                    onChange={(v) => {
                      const it = c.item_id && itemById[c.item_id];
                      setLineFields(i, { description: v, ...(it && !sameName(it.name, v) ? { item_id: null } : {}) });
                    }}
                    onPick={(it) => pickItem(i, it)}
                    renderOption={(it) => (
                      <>
                        <span className="po-name">{it.name}</span>
                        <span className="po-meta">
                          {CATEGORY_LABEL[it.category]}
                          {it.unit_cost != null && ` · ${money2(it.unit_cost)} / ${it.unit || "each"}`}
                        </span>
                      </>
                    )}
                  />
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
                </div>
                <label className="le-cat">
                  <span className="le-label">Type</span>
                  <select
                    value={c.category === "equipment" && c.in_house ? "equipment_in_house" : c.category}
                    onChange={(e) =>
                      e.target.value === "equipment_in_house"
                        ? setLineFields(i, { category: "equipment", in_house: true })
                        : setLineFields(i, { category: e.target.value, in_house: false })
                    }
                  >
                    <option value="material">Material</option>
                    <option value="equipment">Equipment rental</option>
                    <option value="equipment_in_house">Equipment, in-house</option>
                    <option value="subcontractor">Sub (not tied to a task)</option>
                    <option value="other">Other</option>
                    <option value="fee">Permit / city fee (at cost)</option>
                  </select>
                </label>
                <label className="le-qty">
                  <span className="le-label">Qty</span>
                  <NumInput
                    decimals={3}
                    value={lineFollows(c) ? String(lineQty(c, areas)) : c.quantity}
                    onChange={(v) => setLineFields(i, { quantity: v, follows: "" })}
                    placeholder="0"
                    className={lineFollows(c) ? "is-auto" : undefined}
                  />
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
                  <span>{money2(lineQty(c, areas) * num(c.unit_cost))}</span>
                </span>
                {pricing && c.category === "fee" && (
                  <p className="le-markup help">Passed through at cost, no markup. Listed on the proposal so the customer sees it's included.</p>
                )}
                {pricing && c.category !== "fee" && (
                  <div className="le-markup">
                    <label>
                      <span className="le-label vis">Markup</span>
                      <span className="affix">
                        <NumInput
                          decimals={1}
                          value={c.markup_pct ?? ""}
                          onChange={(v) => setLine(i, "markup_pct", v)}
                          placeholder={`${num(job.markups?.[c.category])} (default)`}
                          aria-label={`Line ${i + 1} markup percent`}
                        />
                        <span aria-hidden="true">%</span>
                      </span>
                    </label>
                    <span className="le-price">
                      Price{" "}
                      {money2(
                        lineQty(c, areas) * num(c.unit_cost) * (1 + (c.category === "material" ? num(job.sales_tax_pct) / 100 : 0)) *
                          (1 + markupOf(c, c.category, job.markups) / 100)
                      )}
                      {c.category === "material" && num(job.sales_tax_pct) > 0 && <span className="sub-inline"> with tax</span>}
                    </span>
                  </div>
                )}
                <label className="le-task">
                  <span className="le-label">For task</span>
                  <select value={c.task_key ?? ""} onChange={(e) => setLine(i, "task_key", e.target.value)}>
                    <option value="">Whole job</option>
                    {job.tasks.map((t, ti) => (
                      <option key={t.key} value={t.key}>{t.name || `Task ${ti + 1}`}</option>
                    ))}
                  </select>
                </label>
                <span className="te-tools le-tools">
                  <button type="button" className="icon remove remove-text" onClick={() => removeLine(i)} aria-label={`Remove line ${i + 1}`}>
                    ✕ Remove
                  </button>
                </span>
                {areas && c.category === "material" && (
                  <div className="le-cover">
                    {c.follows ? (
                      <>
                        <div className="le-cover-grid">
                          <label>
                            <span className="le-label vis">Area</span>
                            <select value={c.follows} onChange={(e) => setLine(i, "follows", e.target.value)}>
                              <option value="paint">Paintable area</option>
                              <option value="surface">Surface area</option>
                            </select>
                          </label>
                          <label>
                            <span className="le-label vis">Coats</span>
                            <NumInput decimals={1} value={c.coats} onChange={(v) => setLine(i, "coats", v)} placeholder="1" />
                          </label>
                          <label>
                            <span className="le-label vis">One {c.unit || "unit"} covers (SF per coat)</span>
                            <NumInput decimals={1} value={c.coverage} onChange={(v) => setLine(i, "coverage", v)} placeholder="SF" />
                          </label>
                        </div>
                        <p className="help">
                          {areas[c.follows] == null
                            ? "Set the court size above and the quantity fills in."
                            : num(c.coverage) > 0
                              ? `${fmt(areas[c.follows], 0)} SF × ${num(c.coats) || 1} coat${num(c.coats) > 1 ? "s" : ""} ÷ ${fmt(c.coverage)} SF a ${c.unit || "unit"} = ${fmt((areas[c.follows] * (num(c.coats) || 1)) / num(c.coverage))}, so ${lineQty(c, areas)}.`
                              : "Put in how many square feet one unit covers per coat."}{" "}
                          <button type="button" className="link" onClick={() => setLineFields(i, { follows: "", quantity: String(lineQty(c, areas) || c.quantity || "") })}>
                            Type the quantity instead
                          </button>
                        </p>
                      </>
                    ) : (
                      <button type="button" className="link" onClick={() => setLineFields(i, { follows: "paint", coats: c.coats || "2" })}>
                        Work the quantity out from the court area
                      </button>
                    )}
                  </div>
                )}
              </li>
  );

  return (
    <form className="editor" onSubmit={save} onKeyDown={noEnterSubmit}>
      <button type="button" className="link back" onClick={onCancel}>
        {backLabel}
      </button>
      <h2 className="detail-title">{title}</h2>

      {restoredAt && (
        <div className="restored" role="status">
          <span>Picked up your unsaved work from {savedAtText(restoredAt)}.</span>
          <button type="button" className="link" onClick={startOver}>
            {isNew ? "Start over" : "Throw it away"}
          </button>
        </div>
      )}

      <section className="panel">
        <h3>{labels.panel ?? "Job"}</h3>
        <div className="grid">
          {clientField ? (
            <div className="span-2">{clientField(job, set)}</div>
          ) : (
            <label className="span-2">
              Client
              <input value={job.client} onChange={(e) => set("client", e.target.value)} />
            </label>
          )}
          <label className="span-2">
            {L.name}
            <input required value={job.name} onChange={(e) => set("name", e.target.value)} placeholder={L.namePlaceholder} />
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
          {pricing ? (
            <div className="span-2 price-peek">
              <span className="fig-label">Proposal price so far</span>
              <span className="fig">{money(est.contract)}</span>
              <span className="sub">Adds itself up from the tasks, costs and markups below.</span>
            </div>
          ) : (
            <label>
              {L.price}
              <span className="affix">
                <span aria-hidden="true">$</span>
                <NumInput value={job.contract_amount} onChange={(v) => set("contract_amount", v)} placeholder="0" />
              </span>
            </label>
          )}
        </div>
        {extraTop?.(job, set)}

        <fieldset className="where">
          <legend>{labels.where ?? "Job location"}</legend>
          <p className="help">The pin flags clock-ins made away from the site. Find it from the address, or stand on the court and use your location.</p>
          <AddressFields section="site" value={job.site ?? addressFrom({}, "site", job.address)} onChange={(v) => set("site", v)} />
          <div className="grid">
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

      {intro?.(job, set)}

      {job.court && (
        <section className="panel">
          <h3>Court size</h3>
          <p className="help">
            Entered once. Tasks measured by the area pick it up: surface work (pressure wash) uses the surface, coatings use the paintable area times their coats,
            and line painting uses the number of courts. Materials can work out their pails from it too.
          </p>
          <CourtSizeFields paint court={job.court} courtType={job.court_type} onChange={(c) => set("court", c)} />
        </section>
      )}

      <section className="panel">
        <div className="panel-head">
          <h3>Tasks</h3>
          {isNew && !touchedTasks && <span className="hint">Starter list for this court type and scope</span>}
        </div>
        <p className="help">
          Search the task library by any part of the name. Each task has its own rates{pricing ? ": what it costs us and what we charge" : ""}. Tasks
          measured in SF, LF or each work out their hours from the quantity and production rate. Switch a task to <b>Sub</b> when a subcontractor does it.
        </p>
        <ol className="task-edit task-cards">
          {job.tasks.map((t, i) => (
            <TaskRow
              key={t.key}
              t={t}
              i={i}
              count={job.tasks.length}
              lib={lib}
              pricing={pricing}
              markups={job.markups}
              areas={areas}
              canAddToLibrary={me?.role === "gm"}
              bad={bad === t.key}
              go={go}
              set={(k, v) => setTaskFields(i, { [k]: v })}
              setMany={(fields) => setTaskFields(i, fields)}
              move={(d) => moveTask(i, d)}
              remove={() => removeTask(i)}
              insert={() => addTaskAt(i + 1)}
              lines={job.cost_lines.map((c, li) => [c, li]).filter(([c]) => c.task_key === t.key)}
              renderLine={renderLine}
              onAddLine={(cat) => addLineFor(t.key, cat)}
              lineMoney={lineMoney}
            />
          ))}
        </ol>
        <button type="button" className="btn-ghost add" onClick={addTask}>
          Add task
        </button>

        <p className="subtotal">
          <b>{Math.round(est.hours * 10) / 10} crew hours</b> = <b>{money(est.labor)}</b> labor cost
          {pricing && (
            <>
              {" "}· <b>{money(est.charge.labor)}</b> labor price
            </>
          )}
        </p>
        {noHours > 0 && (
          <p className="help">
            {noHours === 1 ? "1 crew task has" : `${noHours} crew tasks have`} no hours yet, so crew time on it won't have an estimate to compare against.
          </p>
        )}
        {offList > 0 && (
          <p className="help">
            {offList === 1 ? "1 task isn't" : `${offList} tasks aren't`} from the library.{" "}
            {me?.role === "gm" ? "Add them so everyone uses the same names." : "Ask the GM to add them so everyone uses the same names."}
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
        {jobLines.length === 0 ? (
          <p className="help">
            {job.cost_lines.length
              ? "Everything is on its task above. Add anything here that's for the whole job."
              : "Add materials, rentals and fees on the task they're for (+ Add material on the task), or here for the whole job."}
            {" "}Material quantities become the job's material list for the warehouse and crew lead.
          </p>
        ) : (
          <ol className="line-edit">
            <li className="line-head" aria-hidden="true">
              <span>Item</span><span>Type</span><span>Qty</span><span>Unit</span><span>Cost per unit</span><span>Total</span><span>For task</span><span />
            </li>
            {jobLines.map(([c, i]) => renderLine(c, i))}
          </ol>
        )}
        <datalist id="cf-units">
          {UNITS.map((u) => (
            <option key={u} value={u} />
          ))}
        </datalist>
        <div className="add-row">
          <button type="button" className="btn-ghost" onClick={() => addLine("material")}>Add material</button>
          <button type="button" className="btn-ghost" onClick={() => addLine("equipment")}>Add equipment</button>
          <button type="button" className="btn-ghost" onClick={() => addLine("other")}>Add other cost</button>
          <button type="button" className="btn-ghost" onClick={() => addLine("fee")}>Add permit / city fee</button>
        </div>
      </section>

      {extraPanels?.(job, set)}

      {pricing ? (
        <section className="panel">
          <h3>{labels.summary ?? "Price"}</h3>
          <PriceTable est={est} taxPct={num(job.sales_tax_pct)} adjustmentReason={job.adjustment_reason} />

          <div className="markup-controls">
            <h4>Markups</h4>
            <p className="help">
              Every line, sub and crew task can have its own markup, set right on it. These defaults cover anything left blank.
            </p>
            <div className="markup-grid">
              {[
                ["material", "Materials"],
                ["equipment", "Equipment"],
                ["subcontractor", "Subs"],
                ["other", "Other costs"],
              ].map(([k, label]) => (
                <label key={k}>
                  {label} default
                  <span className="affix">
                    <NumInput decimals={1} value={job.markups?.[k] ?? ""} onChange={(v) => set("markups", { ...(job.markups ?? {}), [k]: v })} placeholder="0" />
                    <span aria-hidden="true">%</span>
                  </span>
                </label>
              ))}
            </div>
            <LaborMarkupAll
              tasks={job.tasks}
              areas={courtAreas(job.court)}
              onApply={(pct) => change((j) => ({ ...j, tasks: j.tasks.map((t) => (t.kind === "sub" ? t : withMarkup(t, pct, courtAreas(j.court)))) }))}
            />
            <label className="overall-markup">
              Markup on the whole job <span className="optional">(added on top of everything above)</span>
              <span className="affix">
                <NumInput decimals={1} value={job.overall_markup ?? ""} onChange={(v) => set("overall_markup", v)} placeholder="0" />
                <span aria-hidden="true">%</span>
                {num(job.overall_markup) !== 0 && <span className="sub-inline"> = {money(est.overall_amount)}</span>}
              </span>
            </label>
            {lib && (
              <button type="button" className="link" onClick={() => set("markups", markupsFrom(lib.defaults))}>
                Reset the defaults to the company's (Library → Rates &amp; markups)
              </button>
            )}
          </div>

          <div className="adjust grid">
            <label>
              Adjust the price <span className="optional">(+ or −)</span>
              <span className="affix">
                <span aria-hidden="true">$</span>
                <input
                  inputMode="decimal"
                  value={job.adjustment ?? ""}
                  onChange={(e) => set("adjustment", e.target.value.replace(/[^\d.-]/g, ""))}
                  placeholder="0"
                  aria-label="Price adjustment in dollars, minus to lower it"
                />
              </span>
            </label>
            <label>
              Why? <span className="optional">(needed with an adjustment)</span>
              <input value={job.adjustment_reason ?? ""} onChange={(e) => set("adjustment_reason", e.target.value)} placeholder="e.g. Round to $9,500" maxLength={1000} />
            </label>
            <p className="help span-2">Markups and the adjustment are saved with each version and never print on the proposal.</p>
          </div>
        </section>
      ) : (
        <section className="panel">
          <h3>{labels.summary ?? "Estimate"}</h3>
          <EstimateTable est={est} taxPct={num(job.sales_tax_pct)} priceLabel={L.priceRow} />
        </section>
      )}

      {footer?.(job, set)}
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
          {saving ? "Saving…" : submitLabel}
        </button>
      </div>
      {dirty && <p className="help draft-note">Unsaved changes are kept on this device until you save or start over.</p>}
    </form>
  );
}

// A job's own form. New jobs here are ones with no estimate behind them (GM).
export default function JobEditor({ me, go, jobId, onDone, onCancel }) {
  return (
    <ScopeEditor
      me={me}
      go={go}
      draftKey={`cf.draft.job.${jobId ?? "new"}`}
      load={jobId ? () => api(`/api/jobs/${jobId}/edit`).then(formFrom) : undefined}
      title={jobId ? "Edit job" : "New job without an estimate"}
      backLabel={jobId ? "Back to job" : "All jobs"}
      submitLabel={jobId ? "Save changes" : "Create job"}
      submit={(f, body) =>
        (jobId
          ? api(`/api/jobs/${jobId}`, { method: "PUT", body: { ...body, client: f.client.trim() } })
          : api("/api/jobs", { method: "POST", body: { ...body, client: f.client.trim() } })
        ).then((saved) => saved.id)
      }
      onDone={onDone}
      onCancel={onCancel}
    />
  );
}
