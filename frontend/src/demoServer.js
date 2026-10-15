// Demo mode: an in-browser stand-in for the FastAPI backend, so the app can be
// clicked through with no server (e.g. as a shared preview). It mirrors the
// real API's routes, roles and rules closely enough to try every screen.
// Built only when VITE_DEMO=1. Data is fictional and lives in this browser.

const STORE_KEY = "cf.demo.db";
const HOUR = 3600e3;
const OFF_SITE_METERS = 400;

const uid = () => crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const iso = (ms) => new Date(ms).toISOString();

// ---------- sample data ----------

function seed() {
  let r = 7;
  const rand = () => ((r = (r * 16807) % 2147483647) / 2147483647);
  const now = Date.now();
  const company = { id: "co-sample", name: "Sample Court Builders" };
  const users = [
    { id: "u-gm", name: "Sam Ortiz", role: "gm", hourly_cost: 0, token: "dev-gm" },
    { id: "u-owner", name: "Pat Lin", role: "owner", hourly_cost: 0, token: "dev-owner" },
    { id: "u-est", name: "Riley Shaw", role: "estimator", hourly_cost: 0, token: "dev-estimator" },
    { id: "u-lead1", name: "Marco Diaz", role: "crew_lead", hourly_cost: 38, token: "dev-lead-1" },
    { id: "u-lead2", name: "Jordan Kemp", role: "crew_lead", hourly_cost: 36, token: "dev-lead-2" },
    { id: "u-c1", name: "Luis Vega", role: "crew", hourly_cost: 27 },
    { id: "u-c2", name: "Tyler Brooks", role: "crew", hourly_cost: 25 },
    { id: "u-c3", name: "Andre Wells", role: "crew", hourly_cost: 26 },
    { id: "u-c4", name: "Kenny Ruiz", role: "crew", hourly_cost: 24 },
  ];
  const J = (name, client, court_type, scope_type, status, contract_amount, rate, lat, lng, tasks, made) => ({
    id: uid(), name, client, address: "Sample address", lat, lng, court_type, scope_type, status,
    contract_amount, estimated_labor_rate: rate, created_at: made,
    tasks: tasks.map(([task_type, n, h], i) => ({ id: uid(), task_type, name: n, estimated_hours: h, sort_order: i })),
  });
  const jobs = [
    J("Palm Hollow HOA – 4 Pickleball Resurface", "Palm Hollow HOA", "pickleball", "resurfacing", "complete", 28500, 32, 26.531, -80.091,
      [["prep", "Pressure wash & prep", 16], ["crack_fill", "Crack repair", 12], ["resurfacer", "Acrylic resurfacer (2 coats)", 24],
       ["color_coat", "Color coats (2)", 24], ["lines", "Line striping", 10], ["nets_posts", "Nets & posts", 4]], now - 40 * 864e5),
    J("Westgate Park – Tennis Court Repair", "City of Westgate (sample)", "tennis", "repair", "complete", 9800, 32, 26.552, -80.12,
      [["prep", "Clean & prep", 6], ["crack_fill", "Crack fill + birdbath patch", 14], ["color_coat", "Spot color & blend", 8], ["lines", "Re-stripe", 6]], now - 30 * 864e5),
    J("Coral Ridge Academy – 2 Tennis New Build", "Coral Ridge Academy (sample)", "tennis", "new_construction", "active", 142000, 33, 26.512, -80.074,
      [["prep", "Base check & flood test", 10], ["resurfacer", "Resurfacer (2 coats)", 30], ["color_coat", "Color coats (2)", 28],
       ["lines", "Lines", 12], ["fence", "10' chain-link fence", 60], ["nets_posts", "Posts & nets", 6]], now - 10 * 864e5),
    J("Seabreeze Club – Basketball Resurface", "Seabreeze Club (sample)", "basketball", "resurfacing", "scheduled", 11200, 32, 26.578, -80.065,
      [["prep", "Pressure wash & prep", 6], ["crack_fill", "Crack repair", 6], ["resurfacer", "Resurfacer (1 coat)", 8],
       ["color_coat", "Color coats (2)", 10], ["lines", "Lines", 5]], now - 5 * 864e5),
  ];
  const teamA = ["u-lead1", "u-c1", "u-c2"];
  const teamB = ["u-lead2", "u-c3", "u-c4"];
  const time = [];
  const day7am = (daysAgo) => { const d = new Date(now - daysAgo * 864e5); d.setHours(7, 0, 0, 0); return d.getTime(); };

  function spread(job, plan, team, lead, startDay) {
    let day = startDay, used = Object.fromEntries(team.map((w) => [w, 0]));
    for (const [task, hours] of plan) {
      let left = hours;
      while (left > 0.1) {
        for (const w of team) {
          if (left <= 0.1) break;
          if (used[w] >= 8) continue;
          const chunk = Math.min(left, 8 - used[w], [2, 3, 4, 4, 5][Math.floor(rand() * 5)]);
          const start = day7am(day) + used[w] * HOUR;
          time.push({
            id: uid(), job_id: job.id, task_id: task.id, worker_id: w, entered_by_id: lead,
            clock_in: iso(start), clock_out: iso(start + chunk * HOUR),
            in_lat: job.lat + (rand() - 0.5) * 0.0008, in_lng: job.lng + (rand() - 0.5) * 0.0008,
            out_lat: job.lat, out_lng: job.lng, note: "", client_updated_at: iso(start + chunk * HOUR),
          });
          used[w] += chunk;
          left -= chunk;
        }
        if (team.every((w) => used[w] >= 8)) { day -= 1; used = Object.fromEntries(team.map((w) => [w, 0])); }
      }
    }
  }
  const [palm, west, coral] = jobs;
  spread(palm, palm.tasks.map((t) => [t, t.estimated_hours * 1.18 * (0.85 + rand() * 0.3)]), teamA, "u-lead1", 30);
  spread(west, west.tasks.map((t) => [t, t.estimated_hours * 0.94 * (0.85 + rand() * 0.3)]), teamB, "u-lead2", 18);
  spread(coral, [[coral.tasks[0], 13.5], [coral.tasks[1], 18]], teamA, "u-lead1", 4);
  for (const w of teamA) {
    const start = now - 2.25 * HOUR;
    time.push({ id: uid(), job_id: coral.id, task_id: coral.tasks[1].id, worker_id: w, entered_by_id: "u-lead1",
      clock_in: iso(start), clock_out: null, in_lat: coral.lat, in_lng: coral.lng, out_lat: null, out_lng: null,
      note: "", client_updated_at: iso(start) });
  }
  return { company, users, jobs, time, changes: [] };
}

