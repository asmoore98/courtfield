// The site checklist sales fills in on site, and the court size block that
// starts it. The questions come from backend/app/checklists.py; follow-ups
// only show once the question above is answered a certain way.
import { useEffect, useState } from "react";
import { api } from "./api";
import NumInput from "./NumInput";
import { courtAreas, fmt } from "./qty";
import { sameName } from "./search";

let cache = null;
let pending = null;

export function useChecklists() {
  const [lists, setLists] = useState(cache);
  useEffect(() => {
    if (cache) return;
    pending ??= api("/api/leads/checklists").then((r) => (cache = r)).catch(() => null);
    pending.then((r) => r && setLists(r));
  }, []);
  return lists;
}

export const blankCourt = () => ({ courts: "", length_ft: "", width_ft: "", border_ft: "", surface_sf: "", paint_sf: "" });
export const courtForm = (c) => Object.fromEntries(Object.keys(blankCourt()).map((k) => [k, c?.[k] == null ? "" : String(c[k])]));
const optNum = (v) => (v === "" || v == null ? null : Number(v));
export const courtBody = (c) => ({
  courts: c?.courts === "" || c?.courts == null ? null : Math.round(Number(c.courts)),
  length_ft: optNum(c?.length_ft),
  width_ft: optNum(c?.width_ft),
  border_ft: optNum(c?.border_ft),
  surface_sf: optNum(c?.surface_sf),
  paint_sf: optNum(c?.paint_sf),
});

// Common sizes, as a starting point: [width, length, border, what]. Measure when it matters.
// With an uneven border (more at the ends than the sides), type the surfaced size with no border.
const TYPICAL = {
  tennis: [[60, 120, 0, "tennis, surfaced"]],
  pickleball: [[30, 60, 0, "pickleball, surfaced"]],
  basketball: [
    [50, 94, 5, "full court + 5 ft border"],
    [50, 84, 5, "high school + 5 ft border"],
  ],
};

/* Number of courts x length x width, or a measured total for odd shapes.
   On estimates, the paintable area too: the same as the surface unless
   someone types a different number. */
export function CourtSizeFields({ court, courtType, onChange, paint = false }) {
  const c = court ?? blankCourt();
  const set = (k, v) => onChange({ ...c, [k]: v });
  const a = courtAreas(c);
  return (
    <div className="court-size">
      <div className="court-grid">
        <label>
          Courts
          <NumInput decimals={0} value={c.courts} onChange={(v) => set("courts", v)} placeholder="1" aria-label="Number of courts" />
        </label>
        <label>
          Length of one <span className="optional">(ft)</span>
          <NumInput decimals={1} value={c.length_ft} onChange={(v) => set("length_ft", v)} placeholder="ft" />
        </label>
        <label>
          Width of one <span className="optional">(ft)</span>
          <NumInput decimals={1} value={c.width_ft} onChange={(v) => set("width_ft", v)} placeholder="ft" />
        </label>
        <label>
          Border all around <span className="optional">(ft)</span>
          <NumInput decimals={1} value={c.border_ft ?? ""} onChange={(v) => set("border_ft", v)} placeholder="none" />
        </label>
      </div>
      {a.border != null && (
        <p className="help court-split">
          Playing area {fmt(a.playing, 0)} SF ({fmt(c.width_ft, 1)} × {fmt(c.length_ft, 1)}) + border {fmt(a.border, 0)} SF ={" "}
          {fmt(a.surface, 0)} SF surfaced ({fmt(Number(c.width_ft) + 2 * Number(c.border_ft), 1)} × {fmt(Number(c.length_ft) + 2 * Number(c.border_ft), 1)}
          {Number(c.courts) > 1 ? ` each, × ${c.courts}` : ""}). Lines go on the playing area; the border can be its own color.
        </p>
      )}
      {(TYPICAL[courtType] ?? []).length > 0 && (
        <p className="help typical">
          Common size:{" "}
          {TYPICAL[courtType].map(([w, l, b, what], i) => (
            <span key={what}>
              {i > 0 && " · "}
              <button type="button" className="link" onClick={() => onChange({ ...c, length_ft: String(l), width_ft: String(w), border_ft: b ? String(b) : "" })}>
                {w} × {l} ft ({what})
              </button>
            </span>
          ))}
        </p>
      )}
      <div className="court-grid two">
        <label>
          <span>
            Surface area <span className="optional">(SF)</span>
          </span>
          <NumInput decimals={0} value={c.surface_sf} onChange={(v) => set("surface_sf", v)} placeholder={a.auto != null ? fmt(a.auto, 0) : "measured total"} />
          <span className="help field-help">
            {c.surface_sf !== "" && c.surface_sf != null
              ? a.auto != null && Number(c.surface_sf) !== a.auto
                ? `Typed in. Courts × size would be ${fmt(a.auto, 0)} SF.`
                : "Typed in."
              : a.auto != null
                ? `Worked out from the courts and size${a.border != null ? " with the border" : ""}. Type a number to use a measured total instead.`
                : "Fill in the size above, or type a measured total for odd shapes."}
          </span>
        </label>
        {paint && (
          <label>
            <span>
              Paintable area <span className="optional">(SF)</span>
            </span>
            <NumInput decimals={0} value={c.paint_sf} onChange={(v) => set("paint_sf", v)} placeholder={a.surface != null ? fmt(a.surface, 0) : "SF"} />
            <span className="help field-help">
              {c.paint_sf !== "" && c.paint_sf != null ? "Typed in. Coating tasks and paint use this." : "Same as the surface. Change it if not all of it gets coated."}
            </span>
          </label>
        )}
      </div>
      {(c.surface_sf !== "" || c.paint_sf !== "") && (
        <button type="button" className="link" onClick={() => onChange({ ...c, surface_sf: "", paint_sf: "" })}>
          Go back to the worked-out area
        </button>
      )}
    </div>
  );
}

