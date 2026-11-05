// The library: the task list (the GM keeps it), subcontractors, and the
// company's default rates and markups for new estimates.
import { useEffect, useState } from "react";
import { api } from "./api";
import NumInput from "./NumInput";
import { ActivityList, LinkList, LinksField, NoteAction, StatusChip, money0, useApi, useScreen } from "./bits";
import { TASK_TYPES, TASK_TYPE_LABEL, reloadLibrary } from "./library";
import { searchEntries } from "./search";
import { PER_HOUR, UNITS, UNIT_SHORT, rateLabel, rateText } from "./qty";

const SCREEN_KEY = "cf.library.screen";
const money2 = (n) => (n == null || n === "" ? "" : Number(n).toLocaleString("en-US", { style: "currency", currency: "USD" }));
const JOB_STATUS = { scheduled: "Scheduled", active: "In progress", complete: "Complete" };

export default function LibraryView({ me, go, initial }) {
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const tab = screen.view === "sub" || screen.view === "subs" ? "subs" : screen.view === "rates" ? "rates" : "tasks";
  return (
    <div className="sales library">
      <div className="list-head spread">
        <h2 className="detail-title">Library</h2>
      </div>
      <div className="subtabs" role="group" aria-label="Library section">
        <button aria-pressed={tab === "tasks"} onClick={() => setScreen({ view: "tasks" })}>
          Tasks
        </button>
        <button aria-pressed={tab === "subs"} onClick={() => setScreen({ view: "subs" })}>
          Subs
        </button>
        <button aria-pressed={tab === "rates"} onClick={() => setScreen({ view: "rates" })}>
          Rates &amp; markups
        </button>
      </div>
      {screen.view === "sub" ? (
        <SubDetail me={me} id={screen.id} go={go} onBack={() => setScreen({ view: "subs" })} />
      ) : tab === "subs" ? (
        <SubList onOpen={(id) => setScreen({ view: "sub", id })} />
      ) : tab === "rates" ? (
        <Defaults me={me} />
      ) : (
        <TaskList me={me} />
      )}
    </div>
  );
}

// ---------- tasks ----------

const blankTask = () => ({
  name: "", aliases: "", task_type: "other", kind: "crew", cost_rate: "", charge_rate: "", unit: "hr", production_rate: "", unit_price: "", coats: "", notes: "",
  all_in: false, parts: [],
});

const PART_KINDS = [["material", "Material"], ["equipment", "Machine / rental"], ["other", "Other cost"], ["fee", "Permit / fee"]];
const blankPart = () => ({ category: "material", description: "", item_id: null, unit: "", unit_cost: "", how: "task", per_amount: "", per_every: "1", quantity: "", coverage: "", coats: "" });
const partForm = (p) => Object.fromEntries(Object.entries({ ...blankPart(), ...p }).map(([k, v]) => [k, v == null ? (k === "item_id" ? null : "") : typeof v === "number" ? String(v) : v]));
const partBody = (p) => ({
  category: p.category, description: p.description.trim(), item_id: p.item_id || null, unit: (p.unit ?? "").trim(),
  unit_cost: optNum(p.unit_cost), how: p.how, in_house: false,
  per_amount: p.how === "task" ? optNum(p.per_amount) : null, per_every: p.how === "task" ? optNum(p.per_every) || 1 : null,
  quantity: p.how === "fixed" ? optNum(p.quantity) : null,
  coverage: p.how === "area" ? optNum(p.coverage) : null, coats: p.how === "area" ? optNum(p.coats) : null,
});

/* What a task brings onto an estimate when it's picked: its materials,
   machine time and fees. Each amount follows the task ("1 pail for every
   600 SF a coat", "1 load for every 20 ton"), covers the court area, or is a
   set amount. A blank cost uses the price list. */
