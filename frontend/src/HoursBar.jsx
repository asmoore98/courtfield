// Hours used against the estimate, drawn like a court lane: the estimate is a
// painted baseline, logged hours fill the lane, and anything past the
// baseline runs red. Hours still on the clock show hatched.

export function statusOf(used) {
  if (used == null) return "none";
  if (used > 1) return "over";
  if (used >= 0.9) return "near";
  return "under";
}

const fmt = (h) => (h >= 10 ? Math.round(h) : Math.round(h * 10) / 10);

export default function HoursBar({ estimated, actual, open = 0, size = "md" }) {
  const used = actual + open;
  const span = Math.max(estimated, used, 0.01) * 1.08;
  const pct = (h) => `${(h / span) * 100}%`;
  const within = Math.min(actual, estimated);
  const overClosed = Math.max(0, actual - estimated);
  const status = estimated > 0 ? statusOf(used / estimated) : "none";
  const label =
    estimated > 0
      ? `${fmt(used)} of ${fmt(estimated)} estimated hours used${open ? `, ${fmt(open)} on the clock now` : ""}`
      : `${fmt(used)} hours, no estimate`;

  return (
    <div className={`lane lane-${size} is-${status}`} role="img" aria-label={label}>
      <div className="lane-fill" style={{ width: pct(within) }} />
      {overClosed > 0 && <div className="lane-over" style={{ left: pct(estimated), width: pct(overClosed) }} />}
      {open > 0 && <div className="lane-open" style={{ left: pct(actual), width: pct(open) }} />}
      {estimated > 0 && <div className="lane-baseline" style={{ left: pct(estimated) }} />}
    </div>
  );
}

export function HoursText({ estimated, actual, open = 0 }) {
  const used = actual + open;
  const status = estimated > 0 ? statusOf(used / estimated) : "none";
  return (
    <span className={`hours-text t-${status}`}>
      <b>{fmt(used)}</b> / {fmt(estimated)} h
    </span>
  );
}

// How a task's hours compare with how far along it is: 50% done should
// have used about half the planned hours. Hours come from the clock.
export function paceOf(pct, estimated, used) {
  if (!pct || !estimated) return null;
  const expected = (estimated * pct) / 100;
  const r = (n) => Math.round(n * 10) / 10;
  if (!used) return { tone: "none", text: "No hours clocked on this task yet" };
  if (pct === 100 && used > estimated * 1.05) return { tone: "behind", text: `Done in ${r(used)} hrs, ${r(used - estimated)} over the ${r(estimated)} planned` };
  if (pct === 100) return { tone: "on", text: `Done in ${r(used)} of ${r(estimated)} hrs planned` };
  if (used > expected * 1.15) return { tone: "behind", text: `Behind: ${r(used)} hrs used for ${pct}% (about ${r(expected)} planned)` };
  if (used < expected * 0.85) return { tone: "ahead", text: `Ahead: ${r(used)} hrs used for ${pct}% (about ${r(expected)} planned)` };
  return { tone: "on", text: `On pace: ${r(used)} hrs used for ${pct}%` };
}

export function Pace({ pct, estimated, used }) {
  const p = paceOf(pct, estimated, used);
  return p ? <span className={`pace pace-${p.tone}`}>{p.text}</span> : null;
}