let db;
function load() {
  if (db) return db;
  try { db = JSON.parse(localStorage.getItem(STORE_KEY)); } catch {}
  if (!db) { db = seed(); save(); }
  db.changes ??= [];
  return db;
}
function save() { try { localStorage.setItem(STORE_KEY, JSON.stringify(db)); } catch {} }
export function resetDemo() {
  db = seed();
  save();
  try {
    for (const k of ["cf.entries", "cf.pending", "cf.jobs", "cf.crew", "cf.job"]) localStorage.removeItem(k);
  } catch {}
}

// ---------- rules (mirror backend/app) ----------

const SEES_DOLLARS = ["owner", "gm", "estimator"];
const ENTERS_TIME = ["gm", "crew_lead"];
const EDITS_JOBS = ["gm", "estimator"];
const FIELD = ["crew", "crew_lead"];

class HttpError extends Error { constructor(status, detail) { super(detail); this.status = status; } }
const need = (cond, status, detail) => { if (!cond) throw new HttpError(status, detail); };

const hours = (e, now = Date.now()) => Math.max(0, ((e.clock_out ? Date.parse(e.clock_out) : now) - Date.parse(e.clock_in)) / HOUR);
const r2 = (n) => Math.round(n * 100) / 100;
function dist(a, b, c, d) {
  const R = 6371000, p1 = (a * Math.PI) / 180, p2 = (c * Math.PI) / 180, dp = p2 - p1, dl = ((d - b) * Math.PI) / 180;
  const x = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}
const offSite = (e, j) =>
  j.lat != null && j.lng != null &&
  [[e.in_lat, e.in_lng], [e.out_lat, e.out_lng]].some(([a, b]) => a != null && b != null && dist(a, b, j.lat, j.lng) > OFF_SITE_METERS);