function PartsEditor({ parts, unit, items, onChange }) {
  const set = (i, k, v) => onChange(parts.map((p, n) => (n === i ? { ...p, [k]: v } : p)));
  const byName = Object.fromEntries(items.map((it) => [it.name.toLowerCase(), it]));
  const taskUnit = unit && unit !== "hr" ? UNIT_SHORT[unit] + (unit === "sf_coat" ? " a coat" : "") : "labor hr";
  return (
    <fieldset className="span-2 measure parts">
      <legend>What it brings onto an estimate</legend>
      <p className="help">
        Materials, machine time and fees that come with this task. Amounts work themselves out from the task's quantity, e.g. 1 pail for every 600 SF a coat, or
        0.75 hr of loader for every 20 ton (whole loads). Leave the cost blank to use the price list. They can all be changed on each estimate.
      </p>
      <datalist id="part-items">
        {items.map((it) => (
          <option key={it.id} value={it.name} />
        ))}
      </datalist>
      {parts.length > 0 && (
        <ol className="part-list">
          {parts.map((p, i) => {
            const item = p.item_id ? items.find((it) => it.id === p.item_id) : null;
            return (
              <li key={i}>
                <div className="part-top">
                  <select value={p.category} onChange={(e) => set(i, "category", e.target.value)} aria-label={`Part ${i + 1}: kind`}>
                    {PART_KINDS.map(([v, l]) => (
                      <option key={v} value={v}>{l}</option>
                    ))}
                  </select>
                  <input
                    list="part-items"
                    value={p.description}
                    placeholder="From the price list, or type it"
                    aria-label={`Part ${i + 1}: what`}
                    onChange={(e) => {
                      const hit = byName[e.target.value.trim().toLowerCase()];
                      onChange(parts.map((x, n) => (n === i ? { ...x, description: e.target.value, item_id: hit?.id ?? null, unit: hit ? hit.unit : x.unit, category: hit ? hit.category : x.category } : x)));
                    }}
                  />
                  <button type="button" className="icon remove" onClick={() => onChange(parts.filter((_, n) => n !== i))} aria-label={`Remove part ${i + 1}`}>✕</button>
                </div>
                <div className="part-grid">
                  <label>
                    Unit
                    <input value={p.unit} onChange={(e) => set(i, "unit", e.target.value)} placeholder="pail, ton, hr…" maxLength={20} />
                  </label>
                  <label>
                    Cost per unit
                    <span className="affix">
                      <span aria-hidden="true">$</span>
                      <NumInput value={p.unit_cost} onChange={(v) => set(i, "unit_cost", v)} placeholder={item?.unit_cost != null ? `${item.unit_cost} (price list)` : "0.00"} />
                    </span>
                  </label>
                  <label>
                    How much
                    <select value={p.how} onChange={(e) => set(i, "how", e.target.value)}>
                      <option value="task">Follows the task's amount</option>
                      <option value="area">Covers the court area</option>
                      <option value="fixed">A set amount</option>
                    </select>
                  </label>
                </div>
                {p.how === "task" && (
                  <div className="le-per">
                    <NumInput decimals={3} value={p.per_amount} onChange={(v) => set(i, "per_amount", v)} placeholder="1" aria-label="How much" />
                    <span>{p.unit || "units"} for every</span>
                    <NumInput decimals={2} value={p.per_every} onChange={(v) => set(i, "per_every", v)} placeholder="1" aria-label="For every" />
                    <span>{taskUnit} of the task</span>
                  </div>
                )}
                {p.how === "area" && (
                  <div className="le-per">
                    <span>One {p.unit || "unit"} covers</span>
                    <NumInput decimals={1} value={p.coverage} onChange={(v) => set(i, "coverage", v)} placeholder={item?.coverage_sf ? String(item.coverage_sf) : "SF"} aria-label="SF per coat" />
                    <span>SF a coat,</span>
                    <NumInput decimals={1} value={p.coats} onChange={(v) => set(i, "coats", v)} placeholder="2" aria-label="Coats" />
                    <span>coats</span>
                  </div>
                )}
                {p.how === "fixed" && (
                  <div className="le-per">
                    <NumInput decimals={2} value={p.quantity} onChange={(v) => set(i, "quantity", v)} placeholder="1" aria-label="How many" />
                    <span>{p.unit || "units"} on every estimate</span>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
      <button type="button" className="btn-ghost" onClick={() => onChange([...parts, blankPart()])}>
        + Add a material, machine or fee
      </button>
    </fieldset>
  );
}
const optNum = (v) => (v === "" || v == null ? null : Number(v));

function TaskForm({ task, onSaved, onCancel }) {
  const [f, setF] = useState(() =>
    task
      ? {
          ...task, aliases: task.aliases.join("\n"), cost_rate: task.cost_rate ?? "", charge_rate: task.charge_rate ?? "", unit: task.unit ?? "hr",
          production_rate: task.production_rate ?? "", unit_price: task.unit_price ?? "", coats: task.coats ?? "",
          all_in: !!task.all_in, parts: (task.parts ?? []).map(partForm),
        }
      : blankTask()
  );
  const [items, setItems] = useState([]);
  useEffect(() => {
    api("/api/items").then(setItems).catch(() => {});
  }, []);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  async function save(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const body = {
        ...f, cost_rate: optNum(f.cost_rate), charge_rate: optNum(f.charge_rate),
        production_rate: optNum(f.production_rate), unit_price: optNum(f.unit_price), coats: optNum(f.coats),
        parts: f.parts.filter((p) => p.description.trim()).map(partBody),
      };
      delete body.id;
      delete body.active;
      await api(task ? `/api/library/tasks/${task.id}` : "/api/library/tasks", { method: task ? "PUT" : "POST", body });
      await reloadLibrary();
      onSaved();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }
  return (
    <form className="editor lib-form" onSubmit={save}>
      <div className="grid">
        <label className="span-2">
          Official name
          <input value={f.name} onChange={(e) => set("name", e.target.value)} required placeholder="e.g. Pressure wash" />
        </label>
        <label className="span-2">
          Other names for the same work
          <span className="help field-help">One per line. Only names for this exact work: a broom clean isn't a pressure wash.</span>
          <textarea rows={3} value={f.aliases} onChange={(e) => set("aliases", e.target.value)} placeholder={"power wash\nwash court"} />
        </label>
        <label>
          Type of work
          <select value={f.task_type} onChange={(e) => set("task_type", e.target.value)}>
            {TASK_TYPES.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <label>
          Usually done by
          <select value={f.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="crew">Our crew</option>
            <option value="sub">A sub</option>
          </select>
        </label>
        <label>
          Cost / hr <span className="optional">(blank = default)</span>
          <span className="affix">
            <span aria-hidden="true">$</span>
            <NumInput value={f.cost_rate} onChange={(v) => set("cost_rate", v)} placeholder="default" />
          </span>
        </label>
        <label>
          Charge / hr <span className="optional">(blank = default)</span>
          <span className="affix">
            <span aria-hidden="true">$</span>
            <NumInput value={f.charge_rate} onChange={(v) => set("charge_rate", v)} placeholder="default" />
          </span>
        </label>
        <fieldset className="span-2 measure">
          <legend>How it's measured</legend>
          <p className="help">
            Pick a unit and the estimate works out the crew hours from the quantity. The production rate is what one person does in an hour, so 2 guys for 2 hours on 160 LF of
            cracks is 40 LF per hr. For things counted one at a time, it's the hours each one takes.
          </p>
          <div className="grid">
            <label>
              Measured in
              <select value={f.unit} onChange={(e) => setF((x) => ({ ...x, unit: e.target.value, production_rate: "", unit_price: "", coats: e.target.value === "sf_coat" ? x.coats || "2" : "" }))}>
                {UNITS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            {f.unit === "sf_coat" && (
              <label>
                Usual coats
                <NumInput decimals={1} value={f.coats} onChange={(v) => set("coats", v)} placeholder="2" />
              </label>
            )}
            {f.unit !== "hr" && (
              <>
                <label>
                  Production rate <span className="optional">({rateLabel(f.unit)})</span>
                  <NumInput decimals={3} value={f.production_rate} onChange={(v) => set("production_rate", v)} placeholder={PER_HOUR.has(f.unit) ? "per person" : "hours"} />
                </label>
                <label>
                  Price per {UNIT_SHORT[f.unit]} <span className="optional">(blank = charge / hr)</span>
                  <span className="affix">
                    <span aria-hidden="true">$</span>
                    <NumInput decimals={3} value={f.unit_price} onChange={(v) => set("unit_price", v)} placeholder="0.00" />
                  </span>
                </label>
              </>
            )}
          </div>
        </fieldset>
        {f.kind === "crew" && (
          <fieldset className="span-2 measure">
            <legend>How it's priced on an estimate</legend>
            <div className="seg">
              <button type="button" aria-pressed={!f.all_in} onClick={() => set("all_in", false)}>Built up</button>
              <button type="button" aria-pressed={f.all_in} onClick={() => set("all_in", true)}>By the unit, all in</button>
            </div>
            <p className="help">
              {f.all_in
                ? "One price per unit covers everything (e.g. clearing by the acre). Its materials and machine time are our cost inside that price."
                : "The labor at its rate, plus each material and machine part with its own markup."}
            </p>
          </fieldset>
        )}
        {f.kind === "crew" && <PartsEditor parts={f.parts} unit={f.unit} items={items} onChange={(v) => set("parts", v)} />}
        <label className="span-2">
          Notes <span className="optional">(what's included, equipment it needs…)</span>
          <textarea rows={2} value={f.notes} onChange={(e) => set("notes", e.target.value)} />
        </label>
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn" disabled={busy}>
          {busy ? "Saving…" : task ? "Save task" : "Add task"}
        </button>
      </div>
    </form>
  );
}

function TaskList({ me }) {
  const { data, error, reload } = useApi("/api/library");
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [editing, setEditing] = useState(null); // task id, "new", or null
  const [showOff, setShowOff] = useState(false);
  const [msg, setMsg] = useState(null);
  const isGM = me.role === "gm";
  if (error && !data) return <p className="empty">Couldn't load the library: {error}</p>;
  if (!data) return <p className="empty">Loading the task library…</p>;
  const d = data.defaults;
  const all = data.tasks.filter((t) => (showOff ? true : t.active) && (!type || t.task_type === type));
  const shown = q.trim() ? searchEntries(q, all, 200).map((r) => ({ ...r.entry, via: r.via })) : all;
  const done = () => {
    setEditing(null);
    reload();
  };
  async function loadParts() {
    setMsg(null);
    try {
      const r = await api("/api/library/tasks/starter-parts", { method: "POST" });
      await reloadLibrary();
      setMsg(r.filled ? `Gave ${r.filled} tasks their usual parts.` : "No starter tasks without parts.");
      reload();
    } catch (e) {
      setMsg(e.message);
    }
  }
  async function loadStarter() {
    setMsg(null);
    try {
      const r = await api("/api/library/tasks/starter", { method: "POST" });
      await reloadLibrary();
      setMsg(r.added ? `Added ${r.added} starter tasks.` : "Every starter task is already in the library.");
      reload();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <>
      <p className="help">
        One official name per kind of work, plus the other names people use for it. Search finds a task by any of its names, words in any order.{" "}
        {isGM ? "Only you (the GM) can change this list." : "Only the GM can change this list."}
      </p>
      <div className="filter-row">
        <input className="search" type="search" placeholder="Search: clean, grading, lines…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search tasks" />
        <select className="search" value={type} onChange={(e) => setType(e.target.value)} aria-label="Type of work">
          <option value="">All types</option>
          {TASK_TYPES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        {isGM && (
          <button className="btn" onClick={() => setEditing("new")}>
            Add task
          </button>
        )}
      </div>
      {isGM && data.tasks.length < 10 && (
        <div className="follow-note">
          <p>
            <b>Start with the starter list?</b> About 55 common court, site, paving, fence, lighting and turf tasks with the names people use for them. Rates start at your defaults.
          </p>
          <button className="btn" onClick={loadStarter}>
            Load the starter list
          </button>
        </div>
      )}
      {isGM && data.tasks.length >= 10 && !data.tasks.some((t) => t.parts?.length) && (
        <div className="follow-note">
          <p>
            <b>Give the starter tasks their usual materials?</b> Resurfacer brings resurfacer and sand, color coat brings color, base rock brings rock and truck loads,
            and so on, with ballpark amounts to check. Only tasks with nothing set yet get them.
          </p>
          <button className="btn" onClick={loadParts}>Add the starter parts</button>
        </div>
      )}
      {msg && <p className="help">{msg}</p>}
      {editing === "new" && (
        <section className="panel">
          <h3>New task</h3>
          <TaskForm onSaved={done} onCancel={() => setEditing(null)} />
        </section>
      )}
      <p className="help">
        Default rates: {money2(d.default_cost_rate)}/hr cost, {money2(d.default_charge_rate)}/hr charge.
      </p>
      {!shown.length ? (
        <p className="empty">{data.tasks.length ? "No task matches that." : "No tasks yet."}</p>
      ) : (
        <ul className="row-list boxed lib-list">
          {shown.map((t) => (
            <li key={t.id}>
              {editing === t.id ? (
                <div className="lib-edit">
                  <TaskForm task={t} onSaved={done} onCancel={() => setEditing(null)} />
                  <NoteAction
                    label={t.active ? "Turn this task off" : "Turn it back on"}
                    tone={t.active ? "danger" : undefined}
                    prompt={t.active ? "Why? It drops out of searches; old estimates and jobs keep it." : "Why turn it back on?"}
                    required={false}
                    onSubmit={(n) =>
                      api(`/api/library/tasks/${t.id}/active`, { method: "PATCH", body: { active: !t.active, reason: n } }).then(async () => {
                        await reloadLibrary();
                        done();
                      })
                    }
                  />
                </div>
              ) : (
                <button className="row-btn" onClick={() => isGM && setEditing(t.id)} disabled={!isGM} aria-label={isGM ? `Edit ${t.name}` : t.name}>
                  <span className="row-main">
                    <b>{t.name}</b>
                    {!t.active && <span className="chip">Off</span>}
                    <span className="sub">
                      {TASK_TYPE_LABEL[t.task_type]}
                      {t.kind === "sub" && " · usually a sub"}
                      {t.kind === "crew" && t.all_in && " · priced all in"}
                      {t.via && ` · matched “${t.via}”`}
                    </span>
                    {t.aliases.length > 0 && <span className="sub alias-line">Also: {t.aliases.join(", ")}</span>}
                    {t.parts?.length > 0 && (
                      <span className="sub alias-line">Brings: {t.parts.map((x) => x.description).join(", ")}</span>
                    )}
                  </span>
                  <span className="row-side">
                    {t.kind === "crew" ? (
                      <>
                        <span>{t.cost_rate != null ? money2(t.cost_rate) : <i className="sub-inline">default</i>} cost</span>
                        {t.unit && t.unit !== "hr" ? (
                          <span className="sub">
                            {t.unit_price != null ? `${money2(t.unit_price)}/${UNIT_SHORT[t.unit]}` : `by ${UNIT_SHORT[t.unit]}`}
                            {t.production_rate != null ? ` · ${rateText(t.unit, t.production_rate)}` : " · no rate yet"}
                          </span>
                        ) : (
                          <span className="sub">{t.charge_rate != null ? money2(t.charge_rate) : "default"} charge</span>
                        )}
                      </>
                    ) : (
                      <span className="sub">priced by the sub</span>
                    )}
                  </span>
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {isGM && (
        <label className="check">
          <input type="checkbox" checked={showOff} onChange={(e) => setShowOff(e.target.checked)} /> Show turned-off tasks
        </label>
      )}
    </>
  );
}

// ---------- subs ----------

const blankSub = () => ({ name: "", trade: "", contact_name: "", phone: "", email: "", notes: "", links: "" });

function SubForm({ sub, onSaved, onCancel }) {
  const [f, setF] = useState(() => (sub ? Object.fromEntries(Object.keys(blankSub()).map((k) => [k, sub[k] ?? ""])) : blankSub()));
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api(sub ? `/api/library/subs/${sub.id}` : "/api/library/subs", { method: sub ? "PUT" : "POST", body: f });
      await reloadLibrary();
      onSaved(s);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }
  return (
    <form className="editor lib-form" onSubmit={save}>
      <div className="grid">
        <label className="span-2">
          Company name
          <input value={f.name} onChange={(e) => set("name", e.target.value)} required />
        </label>
        <label>
          Trade
          <input value={f.trade} onChange={(e) => set("trade", e.target.value)} placeholder="Fence, lighting, paving…" />
        </label>
        <label>
          Contact person
          <input value={f.contact_name} onChange={(e) => set("contact_name", e.target.value)} />
        </label>
        <label>
          Phone
          <input type="tel" value={f.phone} onChange={(e) => set("phone", e.target.value)} />
        </label>
        <label>
          Email
          <input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} autoCapitalize="none" />
        </label>
        <label className="span-2">
          Notes
          <textarea rows={2} value={f.notes} onChange={(e) => set("notes", e.target.value)} />
        </label>
        <div className="span-2">
          <LinksField id="sub-links" value={f.links} onChange={(v) => set("links", v)} />
        </div>
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn" disabled={busy}>
          {busy ? "Saving…" : sub ? "Save sub" : "Add sub"}
        </button>
      </div>
    </form>
  );
}

function SubList({ onOpen }) {
  const { data, error, reload } = useApi("/api/library");
  const [adding, setAdding] = useState(false);
  const [q, setQ] = useState("");
  if (error && !data) return <p className="empty">Couldn't load subs: {error}</p>;
  if (!data) return <p className="empty">Loading subs…</p>;
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const shown = data.subs.filter((s) => words.every((w) => `${s.name} ${s.trade} ${s.contact_name}`.toLowerCase().includes(w)));
  return (
    <>
      <div className="filter-row">
        <input className="search" type="search" placeholder="Search name, trade, contact…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search subs" />
        <button className="btn" onClick={() => setAdding(true)}>
          Add sub
        </button>
      </div>
      {adding && (
        <section className="panel">
          <h3>New sub</h3>
          <SubForm
            onSaved={(s) => {
              setAdding(false);
              reload();
              onOpen(s.id);
            }}
            onCancel={() => setAdding(false)}
          />
        </section>
      )}
      {!shown.length ? (
        <p className="empty">{data.subs.length ? "No sub matches that." : "No subs yet. Add one here or right from a task on an estimate."}</p>
      ) : (
        <ul className="row-list boxed">
          {shown.map((s) => (
            <li key={s.id}>
              <button className="row-btn" onClick={() => onOpen(s.id)}>
                <span className="row-main">
                  <b>{s.name}</b>
                  {!s.active && <span className="chip">Off</span>}
                  <span className="sub">{[s.trade, s.contact_name, s.phone].filter(Boolean).join(" · ") || "No details yet"}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function SubDetail({ me, id, go, onBack }) {
  const { data: s, error, reload } = useApi(`/api/library/subs/${id}`);
  const [editing, setEditing] = useState(false);
  if (error && !s) return <p className="empty">Couldn't load the sub: {error}</p>;
  if (!s) return <p className="empty">Loading…</p>;
  return (
    <div className="detail">
      <button className="link back" onClick={onBack}>
        All subs
      </button>
      <div className="detail-head">
        <div>
          <p className="eyebrow">Subcontractor{!s.active && " · turned off"}</p>
          <h2 className="detail-title">{s.name}</h2>
          {s.trade && <p className="detail-sub">{s.trade}</p>}
        </div>
        <div className="detail-actions">
          <button className="btn-ghost" onClick={() => setEditing(true)}>
            Edit sub
          </button>
          {me.role === "gm" && (
            <NoteAction
              label={s.active ? "Turn off" : "Turn back on"}
              tone={s.active ? "danger" : undefined}
              prompt={s.active ? "Why? They stay on record and on old estimates." : "Why turn them back on?"}
              onSubmit={(n) => api(`/api/library/subs/${id}/active`, { method: "PATCH", body: { active: !s.active, reason: n } }).then(() => reloadLibrary()).then(reload)}
            />
          )}
        </div>
      </div>
      {editing ? (
        <section className="panel">
          <SubForm
            sub={s}
            onSaved={() => {
              setEditing(false);
              reload();
            }}
            onCancel={() => setEditing(false)}
          />
        </section>
      ) : (
        <section className="panel">
          <h3>Contact</h3>
          <dl className="facts">
            <div>
              <dt>Contact</dt>
              <dd>{s.contact_name || "—"}</dd>
            </div>
            <div>
              <dt>Phone</dt>
              <dd>{s.phone ? <a href={`tel:${s.phone}`}>{s.phone}</a> : "—"}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{s.email ? <a href={`mailto:${s.email}`}>{s.email}</a> : "—"}</dd>
            </div>
          </dl>
          {s.notes && <p className="pre">{s.notes}</p>}
          <h4>Documents</h4>
          <LinkList text={s.links} empty="No links yet. Insurance certs get their own place in a later batch." />
        </section>
      )}
      <section className="panel">
        <h3>On estimates</h3>
        {!s.estimates.length ? (
          <p className="help">Not on any estimate yet.</p>
        ) : (
          <ul className="row-list">
            {s.estimates.map((e, i) => (
              <li key={i}>
                <button className="row-btn" onClick={() => go("estimates", { view: "detail", id: e.id })}>
                  <span className="row-main">
                    <b>{e.name}</b>
                    <span className="sub">
                      {e.number} · {e.task}
                      {e.quote_link && " · quote linked"}
                    </span>
                  </span>
                  <span className="row-side">
                    <StatusChip status={e.status} />
                    <span className="sub">{money0(e.price ?? 0)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      {s.jobs.length > 0 && (
        <section className="panel">
          <h3>On jobs</h3>
          <ul className="row-list">
            {s.jobs.map((j, i) => (
              <li key={i}>
                <button className="row-btn" onClick={() => go("office", { view: "job", id: j.id })}>
                  <span className="row-main">
                    <b>{j.name}</b>
                    <span className="sub">{j.task}</span>
                  </span>
                  <span className="row-side">
                    <span className="chip">{JOB_STATUS[j.status]}</span>
                    <span className="sub">{money0(j.price ?? 0)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <ActivityList items={s.activity} />
    </div>
  );
}

// ---------- defaults ----------

const DEFAULT_FIELDS = [
  ["default_cost_rate", "Default cost / hr", "$", "What an hour of crew time costs, for tasks without their own rate"],
  ["default_charge_rate", "Default charge / hr", "$", "What we bill an hour of crew time, for tasks without their own rate"],
  ["markup_material", "Materials markup", "%", "Added over material cost (with its sales tax)"],
  ["markup_equipment", "Equipment markup", "%", "Rentals and in-house equipment"],
  ["markup_subcontractor", "Sub markup", "%", "Added over each sub's price"],
  ["markup_other", "Other costs markup", "%", "Permits, freight, disposal…"],
];

function Defaults({ me }) {
  const [f, setF] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const isGM = me.role === "gm";
  useEffect(() => {
    api("/api/library")
      .then((l) => setF(Object.fromEntries(Object.entries(l.defaults).map(([k, v]) => [k, String(v)]))))
      .catch((e) => setError(e.message));
  }, []);
  if (!f) return <p className="empty">{error ?? "Loading…"}</p>;
  async function save(e) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/library/defaults", { method: "PUT", body: Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v) || 0])) });
      await reloadLibrary();
      setSaved(true);
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form className="editor" onSubmit={save}>
      <section className="panel">
        <h3>Defaults for new estimates</h3>
        <p className="help">
          New estimates start with these. Each estimate can change its own markups, and each task its own rates. {!isGM && "Only the GM can change the defaults."}
        </p>
        <div className="grid">
          {DEFAULT_FIELDS.map(([k, label, unit, help]) => (
            <label key={k}>
              {label}
              <span className="help field-help">{help}</span>
              <span className="affix">
                {unit === "$" && <span aria-hidden="true">$</span>}
                <NumInput
                  value={f[k]}
                  onChange={(v) => {
                    setSaved(false);
                    setF((x) => ({ ...x, [k]: v }));
                  }}
                  disabled={!isGM}
                />
                {unit === "%" && <span aria-hidden="true">%</span>}
              </span>
            </label>
          ))}
        </div>
      </section>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {isGM && (
        <div className="editor-actions">
          {saved && <span className="loc-msg">Saved.</span>}
          <button className="btn">Save defaults</button>
        </div>
      )}
    </form>
  );
}
