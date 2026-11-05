// Material the crew lead asked for from the field, signed by name. The shop,
// the GM or a PM marks it sent, or declines it with a reason. Shown on the
// Materials tab (everything still waiting) and on each job page.
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { NoteAction, fmtWhen } from "./bits";
import { fmt } from "./qty";

const WORD = { open: "Waiting", sent: "Sent", declined: "Declined" };

export default function MaterialRequests({ jobId, canHandle, onChanged, title = "Material asked for from the site", hideEmpty = false }) {
  const [rows, setRows] = useState(null);
  const load = useCallback(() => {
    api(jobId ? `/api/jobs/${jobId}/material-requests` : "/api/material-requests?status=recent")
      .then(setRows)
      .catch(() => setRows((r) => r ?? []));
  }, [jobId]);
  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);
  const handle = (r, status) => (note) =>
    api(`/api/material-requests/${r.id}/handle`, { method: "POST", body: { status, note } }).then(() => {
      load();
      onChanged?.();
    });
  if (!rows || (hideEmpty && !rows.length)) return null;
  const waiting = rows.filter((r) => r.status === "open").length;
  return (
    <section className={`panel${waiting ? " has-requests" : ""}`}>
      <h3>
        {title}
        {waiting > 0 && <span className="count warn">{waiting} waiting</span>}
      </h3>
      {!rows.length ? (
        <p className="help">Nothing asked for. When a crew lead runs short, what they ask for shows up here.</p>
      ) : (
        <ul className="reports">
          {rows.map((r) => (
            <li key={r.id} className={r.status === "open" ? "is-waiting" : ""}>
              <p>
                <b>
                  {fmt(r.quantity)} {r.unit} {r.description}
                </b>
                {!jobId && <span className="sub-inline"> for {r.job_name}</span>}
                <span className={`chip chip-req-${r.status}`}>{WORD[r.status]}</span>
              </p>
              <p>{r.reason}</p>
              <p className="sub">
                Asked by {r.by}, signed “{r.signed_name}” · {fmtWhen(r.at)}
              </p>
              {r.status !== "open" && (
                <p className={r.status === "sent" ? "r-resolved" : "err"}>
                  {WORD[r.status]} by {r.handled_by} {fmtWhen(r.handled_at)}
                  {r.handled_note ? `: ${r.handled_note}` : ""}
                </p>
              )}
              {canHandle && r.status === "open" && (
                <div className="req-actions">
                  <NoteAction label="Mark sent" prompt="Anything to add? (optional)" placeholder="e.g. On the truck with Luis, 2 pm"
                    required={false} onSubmit={handle(r, "sent")} />
                  <NoteAction label="Decline" tone="danger" prompt="Why not?" placeholder="e.g. There's enough left on site; check the trailer"
                    onSubmit={handle(r, "declined")} />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
      {!jobId && <p className="help">Sending it from stock? Also record it on the job's list below so the job's material cost stays right.</p>}
    </section>
  );
}
