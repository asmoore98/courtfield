// The task library, subs and default rates, loaded once and shared by every
// form on the page. `reload()` after adding a task or a sub.
import { useEffect, useState } from "react";
import { DEMO, api } from "./api";
import { defaultFollows } from "./qty";

let cache = null; // { tasks, subs, defaults }
let pending = null;
const listeners = new Set();

function load() {
  if (DEMO) return Promise.resolve(null);
  pending ??= api("/api/library")
    .then((lib) => {
      cache = lib;
      listeners.forEach((fn) => fn(lib));
      return lib;
    })
    .catch(() => null) // no access (e.g. sales) or offline: forms fall back to typed names
    .finally(() => {
      pending = null;
    });
  return pending;
}

export function reloadLibrary() {
  return load();
}

export function useLibrary() {
  const [lib, setLib] = useState(cache);
  useEffect(() => {
    listeners.add(setLib);
    if (!cache) load();
    return () => listeners.delete(setLib);
  }, []);
  return lib;
}

export const TASK_TYPE_LABEL = {
  prep: "Prep",
  crack_fill: "Crack fill",
  resurfacer: "Resurfacer",
  color_coat: "Color coat",
  lines: "Lines",
  fence: "Fence",
  nets_posts: "Nets & posts",
  lighting: "Lighting",
  site_work: "Site work",
  paving: "Paving & concrete",
  turf: "Turf",
  drainage: "Drainage",
  cleanup: "Cleanup",
  building: "Buildings",
  other: "Other",
};
export const TASK_TYPES = Object.entries(TASK_TYPE_LABEL);

// Fill a task from a library entry. Blank library rates use the company
// defaults. Area work follows the court size until someone types a quantity.
export function fromTemplate(t, defaults) {
  const unit = t.unit || "hr";
  return {
    name: t.name,
    task_type: t.task_type,
    kind: t.kind,
    template_id: t.id,
    cost_rate: t.cost_rate ?? defaults?.default_cost_rate ?? "",
    charge_rate: t.charge_rate ?? defaults?.default_charge_rate ?? "",
    unit,
    production_rate: t.production_rate ?? "",
    unit_price: t.unit_price ?? "",
    coats: unit === "sf_coat" ? t.coats ?? 2 : "",
    follows: defaultFollows(unit, t.task_type),
    all_in: !!t.all_in,
  };
}

// The lines a library task brings onto an estimate: its materials, machine
// time and fees. A blank cost takes the price list's price.
export function linesFromParts(t, taskKey, items = []) {
  const byId = Object.fromEntries(items.map((i) => [i.id, i]));
  return (t.parts ?? []).map((p) => {
    const item = p.item_id ? byId[p.item_id] : null;
    return {
      key: crypto.randomUUID?.() ?? String(Math.random()),
      category: p.category,
      description: p.description,
      item_id: item ? p.item_id : null,
      unit: p.unit || item?.unit || "",
      unit_cost: p.unit_cost != null ? String(p.unit_cost) : item?.unit_cost != null ? String(item.unit_cost) : "",
      in_house: !!p.in_house,
      task_key: taskKey,
      quantity: p.how === "fixed" && p.quantity != null ? String(p.quantity) : "",
      follows: p.how === "task" ? "task" : p.how === "area" ? "paint" : "",
      per_amount: p.per_amount != null ? String(p.per_amount) : "",
      per_every: p.per_every != null ? String(p.per_every) : "1",
      coverage: p.coverage != null ? String(p.coverage) : item?.coverage_sf != null ? String(item.coverage_sf) : "",
      coats: p.coats != null ? String(p.coats) : "",
      markup_pct: "",
      from_template: t.id,
    };
  });
}