// ---------- the questions ----------

const answered = (v) => !(v == null || (typeof v === "string" && !v.trim()) || (Array.isArray(v) && !v.length));

export function shown(q, answers) {
  if (!q.show_if) return true;
  return Object.entries(q.show_if).every(([id, want]) => {
    const wants = Array.isArray(want) ? want : [want];
    const have = answers[id];
    return Array.isArray(have) ? have.some((h) => wants.includes(h)) : wants.includes(have);
  });
}

// Some questions and sections only apply to some court types (no nets on a
// basketball court). With no court type picked, everything shows.
const forCourt = (item, court) => !court || !item.courts || item.courts.includes(court);
export const courtSections = (sections, court) =>
  sections.filter((sec) => forCourt(sec, court)).map((sec) => ({ ...sec, questions: sec.questions.filter((q) => forCourt(q, court)) }));
const allQuestions = (sections, court) => courtSections(sections, court).flatMap((sec) => sec.questions);
const label = (q) => q.long_label ?? q.label;

// What gets saved: only answers (and notes) to questions that are showing
// (follow-ups go when their yes does), with numbers as numbers.
export function tidyAnswers(sections, answers, court) {
  const out = {};
  for (const q of allQuestions(sections, court)) {
    if (!shown(q, out)) continue;
    const v = answers[q.id];
    if (answered(v)) out[q.id] = q.kind === "number" ? Number(v) : typeof v === "string" ? v.trim() : v;
    const note = answers[`${q.id}_note`];
    if (q.kind !== "text" && typeof note === "string" && note.trim()) out[`${q.id}_note`] = note.trim();
  }
  return out;
}

export function checklistProgress(sections, survey, court) {
  const answers = survey?.answers ?? {};
  const a = courtAreas(survey?.court);
  const hasSize = a?.surface != null;
  let done = hasSize ? 1 : 0;
  let total = 1;
  const missing = hasSize ? [] : ["Court size"];
  for (const q of allQuestions(sections, court)) {
    if (!q.required || !shown(q, answers)) continue;
    total += 1;
    if (answered(answers[q.id])) done += 1;
    else missing.push(label(q));
  }
  return { done, total, missing };
}

export function answerText(q, v) {
  if (!answered(v)) return "—";
  if (v === "yes" || v === "no") return v === "yes" ? "Yes" : "No";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "number" || q?.kind === "number") return `${Number(v).toLocaleString("en-US")}${q?.unit ? ` ${q.unit}` : ""}`;
  return String(v);
}

function Segmented({ options, value, onChange, label, multi = false }) {
  const isOn = (o) => (multi ? (value ?? []).includes(o) : value === o);
  const toggle = (o) => {
    if (!multi) return onChange(value === o ? null : o); // tap again to clear
    const cur = value ?? [];
    onChange(cur.includes(o) ? cur.filter((x) => x !== o) : [...cur, o]);
  };
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, l]) => (
        <button type="button" key={v} aria-pressed={isOn(v)} onClick={() => toggle(v)}>
          {l}
        </button>
      ))}
    </div>
  );
}