const tone = (u) => (u == null ? "no_estimate" : u > 1 ? "over" : u >= 0.9 ? "near" : "under");

function jobOut(j, user) {
  const { created_at, ...rest } = j;
  const out = { ...rest, tasks: [...j.tasks].sort((a, b) => a.sort_order - b.sort_order) };
  if (!SEES_DOLLARS.includes(user.role)) { delete out.contract_amount; delete out.estimated_labor_rate; }
  return out;
}

function costing(j, withDollars) {
  const entries = db.time.filter((e) => e.job_id === j.id && !e.voided_at);
  const closed = {}, open = {}, cost = {}, onSite = new Set();
  for (const e of entries) {
    const h = hours(e);
    const w = db.users.find((u) => u.id === e.worker_id);
    (e.clock_out ? closed : open)[e.task_id] = ((e.clock_out ? closed : open)[e.task_id] ?? 0) + h;
    if (!e.clock_out) onSite.add(e.worker_id);
    cost[e.task_id] = (cost[e.task_id] ?? 0) + h * (w?.hourly_cost ?? 0);
  }
  const tasks = [...j.tasks].sort((a, b) => a.sort_order - b.sort_order).map((t) => {
    const a = closed[t.id] ?? 0, o = open[t.id] ?? 0;
    const used = t.estimated_hours > 0 ? (a + o) / t.estimated_hours : null;
    const row = { task_id: t.id, name: t.name, task_type: t.task_type, estimated_hours: t.estimated_hours,
      actual_hours: r2(a), open_hours: r2(o), hours_used_pct: used == null ? null : Math.round(used * 1e4) / 1e4, status: tone(used) };
    if (withDollars) { row.estimated_labor_cost = r2(t.estimated_hours * j.estimated_labor_rate); row.actual_labor_cost = r2(cost[t.id] ?? 0); }
    return row;
  });
  const est = j.tasks.reduce((s, t) => s + t.estimated_hours, 0);
  const act = Object.values(closed).reduce((s, v) => s + v, 0);
  const opn = Object.values(open).reduce((s, v) => s + v, 0);
  const out = { job_id: j.id, job_name: j.name, status: j.status, estimated_hours: r2(est), actual_hours: r2(act), open_hours: r2(opn),
    hours_used_pct: est > 0 ? Math.round(((act + opn) / est) * 1e4) / 1e4 : null, crew_on_site: onSite.size, tasks };
  if (withDollars) {
    const ec = r2(est * j.estimated_labor_rate), ac = r2(Object.values(cost).reduce((s, v) => s + v, 0));
    Object.assign(out, { contract_amount: j.contract_amount, estimated_labor_cost: ec, actual_labor_cost: ac,
      labor_cost_used_pct: ec > 0 ? Math.round((ac / ec) * 1e4) / 1e4 : null,
      labor_variance: j.status === "complete" ? r2(ac - ec) : null });
  }
  return out;
}

const tasksWithTime = (j) => new Set(db.time.filter((e) => e.job_id === j.id).map((e) => e.task_id));
const editView = (j, user) => {
  const used = tasksWithTime(j);
  const out = jobOut(j, user);
  out.tasks = out.tasks.map((t) => ({ ...t, has_time: used.has(t.id) }));
  return out;
};
const findJob = (id) => { const j = db.jobs.find((x) => x.id === id); need(j, 404, "Job not found"); return j; };

function validateEntry(e) {
  const job = db.jobs.find((j) => j.id === e.job_id);
  if (!job) return "unknown job";
  if (!job.tasks.some((t) => t.id === e.task_id)) return "task does not belong to this job";
  const w = db.users.find((u) => u.id === e.worker_id);
  if (!w || !FIELD.includes(w.role)) return "unknown crew member";
  const now = Date.now(), cin = Date.parse(e.clock_in), cout = e.clock_out ? Date.parse(e.clock_out) : null;
  if (cin > now + 10 * 60e3) return "clock-in is in the future";
  if (cout != null && cout < cin) return "clock-out is before clock-in";
  if (cout != null && cout > now + 10 * 60e3) return "clock-out is in the future";
  if (cout != null && cout - cin > 16 * HOUR) return "entry is longer than 16 hours";
  if (cout == null && now - cin > 16 * HOUR) return "open entry is older than 16 hours; clock it out with the real time";
  const end = cout ?? Infinity;
  const clash = db.time.find((x) => x.worker_id === e.worker_id && x.id !== e.id && !x.voided_at && Date.parse(x.clock_in) < end &&
    (!x.clock_out || Date.parse(x.clock_out) > cin));
  if (clash) return `overlaps another entry for ${w.name}`;
  return null;
}
const SAME = ["job_id", "task_id", "worker_id", "clock_in", "clock_out", "in_lat", "in_lng", "out_lat", "out_lng", "note"];
const norm = (k, v) => (v == null ? null : ["clock_in", "clock_out"].includes(k) ? Date.parse(v) : v);

