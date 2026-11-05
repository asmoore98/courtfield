// How a task is measured, and the numbers that follow. Mirrors
// backend/app/quantities.py and the court size in sales_schemas.py.
//
// With a production rate, crew hours are worked out from the quantity:
//   SF, SF per coat, LF, SY  → rate is units one person does in an hour
//   each, CY, ton, lump sum  → rate is person-hours for one unit
// Crew work is charged at its price per unit, or hours × charge rate when
// it has none.
//
// A task is built up (each part priced: labor by its rate, lines with their
// markup) or priced by the unit, all in (quantity × price per unit; its lines
// are our cost inside that price). Base rock and fill can come from length ×
// width × depth. A line can follow its task: "0.75 hr for every 20 ton".

export const UNITS = [
  ["hr", "Hours"],
  ["sf", "Square feet (SF)"],
  ["sf_coat", "SF per coat"],
  ["lf", "Linear feet (LF)"],
  ["sy", "Square yards (SY)"],
  ["cy", "Cubic yards (CY)"],
  ["ton", "Tons"],
  ["acre", "Acres"],
  ["ea", "Each"],
  ["ls", "Lump sum"],
];
export const UNIT_SHORT = { hr: "hr", sf: "SF", sf_coat: "SF", lf: "LF", sy: "SY", cy: "CY", ton: "ton", acre: "acre", ea: "ea", ls: "job" };
export const PER_HOUR = new Set(["sf", "sf_coat", "lf", "sy"]);

const n = (v) => (v === "" || v == null ? 0 : Number(v));
const blank = (v) => v === "" || v == null;

// "SF / hr" or "hrs each": what the production rate means for this unit.
export const rateLabel = (unit) => (PER_HOUR.has(unit) ? `${UNIT_SHORT[unit]} per hr` : unit === "ls" ? "Hours for the job" : `Hours per ${UNIT_SHORT[unit]}`);
export const rateText = (unit, rate) =>
  blank(rate) ? "" : PER_HOUR.has(unit) ? `${fmt(rate)} ${UNIT_SHORT[unit]}/hr` : unit === "ls" ? `${fmt(rate)} hrs` : `${fmt(rate)} hrs/${UNIT_SHORT[unit]}`;
export const fmt = (v, d = 2) => (Math.round(n(v) * 10 ** d) / 10 ** d).toLocaleString("en-US");

const r2 = (v) => Math.round(v * 100) / 100;

// The court size, entered once. Length × width is the playing area; a border
// band (ft all around each court) makes the surfaced size. Surface SF,
// playing SF, border SF, paintable SF and number of courts.
export function courtAreas(court) {
  if (!court) return null;
  const courts = n(court.courts);
  const L = n(court.length_ft);
  const W = n(court.width_ft);
  const b = 2 * n(court.border_ft);
  const playing = L > 0 && W > 0 ? r2(L * W * (courts || 1)) : null;
  const auto = L > 0 && W > 0 ? r2((L + b) * (W + b) * (courts || 1)) : null;
  const surface = !blank(court.surface_sf) ? n(court.surface_sf) : auto;
  const border = surface != null && playing != null && n(court.border_ft) > 0 ? r2(Math.max(0, surface - playing)) : null;
  const paint = !blank(court.paint_sf) ? n(court.paint_sf) : surface;
  return { surface, playing, border, paint, courts: courts || null, auto };
}

export const TONS_PER_CY = 1.4; // crushed base rock, roughly; set per task

// The quantity from a size: L × W for SF and SY, with a depth for CY and tons.
export function sizeQuantity(unit, t) {
  const L = n(t.size_length_ft);
  const W = n(t.size_width_ft);
  if (!(L > 0 && W > 0)) return null;
  const sf = L * W;
  if (unit === "sf") return r2(sf);
  if (unit === "sy") return r2(sf / 9);
  if (unit === "cy" || unit === "ton") {
    const d = n(t.size_depth_in);
    if (!(d > 0)) return null;
    const cy = (sf * d) / 12 / 27;
    return r2(unit === "cy" ? cy : cy * (n(t.tons_per_cy) || TONS_PER_CY));
  }
  return null;
}
export const SIZE_UNITS = new Set(["sf", "sy", "cy", "ton"]);