function Question({ q, value, note, onChange, onNote }) {
  const missing = q.required && !answered(value);
  const [noting, setNoting] = useState(false);
  const showNote = q.kind !== "text" && (noting || answered(note));
  let input;
  if (q.kind === "yesno")
    input = (
      <Segmented
        label={q.label}
        options={[
          ["yes", "Yes"],
          ["no", "No"],
        ]}
        value={value}
        onChange={onChange}
      />
    );
  else if (q.kind === "choice") input = <Segmented label={q.label} options={q.options.map((o) => [o, o])} value={value} onChange={onChange} />;
  else if (q.kind === "multi") input = <Segmented multi label={q.label} options={q.options.map((o) => [o, o])} value={value} onChange={onChange} />;
  else if (q.kind === "number")
    input = (
      <span className="affix">
        <NumInput decimals={2} value={value ?? ""} onChange={(v) => onChange(v === "" ? null : v)} placeholder="0" aria-label={q.label} />
        {q.unit && <span aria-hidden="true">{q.unit}</span>}
      </span>
    );
  else input = <input value={value ?? ""} onChange={(e) => onChange(e.target.value)} aria-label={q.label} maxLength={2000} />;
  return (
    <li className={`cq${q.show_if ? " cq-follow" : ""}${missing ? " cq-missing" : ""}`}>
      <span className="cq-label">
        {q.label}
        {!q.required && <span className="optional"> (optional)</span>}
      </span>
      {q.help && <span className="help field-help">{q.help}</span>}
      {input}
      {q.kind !== "text" &&
        (showNote ? (
          <label className="cq-note">
            <span className="tr-label">Note</span>
            <textarea rows={2} value={note ?? ""} onChange={(e) => onNote(e.target.value)} autoFocus={noting && !answered(note)} maxLength={2000} />
          </label>
        ) : (
          <button type="button" className="link cq-add-note" onClick={() => setNoting(true)}>
            + Add a note
          </button>
        ))}
    </li>
  );
}

/* The checklist on the lead form. `survey` is { court, answers }. */
export function ChecklistForm({ lists, scope, courtType, survey, onChange }) {
  if (!lists) return <p className="help">Loading the checklist…</p>;
  const sections = courtSections(lists.scopes[scope] ?? [], courtType);
  const answers = survey.answers ?? {};
  // Hidden follow-ups keep their answer while you're on the form (a wrong tap
  // doesn't lose the footage you typed); they're dropped when it's saved.
  const setAnswer = (id, v) => onChange({ ...survey, answers: { ...answers, [id]: v } });
  const p = checklistProgress(sections, survey, courtType);
  return (
    <div className="checklist">
      <Progress p={p} />
      <fieldset className="cl-section">
        <legend>{lists.court.title}</legend>
        <p className="help">{lists.court.help}</p>
        <CourtSizeFields court={survey.court} courtType={courtType} onChange={(court) => onChange({ ...survey, court })} />
      </fieldset>
      {sections.map((sec) => (
        <fieldset className="cl-section" key={sec.title}>
          <legend>{sec.title}</legend>
          <ul className="cq-list">
            {sec.questions
              .filter((q) => shown(q, answers))
              .map((q) => (
                <Question
                  key={q.id}
                  q={q}
                  value={answers[q.id]}
                  note={answers[`${q.id}_note`]}
                  onChange={(v) => setAnswer(q.id, v)}
                  onNote={(v) => setAnswer(`${q.id}_note`, v)}
                />
              ))}
          </ul>
        </fieldset>
      ))}
    </div>
  );
}

function Progress({ p }) {
  const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
  return (
    <div className={`cl-progress${p.done === p.total ? " is-done" : ""}`}>
      <span>
        <b>
          {p.done} of {p.total}
        </b>{" "}
        answered{p.done === p.total ? ". Checklist complete." : ""}
      </span>
      <span className="bar" aria-hidden="true">
        <span style={{ width: `${pct}%` }} />
      </span>
    </div>
  );
}

