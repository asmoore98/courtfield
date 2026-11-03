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
  };
}
