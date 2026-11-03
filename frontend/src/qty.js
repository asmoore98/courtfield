// How a task is measured, and the numbers that follow. Mirrors
// backend/app/quantities.py and the court size in sales_schemas.py.
//
// With a production rate, crew hours are worked out from the quantity:
//   SF, SF per coat, LF, SY  → rate is units one person does in an hour
//   each, CY, ton, lump sum  → rate is person-hours for one unit
// Crew work is charged at its price per unit, or hours × charge rate when
// it has none.

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

// The court size, entered once: surface SF, paintable SF and number of courts.
export function courtAreas(court) {
  if (!court) return null;
  const courts = n(court.courts);
  const auto = n(court.length_ft) > 0 && n(court.width_ft) > 0 ? Math.round(n(court.length_ft) * n(court.width_ft) * (courts || 1) * 100) / 100 : null;
  const surface = !blank(court.surface_sf) ? n(court.surface_sf) : auto;
  const paint = !blank(court.paint_sf) ? n(court.paint_sf) : surface;
  return { surface, paint, courts: courts || null, auto };
}

// Which court figure a task follows by default, from how it's measured.
export const defaultFollows = (unit, taskType) =>
  unit === "sf" ? "surface" : unit === "sf_coat" ? "paint" : unit === "ea" && taskType === "lines" ? "courts" : "";
export const FOLLOWS_LABEL = { surface: "court surface", paint: "paintable area", courts: "number of courts" };

// The quantity a task is using: the court figure it follows, or what was typed.
export function quantityOf(t, areas) {
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

// The quantity a cost line is using.
export function lineQty(c, areas) {
  if ((c.follows === "surface" || c.follows === "paint") && n(c.coverage) > 0 && areas?.[c.follows] != null)
    return materialQty(areas[c.follows], c.coats, c.coverage);
  return n(c.quantity);
}

// "120 LF", "3,400 SF × 2 coats": the amount of work, for crews and the job page.
export function amountText(t) {
  if (!t?.unit || t.unit === "hr" || t.quantity == null) return "";
  const coats = t.unit === "sf_coat" && t.coats > 1 ? ` × ${fmt(t.coats, 1)} coats` : "";
  return t.unit === "ls" ? "" : `${fmt(t.quantity)} ${UNIT_SHORT[t.unit]}${coats}`;
}