function jobFields(body) {
  const pick = ["name", "client", "address", "lat", "lng", "court_type", "scope_type", "contract_amount", "estimated_labor_rate"];
  need(typeof body.name === "string" && body.name.trim(), 422, "Job name is required");
  return Object.fromEntries(pick.map((k) => [k, body[k] ?? (["lat", "lng"].includes(k) ? null : k.endsWith("amount") || k.endsWith("rate") ? 0 : "")]));
}

const findEntry = (id) => { const e = db.time.find((x) => x.id === id); need(e, 404, "Time entry not found"); return e; };
function snap(e) {
  const j = db.jobs.find((x) => x.id === e.job_id);
  return { job_id: e.job_id, task_id: e.task_id, task: j?.tasks.find((t) => t.id === e.task_id)?.name,
    worker_id: e.worker_id, worker: db.users.find((u) => u.id === e.worker_id)?.name, clock_in: e.clock_in, clock_out: e.clock_out };
}
function record(user, e, action, reason, before) {
  db.changes.push({ entry_id: e.id, action, reason: reason.trim(), changed_by: user.name, changed_at: iso(Date.now()),
    before, after: action === "remove" ? null : snap(e) });
}
function listRow(e) {
  const j = db.jobs.find((x) => x.id === e.job_id);
  return { ...e, worker_name: db.users.find((u) => u.id === e.worker_id)?.name ?? "", task_name: j?.tasks.find((t) => t.id === e.task_id)?.name ?? "",
    hours: e.clock_out ? r2(hours(e)) : null, off_site: j ? offSite(e, j) : false,
    edited: db.changes.some((c) => c.entry_id === e.id && c.action !== "add"), removed: !!e.voided_at, removed_reason: e.void_reason ?? "" };
}

// ---------- routes ----------

