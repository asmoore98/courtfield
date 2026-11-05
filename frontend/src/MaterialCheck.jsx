// Checking a job's material, item by item: the shop checks the truck is
// loaded before it leaves ("loaded"), and the crew lead checks it's all on
// site ("on_site"). Anything short on site goes to the office as a problem.
// No dollars here: crews never see them.
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { fmtWhen } from "./bits";
import { fmt } from "./qty";

const WHAT = { loaded: "Truck loaded", on_site: "On site" };

function Summary({ c, kind }) {
  if (!c)
    return (
      <p className="mc-line mc-none">
        {kind === "loaded" ? "The shop hasn't checked the truck yet." : "Not checked on site yet."}
      </p>
    );
  const short = c.items.filter((i) => i.here < i.expected);
  return (
    <div className={`mc-line ${c.all_here ? "mc-ok" : "mc-short"}`}>
      <p>
        <b>{WHAT[c.kind]}:</b> {c.all_here ? "everything there" : `${short.length} short`} · checked by {c.by}, {fmtWhen(c.at)}
      </p>
      {short.length > 0 && (
        <ul>
          {short.map((i) => (
            <li key={i.key}>
              {i.description}: {fmt(i.here)} of {fmt(i.expected)} {i.unit}
            </li>
          ))}
        </ul>
      )}
      {c.note && <p className="sub">{c.note}</p>}
    </div>
  );
}

export default function MaterialCheck({ jobId, kind, canCheck = true, onSaved, showOther = true }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [short, setShort] = useState({}); // key -> how many are here
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const load = useCallback(() => {
    api(`/api/jobs/${jobId}/material-checks`).then(setData).catch(() => setData((d) => d ?? { expected: {}, checks: [] }));
  }, [jobId]);
  useEffect(() => void load(), [load]);
  if (!data) return null;
  const items = data.expected[kind] ?? [];
  const last = (k) => data.checks.find((c) => c.kind === k);
  const other = kind === "on_site" ? "loaded" : "on_site";
  const anyShort = Object.keys(short).length > 0;

  async function save() {
    setError(null);
    if (anyShort && note.trim().length < 3) return setError("Say what happened with what's short.");
    setBusy(true);
    try {
      await api(`/api/jobs/${jobId}/material-checks`, {
        method: "POST",
        body: { kind, note: note.trim(), items: Object.entries(short).map(([key, here]) => ({ key, here: Number(here) || 0 })) },
      });
      setOpen(false);
      setShort({});
      setNote("");
      load();
      onSaved?.();
    } catch (e) {
      setError(e.status === 0 ? "No signal. Try again in a minute; your check is still here." : e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!items.length) return <p className="help">No material on this job's list to check.</p>;
  return (
    <div className="mat-check">
      {showOther && <Summary c={last(other)} kind={other} />}
      <Summary c={last(kind)} kind={kind} />
      {canCheck && !open && (
        <button className="btn-ghost" onClick={() => setOpen(true)}>
          {last(kind) ? "Check again" : kind === "loaded" ? "Check the truck" : "Check the material on site"}
        </button>
      )}
      {open && (
        <div className="mc-form">
          <p className="help">
            {kind === "loaded"
              ? "Everything planned for this job. Tap Short for anything that isn't on the truck."
              : "What the shop sent. Tap Short for anything that isn't here, and say how many are."}
          </p>
          <ul className="mc-items">
            {items.map((i) => {
              const isShort = i.key in short;
              return (
                <li key={i.key} className={isShort ? "is-short" : ""}>
                  <span className="mc-name">
                    {i.description}
                    <span className="sub">
                      {fmt(i.expected)} {i.unit}
                    </span>
                  </span>
                  <div className="seg" role="group" aria-label={i.description}>
                    <button type="button" aria-pressed={!isShort} onClick={() => setShort(({ [i.key]: _, ...rest }) => rest)}>
                      Here
                    </button>
                    <button type="button" aria-pressed={isShort} onClick={() => setShort((s) => ({ ...s, [i.key]: s[i.key] ?? "" }))}>
                      Short
                    </button>
                  </div>
                  {isShort && (
                    <label className="mc-here">
                      How many are {kind === "loaded" ? "on the truck" : "here"}?
                      <input type="number" inputMode="decimal" min="0" step="any" value={short[i.key]}
                        onChange={(e) => setShort((s) => ({ ...s, [i.key]: e.target.value }))} />
                    </label>
                  )}
                </li>
              );
            })}
          </ul>
          <label className="mc-note">
            {anyShort ? "What happened? (needed)" : "Note (optional)"}
            <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)}
              placeholder={anyShort ? "e.g. Only 3 pails of color on the truck, 1 still at the shop" : ""} />
          </label>
          {error && <p className="err">{error}</p>}
          <div className="note-buttons">
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); setShort({}); setError(null); }}>
              Cancel
            </button>
            <button className="btn" onClick={save} disabled={busy}>
              {busy ? "Saving…" : anyShort ? (kind === "on_site" ? "Send what's short to the office" : "Save: some is short") : "Everything is here"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