// Which court figure a task follows by default, from how it's measured.
export const defaultFollows = (unit, taskType) =>
  unit === "sf" ? "surface" : unit === "sf_coat" ? "paint" : unit === "ea" && taskType === "lines" ? "courts" : "";
export const FOLLOWS_LABEL = {
  surface: "court surface", playing: "playing area", border: "border band", paint: "paintable area", courts: "number of courts",
};

// The quantity a task is using: its size, the court figure it follows, or what was typed.
export function quantityOf(t, areas) {
  if (t.follows === "size") {
    const q = sizeQuantity(t.unit, t);
    if (q != null) return q;
    return blank(t.quantity) ? null : n(t.quantity);
  }
  if (t.follows && areas && areas[t.follows] != null) return areas[t.follows];
  return blank(t.quantity) ? null : n(t.quantity);
}

export function totalUnits(unit, qty, coats) {
  if (unit === "ls") return qty || 1;
  let q = qty || 0;
  if (unit === "sf_coat") q *= blank(coats) ? 1 : n(coats);
  return q;
}

// Hours from the quantity and rate, or null when hours are typed.
export function workedHours(t, qty) {
  if (!t.unit || t.unit === "hr" || !(n(t.production_rate) > 0)) return null;
  const q = totalUnits(t.unit, qty, t.coats);
  return Math.round((PER_HOUR.has(t.unit) ? q / n(t.production_rate) : q * n(t.production_rate)) * 100) / 100;
}

// Everything about one crew task: quantity, hours, what it costs us, what we charge.
export function taskNums(t, areas, fallbackRate = 0) {
  const unit = t.unit || "hr";
  const qty = unit === "hr" ? null : quantityOf(t, areas);
  const worked = workedHours(t, qty);
  const hours = worked ?? n(t.estimated_hours);
  const rate = blank(t.cost_rate) ? fallbackRate : n(t.cost_rate);
  const cost = hours * rate;
  const units = unit === "hr" ? null : totalUnits(unit, qty, t.coats);
  const perUnit = unit !== "hr" && !blank(t.unit_price);
  const charge = perUnit ? units * n(t.unit_price) : hours * n(t.charge_rate);
  return { unit, qty, units, hours, worked: worked != null, cost, charge, perUnit };
}

// Units of material to buy to cover an area: rounded up to whole units.
export const materialQty = (area, coats, coverage) => Math.ceil(Math.round(((area * (blank(coats) ? 1 : n(coats))) / n(coverage)) * 1e6) / 1e6);

// How much of a task there is, for lines that follow it: its quantity
// (times coats), or its hours when it's measured in hours.
export function taskUnits(t, areas) {
  const x = taskNums(t, areas);
  return x.unit === "hr" ? x.hours : x.units ?? 0;
}

// A line that follows its task: `amount` for every `every` units of it. Per
// load or batch (every > 1) counts whole loads; materials are bought whole.
export function perTaskQty(units, amount, every, category) {
  if (!(n(amount) > 0) || !(units > 0)) return 0;
  const e = n(every) > 0 ? n(every) : 1;
  let loads = units / e;
  if (e > 1) loads = Math.ceil(Math.round(loads * 1e6) / 1e6);
  const q = loads * n(amount);
  return category === "material" ? Math.ceil(Math.round(q * 1e6) / 1e6) : r2(q);
}

export const AREA_FOLLOWS = new Set(["surface", "playing", "border", "paint"]);

// The quantity a cost line is using. `task` is the task it's on, if any.
export function lineQty(c, areas, task) {
  if (AREA_FOLLOWS.has(c.follows) && n(c.coverage) > 0 && areas?.[c.follows] != null)
    return materialQty(areas[c.follows], c.coats, c.coverage);
  if (c.follows === "task" && task) return perTaskQty(taskUnits(task, areas), c.per_amount, c.per_every, c.category);
  return n(c.quantity);
}

// "120 LF", "3,400 SF × 2 coats": the amount of work, for crews and the job page.
export function amountText(t) {
  if (!t?.unit || t.unit === "hr" || t.quantity == null) return "";
  const coats = t.unit === "sf_coat" && t.coats > 1 ? ` × ${fmt(t.coats, 1)} coats` : "";
  return t.unit === "ls" ? "" : `${fmt(t.quantity)} ${UNIT_SHORT[t.unit]}${coats}`;
}