function route(method, path, query, body, user) {
  let m;
  if (method === "GET" && path === "/api/health") return { ok: true };
  if (method === "GET" && path === "/api/me")
    return { id: user.id, name: user.name, role: user.role, company_id: db.company.id, company_name: db.company.name,
      sees_dollars: SEES_DOLLARS.includes(user.role), enters_time: ENTERS_TIME.includes(user.role), edits_jobs: EDITS_JOBS.includes(user.role) };

  if (method === "GET" && path === "/api/jobs") {
    let jobs = [...db.jobs].sort((a, b) => b.created_at - a.created_at);
    if (query.get("status")) jobs = jobs.filter((j) => j.status === query.get("status"));
    else if (user.role === "crew_lead") jobs = jobs.filter((j) => j.status !== "complete");
    return jobs.map((j) => jobOut(j, user));
  }
  if (method === "POST" && path === "/api/jobs") {
    need(EDITS_JOBS.includes(user.role), 403, "Your role can't do that");
    const j = { id: uid(), ...jobFields(body), status: user.role === "gm" ? body.status ?? "scheduled" : "scheduled", created_at: Date.now(),
      tasks: (body.tasks ?? []).map((t, i) => ({ id: uid(), task_type: t.task_type, name: t.name, estimated_hours: t.estimated_hours ?? 0, sort_order: i })) };
    db.jobs.push(j);
    return jobOut(j, user);
  }
  if (method === "GET" && path === "/api/jobs/summary") {
    need(SEES_DOLLARS.includes(user.role), 403, "Your role can't do that");
    return [...db.jobs].sort((a, b) => b.created_at - a.created_at).map((j) => costing(j, true));
  }
  if ((m = path.match(/^\/api\/jobs\/([^/]+)\/edit$/)) && method === "GET") {
    need(EDITS_JOBS.includes(user.role), 403, "Your role can't do that");
    return editView(findJob(m[1]), user);
  }
  if ((m = path.match(/^\/api\/jobs\/([^/]+)\/costing$/)) && method === "GET") {
    need(!["crew", "warehouse"].includes(user.role), 403, "Your role can't do that");
    return costing(findJob(m[1]), SEES_DOLLARS.includes(user.role));
  }
  if ((m = path.match(/^\/api\/jobs\/([^/]+)\/status$/)) && method === "PATCH") {
    need(user.role === "gm", 403, "Your role can't do that");
    const j = findJob(m[1]);
    j.status = body.status;
    return jobOut(j, user);
  }
  if ((m = path.match(/^\/api\/jobs\/([^/]+)$/))) {
    if (method === "GET") return jobOut(findJob(m[1]), user);
    if (method === "PUT") {
      need(EDITS_JOBS.includes(user.role), 403, "Your role can't do that");
      const j = findJob(m[1]);
      const byId = Object.fromEntries(j.tasks.map((t) => [t.id, t]));
      const sent = (body.tasks ?? []).filter((t) => t.id).map((t) => t.id);
      need(sent.every((id) => byId[id]) && new Set(sent).size === sent.length, 422, "A task in this save doesn't belong to this job");
      const removed = j.tasks.filter((t) => !sent.includes(t.id));
      const used = tasksWithTime(j);
      const blocked = removed.filter((t) => used.has(t.id)).map((t) => t.name).sort();
      need(!blocked.length, 409, `Crew time is logged on ${blocked.join(", ")}, so it can't be removed. Set its hours instead.`);
      Object.assign(j, jobFields(body));
      j.tasks = body.tasks.map((t, i) => ({ id: t.id ?? uid(), task_type: t.task_type, name: t.name, estimated_hours: t.estimated_hours ?? 0, sort_order: i }));
      return editView(j, user);
    }
  }

  if (method === "POST" && path === "/api/time/office") {
    need(user.role === "gm", 403, "Your role can't do that");
    need((body.reason ?? "").trim().length >= 3, 422, "Give a reason for the change");
    const e = { id: uid(), job_id: body.job_id, task_id: body.task_id, worker_id: body.worker_id, clock_in: body.clock_in, clock_out: body.clock_out,
      in_lat: null, in_lng: null, out_lat: null, out_lng: null, note: "", client_updated_at: iso(Date.now()), entered_by_id: user.id, office_edited: true };
    const bad = validateEntry(e);
    need(!bad, 422, `Can't add this time: ${bad}.`);
    db.time.push(e);
    record(user, e, "add", body.reason, null);
    return listRow(e);
  }
  if ((m = path.match(/^\/api\/time\/([^/]+)\/history$/)) && method === "GET") {
    need(SEES_DOLLARS.includes(user.role), 403, "Your role can't do that");
    findEntry(m[1]);
    return db.changes.filter((c) => c.entry_id === m[1]).map(({ entry_id, ...c }) => c);
  }
  if ((m = path.match(/^\/api\/time\/([^/]+)\/remove$/)) && method === "POST") {
    need(user.role === "gm", 403, "Your role can't do that");
    need((body.reason ?? "").trim().length >= 3, 422, "Give a reason for the change");
    const e = findEntry(m[1]);
    need(!e.voided_at, 409, "This entry was already removed");
    const before = snap(e);
    Object.assign(e, { voided_at: iso(Date.now()), void_reason: body.reason.trim(), office_edited: true });
    record(user, e, "remove", body.reason, before);
    return listRow(e);
  }
  if ((m = path.match(/^\/api\/time\/([^/]+)$/)) && method === "PATCH") {
    need(user.role === "gm", 403, "Your role can't do that");
    need((body.reason ?? "").trim().length >= 3, 422, "Give a reason for the change");
    const e = findEntry(m[1]);
    need(!e.voided_at, 409, "This entry was removed. Add new time instead.");
    const keys = ["task_id", "worker_id", "clock_in", "clock_out"].filter((k) => k in body);
    need(keys.length, 422, "Nothing to change");
    const cand = { ...e, ...Object.fromEntries(keys.map((k) => [k, body[k]])) };
    const bad = validateEntry(cand);
    need(!bad, 422, `Can't save this change: ${bad}.`);
    const before = snap(e);
    Object.assign(e, Object.fromEntries(keys.map((k) => [k, body[k]])), { office_edited: true, client_updated_at: iso(Date.now()) });
    record(user, e, "edit", body.reason, before);
    return listRow(e);
  }

  if (method === "GET" && path === "/api/crew")
    return db.users.filter((u) => FIELD.includes(u.role)).map(({ id, name, role }) => ({ id, name, role })).sort((a, b) => a.name.localeCompare(b.name));

  if (method === "POST" && path === "/api/time/sync") {
    need(ENTERS_TIME.includes(user.role), 403, "Your role can't do that");
    const results = [];
    for (const e of [...(body.entries ?? [])].sort((a, b) => Date.parse(a.client_updated_at) - Date.parse(b.client_updated_at))) {
      const ex = db.time.find((x) => x.id === e.id);
      let inc = e;
      if (ex) {
        if (ex.voided_at) { results.push({ id: e.id, status: "rejected", reason: "the office removed this entry" }); continue; }
        if (SAME.every((k) => norm(k, ex[k]) === norm(k, e[k]))) { results.push({ id: e.id, status: "unchanged" }); continue; }
        if (ex.office_edited) {
          if (ex.clock_out || !e.clock_out) { results.push({ id: e.id, status: "stale", reason: "the office corrected this entry" }); continue; }
          inc = { ...e, ...Object.fromEntries(["job_id", "task_id", "worker_id", "clock_in", "in_lat", "in_lng", "note"].map((k) => [k, ex[k]])) };
        } else if (Date.parse(ex.client_updated_at) > Date.parse(e.client_updated_at)) { results.push({ id: e.id, status: "stale", reason: "server has a newer edit" }); continue; }
      }
      const reason = validateEntry(inc);
      if (reason) { results.push({ id: e.id, status: "rejected", reason }); continue; }
      if (ex) Object.assign(ex, inc);
      else db.time.push({ ...inc, entered_by_id: user.id });
      results.push({ id: e.id, status: "saved" });
    }
    return { results };
  }
  if (method === "GET" && path === "/api/time") {
    need(!["crew", "warehouse"].includes(user.role), 403, "Your role can't do that");
    let rows = [...db.time];
    if (query.get("job_id")) rows = rows.filter((e) => e.job_id === query.get("job_id"));
    if (query.get("open_only") === "true") rows = rows.filter((e) => !e.clock_out);
    if (query.get("include_removed") !== "true" || query.get("open_only") === "true") rows = rows.filter((e) => !e.voided_at);
    const edited = new Set(db.changes.filter((c) => c.action !== "add").map((c) => c.entry_id));
    rows.sort((a, b) => Date.parse(b.clock_in) - Date.parse(a.clock_in));
    return rows.slice(0, 1000).map((e) => {
      const j = db.jobs.find((x) => x.id === e.job_id);
      return { ...e, worker_name: db.users.find((u) => u.id === e.worker_id)?.name ?? "",
        task_name: j?.tasks.find((t) => t.id === e.task_id)?.name ?? "",
        hours: e.clock_out ? r2(hours(e)) : null, off_site: j ? offSite(e, j) : false,
        edited: edited.has(e.id), removed: !!e.voided_at, removed_reason: e.void_reason ?? "" };
    });
  }
  throw new HttpError(404, "Not found");
}

export async function demoFetch(path, { method = "GET", body, token }) {
  load();
  await new Promise((r) => setTimeout(r, 120)); // feel like a network
  const url = new URL(path, "http://demo");
  const user = db.users.find((u) => u.token && u.token === token);
  try {
    if (!user) throw new HttpError(401, "That access code isn't recognized.");
    const data = route(method, url.pathname, url.searchParams, body ? JSON.parse(JSON.stringify(body)) : null, user);
    if (method !== "GET") save();
    return { ok: true, status: 200, data: JSON.parse(JSON.stringify(data)) };
  } catch (e) {
    if (e instanceof HttpError) return { ok: false, status: e.status, data: { detail: e.message } };
    throw e;
  }
}
