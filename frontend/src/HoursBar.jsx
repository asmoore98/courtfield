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