/* What sales found, read-only: for the lead page and the estimator. */
export function ChecklistSummary({ lists, scope, courtType, survey, showMissing = true }) {
  if (!lists) return null;
  const sections = courtSections(lists.scopes[scope] ?? [], courtType);
  const answers = survey?.answers ?? {};
  const a = courtAreas(survey?.court);
  const c = survey?.court ?? {};
  const p = checklistProgress(sections, survey, courtType);
  return (
    <div className="checklist-summary">
      <Progress p={p} />
      <dl className="facts cl-facts">
        <div>
          <dt>Court size</dt>
          <dd>
            {a?.surface != null ? (
              <>
                {fmt(a.surface, 0)} SF
                <span className="sub">
                  {c.length_ft && c.width_ft ? `${c.courts || 1} × ${fmt(c.width_ft, 1)} × ${fmt(c.length_ft, 1)} ft` : ""}
                  {c.surface_sf != null && c.surface_sf !== "" ? `${c.length_ft && c.width_ft ? " · " : ""}measured total` : ""}
                </span>
              </>
            ) : (
              "Not given"
            )}
          </dd>
        </div>
        {sections.flatMap((sec) =>
          sec.questions
            .filter((q) => (answered(answers[q.id]) || answered(answers[`${q.id}_note`])) && shown(q, answers))
            .map((q) => (
              <div key={q.id} className={q.show_if ? "cl-follow" : undefined}>
                <dt>{label(q)}</dt>
                <dd>
                  {answerText(q, answers[q.id])}
                  {answered(answers[`${q.id}_note`]) && <span className="sub cl-note">Note: {answers[`${q.id}_note`]}</span>}
                </dd>
              </div>
            ))
        )}
      </dl>
      {showMissing && p.missing.length > 0 && (
        <p className="help cl-missing">
          <b>Not answered yet:</b> {p.missing.join(" · ")}
        </p>
      )}
    </div>
  );
}

/* An estimate started from the lead: a yes adds the matching task with its
   quantity (or tied to the court size); any other answer takes it off the
   starter list. `make(name)` builds a task from the library. */
// The order work happens in, so a task the checklist adds lands in the right
// spot (the slab goes in before the coatings, not after).
const WORK_ORDER = ["site_work", "drainage", "paving", "prep", "crack_fill", "resurfacer", "color_coat", "lines",
  "nets_posts", "fence", "lighting", "turf", "building", "other", "cleanup"];
const rank = (t) => {
  const r = WORK_ORDER.indexOf(t.task_type);
  return r < 0 ? WORK_ORDER.indexOf("other") : r;
};
function placeFor(tasks, t) {
  const same = tasks.map(rank).lastIndexOf(rank(t));
  if (same >= 0) return same + 1; // after the same kind of work (mildew treatment after the pressure wash)
  const later = tasks.findIndex((x) => rank(x) > rank(t));
  return later >= 0 ? later : tasks.length;
}

// What sales said about this piece of work: the question, its follow-ups
// and any notes ("Fence work: Replace · 240 LF · 8 ft · Note: gate sags").
function noteFor(q, qs, answers) {
  const byId = Object.fromEntries(qs.map((x) => [x.id, x]));
  let root = q;
  while (root.show_if && byId[Object.keys(root.show_if)[0]]) root = byId[Object.keys(root.show_if)[0]];
  const family = [root];
  for (let i = 0; i < family.length; i++)
    for (const x of qs) if (x.show_if && family[i].id in x.show_if && !family.includes(x)) family.push(x);
  const bits = [];
  for (const x of family) {
    if (!shown(x, answers)) continue;
    if (answered(answers[x.id])) bits.push(x === root ? `${label(x)} ${answerText(x, answers[x.id])}` : `${label(x).replace(/\?$/, "")}: ${answerText(x, answers[x.id])}`);
    if (answered(answers[`${x.id}_note`])) bits.push(`Note: ${answers[`${x.id}_note`]}`);
  }
  return bits.join(" · ").slice(0, 1900);
}

export function tasksFromChecklist(tasks, sections, survey, make, court) {
  const answers = survey?.answers ?? {};
  const qs = allQuestions(sections, court);
  let out = [...tasks];
  for (const q of qs) {
      const v = answers[q.id];
      if (!q.tasks || !answered(v) || !shown(q, answers)) continue;
      for (const def of q.tasks) {
        const wants = def.when_answered ? null : [def.when ?? "yes"].flat();
        const hit = !wants || (Array.isArray(v) ? v.some((x) => wants.includes(x)) : wants.includes(v));
        if (!hit) {
          out = out.filter((t) => !sameName(t.name, def.name));
          continue;
        }
        if (def.only_remove) continue; // the follow-up question adds the right task
        let i = out.findIndex((t) => sameName(t.name, def.name));
        if (i < 0) {
          const t = make(def.name);
          i = placeFor(out, t);
          out.splice(i, 0, t);
        }
        out[i] = { ...out[i], checklist_note: noteFor(q, qs, answers) };
        if (def.qty === "surface" || def.qty === "paint" || def.qty === "courts") out[i] = { ...out[i], follows: def.qty };
        else if (def.qty && answered(answers[def.qty])) out[i] = { ...out[i], quantity: String(answers[def.qty]), follows: "" };
      }
    }
  return out;
}
