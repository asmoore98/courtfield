// Leads: what sales brings in for an estimator to price.
import { useEffect, useState } from "react";
import { api } from "./api";
import { ClientPicker, saveClient } from "./ClientPicker";
import { COURT_TYPES, SCOPE_TYPES } from "./JobEditor";
import Photos, { uploadAll } from "./Photos";
import { ChecklistForm, ChecklistSummary, blankCourt, courtBody, courtForm, tidyAnswers, useChecklists } from "./Checklist";
import {
  ActivityList, AddressFields, COURT_LABEL, LEAD_STATUS, LinkList, LinksField, NoteAction, Restored, addressBody, addressFrom, blankAddress, noEnterSubmit, SCOPE_LABEL, StatusChip, fmtDate, money0, useApi, useDraft, useScreen,
} from "./bits";

const SCREEN_KEY = "cf.leads.screen";

export default function LeadsView({ me, go, initial }) {
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const toList = () => setScreen({ view: "list" });
  const open = (id) => setScreen({ view: "lead", id });

  if (screen.view === "edit")
    return <LeadForm me={me} leadId={screen.id} clientId={screen.clientId} onDone={open} onCancel={() => (screen.id ? open(screen.id) : toList())} />;
  if (screen.view === "lead")
    return <LeadDetail me={me} id={screen.id} go={go} onBack={toList} onEdit={() => setScreen({ view: "edit", id: screen.id })} />;
  return <LeadList me={me} onOpen={open} onNew={() => setScreen({ view: "edit" })} />;
}

function LeadList({ me, onOpen, onNew }) {
  const { data, error } = useApi("/api/leads");
  const [filter, setFilter] = useState("open");
  if (error && !data) return <p className="empty">Couldn't load leads: {error}</p>;
  if (!data) return <p className="empty">Loading leads…</p>;
  const groups = {
    open: (l) => ["new", "estimating"].includes(l.outcome),
    estimated: (l) => ["estimated", "expired"].includes(l.outcome),
    won: (l) => l.outcome === "won",
    lost: (l) => ["lost", "no_bid", "dropped"].includes(l.outcome),
    all: () => true,
  };
  const filters = [
    ["open", "Open"],
    ["estimated", "Estimate sent"],
    ["won", "Won"],
    ["lost", "Lost / dropped"],
    ["all", "All"],
  ];
  const shown = data.filter(groups[filter]);
  const waiting = data.filter((l) => l.status === "new" && !l.sent_at).length;

  return (
    <div className="sales">
      <div className="list-head spread">
        <h2 className="detail-title">Leads</h2>
        <button className="btn" onClick={onNew}>
          New lead
        </button>
      </div>
      {waiting > 0 && (
        <p className="follow-note">
          <b>{waiting === 1 ? "1 lead hasn't" : `${waiting} leads haven't`} been sent to estimating yet.</b> Open it and tap Send to estimating when it's
          wrapped up.
        </p>
      )}
      <div className="filter-row" role="group" aria-label="Show leads">
        {filters.map(([k, l]) => (
          <button key={k} className="filter" aria-pressed={filter === k} onClick={() => setFilter(k)}>
            {l} <span className="count">{data.filter(groups[k]).length}</span>
          </button>
        ))}
      </div>
      {!shown.length ? (
        <p className="empty">{data.length ? "Nothing here." : "No leads yet. Add one with New lead."}</p>
      ) : (
        <ul className="joblist">
          {shown.map((l) => (
            <li key={l.id}>
              <button className="jobrow" onClick={() => onOpen(l.id)}>
                <span className="jobrow-head">
                  <span className="jobrow-name">{l.name}</span>
                  <StatusChip status={l.outcome} label={LEAD_STATUS[l.outcome]} />
                </span>
                <span className="jobrow-foot">
                  <span>{l.client_name}</span>
                  {l.court_type && <span>{COURT_LABEL[l.court_type]}{l.scope_type && `, ${SCOPE_LABEL[l.scope_type].toLowerCase()}`}</span>}
                  {l.salesperson && <span>Sales: {l.salesperson}</span>}
                  {l.checklist && (
                    <span className={l.checklist.done < l.checklist.total ? "t-near" : ""}>
                      Checklist {l.checklist.done}/{l.checklist.total}
                    </span>
                  )}
                  {l.status === "new" && <span className={l.sent_at ? "" : "t-near"}>{l.sent_at ? "With estimating" : "Not sent to estimating"}</span>}
                  {l.bid_due && <span className={new Date(l.bid_due) < new Date() && l.status === "new" ? "t-over" : ""}>Bid due {fmtDate(l.bid_due + "T12:00:00")}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function LeadDetail({ me, id, go, onBack, onEdit }) {
  const { data: l, error, reload } = useApi(`/api/leads/${id}`);
  const lists = useChecklists();
  const [sendErr, setSendErr] = useState(null);
  if (error && !l) return <p className="empty">Couldn't load the lead: {error}</p>;
  if (!l) return <p className="empty">Loading lead…</p>;
  const setStatus = (status, reason) => api(`/api/leads/${id}/status`, { method: "POST", body: { status, reason } }).then(reload);
  const send = (what) => {
    setSendErr(null);
    api(`/api/leads/${id}/${what}`, { method: "POST", body: {} }).then(reload, (e) => setSendErr(e.message));
  };

  return (
    <div className="detail sales">
      <button className="link back" onClick={onBack}>
        All leads
      </button>
      <div className="detail-head">
        <div>
          <p className="eyebrow">
            Lead · <StatusChip status={l.outcome} label={LEAD_STATUS[l.outcome]} />
          </p>
          <h2 className="detail-title">{l.name}</h2>
          <p className="detail-sub">
            <button className="link" onClick={() => go("clients", { view: "client", id: l.client_id })}>
              {l.client_name}
            </button>
            {l.salesperson && ` · Sales: ${l.salesperson}`}
            {l.bid_due && ` · Bid due ${fmtDate(l.bid_due + "T12:00:00")}`}
          </p>
        </div>
      </div>

      <section className="panel">
        <h3>What's next</h3>
        {l.status === "new" &&
          (l.sent_at ? (
            <p className="help">
              Sent to estimating by {l.sent_by ?? "sales"} on {fmtDate(l.sent_at)}.{" "}
              <button className="link" onClick={() => send("unsend")}>
                Take it back to finish it
              </button>
            </p>
          ) : (
            <div className="send-box">
              <p>
                <b>Wrapped up?</b> Send it to the estimators. It shows up on their Estimates tab as a new lead to estimate.
              </p>
              {l.checklist && l.checklist.done < l.checklist.total && (
                <p className="help t-near">
                  {l.checklist.total - l.checklist.done} checklist question{l.checklist.total - l.checklist.done > 1 ? "s" : ""} not answered:{" "}
                  {l.checklist.missing.slice(0, 6).join(" · ")}
                  {l.checklist.missing.length > 6 ? " …" : ""}
                </p>
              )}
              <button className="btn" onClick={() => send("send")}>
                Send to estimating
              </button>
            </div>
          ))}
        {sendErr && <p className="err">{sendErr}</p>}
        <div className="action-row">
          {me.estimates && l.status !== "dropped" && l.outcome !== "won" && (
            <button className="btn" onClick={() => go("estimates", { view: "edit", leadId: l.id })}>
              {l.estimates.length ? "Start another estimate" : "Start the estimate"}
            </button>
          )}
          <button className="btn-ghost" onClick={onEdit}>
            Edit lead
          </button>
          {l.status !== "dropped" ? (
            <NoteAction label="Drop lead" tone="danger" prompt="Why are we dropping it?" onSubmit={(n) => setStatus("dropped", n)} />
          ) : (
            <NoteAction label="Reopen lead" prompt="Why reopen it?" onSubmit={(n) => setStatus("new", n)} />
          )}
        </div>
        {l.status === "dropped" && l.status_reason && <p className="help">Dropped: {l.status_reason}</p>}
      </section>

      <section className="panel">
        <h3>Details</h3>
        <dl className="facts">
          <div>
            <dt>Site</dt>
            <dd>
              {l.site_address || "No address yet"}
              {l.parcel_id && <span className="sub">Parcel {l.parcel_id}</span>}
            </dd>
          </div>
          <div>
            <dt>Work</dt>
            <dd>{l.court_type ? `${COURT_LABEL[l.court_type]}${l.scope_type ? `, ${SCOPE_LABEL[l.scope_type].toLowerCase()}` : ""}` : "Not set"}</dd>
          </div>
        </dl>
        {l.description ? <p className="pre">{l.description}</p> : <p className="help">No description yet.</p>}
        <h4>Plans &amp; documents</h4>
        <LinkList text={l.links} empty="No links yet. Edit the lead to paste Google Drive links." />
      </section>

      <section className="panel">
        <Photos kind="lead" id={l.id} />
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Site checklist</h3>
          <button className="link" onClick={onEdit}>
            {l.checklist && l.checklist.done > 1 ? "Update it" : "Fill it in"}
          </button>
        </div>
        {l.scope_type ? (
          <ChecklistSummary lists={lists} scope={l.scope_type} courtType={l.court_type} survey={l.survey} />
        ) : (
          <p className="help">Set the scope (resurfacing, repair or new construction) to get its checklist.</p>
        )}
      </section>

      {l.estimates.length > 0 && (
        <section className="panel">
          <h3>Estimates</h3>
          <ul className="row-list">
            {l.estimates.map((e) => (
              <li key={e.id}>
                <button className="row-btn" onClick={() => go("estimates", { view: "detail", id: e.id })}>
                  <span className="row-main">
                    <b>{e.number}</b> · v{e.version}
                    <span className="sub">{e.name}</span>
                  </span>
                  <span className="row-side">
                    <StatusChip status={e.status} />
                    <span className="sub">{money0(e.price)}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ActivityList items={l.activity} />
    </div>
  );
}

const blankLead = () => ({
  client_id: "",
  new_client: null,
  name: "",
  site_address: "",
  site: blankAddress(),
  parcel_id: "",
  court_type: "",
  scope_type: "",
  description: "",
  links: "",
  bid_due: "",
  salesperson_id: "",
  survey: { court: blankCourt(), answers: {} },
});

function LeadForm({ me, leadId, clientId, onDone, onCancel }) {
  const d = useDraft(`cf.draft.lead.${leadId ?? "new"}`, { ...blankLead(), client_id: clientId ?? "" });
  const [people, setPeople] = useState([]);
  const [loaded, setLoaded] = useState(!leadId || !!d.restoredAt);
  const [fetchN, setFetchN] = useState(0);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const lists = useChecklists();
  const [pending, setPending] = useState([]); // photos picked before a new lead is saved
  const [sending, setSending] = useState(null);
  const f = d.form;
  const survey = f.survey ?? { court: blankCourt(), answers: {} };
  const site = f.site ?? addressFrom({}, "site", f.site_address); // drafts from before the address was split

  useEffect(() => {
    api("/api/estimates/people").then(setPeople).catch(() => {});
  }, []);
  useEffect(() => {
    if (!leadId || d.restoredAt) return;
    api(`/api/leads/${leadId}`)
      .then((l) => {
        d.discard({
          ...blankLead(), ...l, court_type: l.court_type ?? "", scope_type: l.scope_type ?? "", bid_due: l.bid_due ?? "", salesperson_id: l.salesperson_id ?? "",
          survey: { court: courtForm(l.survey?.court), answers: l.survey?.answers ?? {} },
          site: addressFrom(l, "site", l.site_address),
        });
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
  }, [leadId, fetchN]);

  if (!loaded) return <p className="empty">{error ?? "Loading lead…"}</p>;

  async function save(e) {
    e.preventDefault();
    setError(null);
    if (!f.name.trim()) return setError("Give the lead a project name.");
    setSaving(true);
    try {
      const client_id = await saveClient(f.client_id, f.new_client);
      const body = {
        client_id,
        name: f.name.trim(),
        ...addressBody(site, "site", "site_address"),
        parcel_id: f.parcel_id.trim(),
        court_type: f.court_type || null,
        scope_type: f.scope_type || null,
        description: f.description,
        links: f.links,
        bid_due: f.bid_due || null,
        salesperson_id: f.salesperson_id || null,
        // the checklist for the scope chosen; left as it was if the questions didn't load
        survey: lists ? { court: courtBody(survey.court), answers: tidyAnswers(lists.scopes[f.scope_type] ?? [], survey.answers, f.court_type || null) } : null,
      };
      const saved = leadId ? await api(`/api/leads/${leadId}`, { method: "PUT", body }) : await api("/api/leads", { method: "POST", body });
      d.done();
      if (pending.length) await uploadAll("lead", saved.id, pending, (i, n) => setSending(`Uploading photo ${i} of ${n}…`));
      onDone(saved.id);
    } catch (err) {
      setError(err.status === 0 ? "No connection. Your work is kept on this device; save again when you have signal." : err.message);
      setSaving(false);
    }
  }

  return (
    <form className="editor" onSubmit={save} onKeyDown={noEnterSubmit}>
      <button type="button" className="link back" onClick={onCancel}>
        {leadId ? "Back to lead" : "All leads"}
      </button>
      <h2 className="detail-title">{leadId ? "Edit lead" : "New lead"}</h2>
      <Restored at={d.restoredAt} label={leadId ? "Throw it away" : "Start over"} onDiscard={() => {
          d.discard(blankLead());
          if (leadId) {
            setLoaded(false);
            setFetchN((n) => n + 1);
          }
        }} />

      <section className="panel">
        <h3>Who</h3>
        <ClientPicker
          clientId={f.client_id}
          newClient={f.new_client}
          onChange={(cid, nc) => d.setForm({ ...f, client_id: cid, new_client: nc })}
        />
        {me.role !== "sales" && (
          <div className="grid extra-top">
            <label>
              Salesperson
              <select value={f.salesperson_id} onChange={(e) => d.set("salesperson_id", e.target.value)}>
                <option value="">None</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </section>

      <section className="panel">
        <h3>Details</h3>
        <div className="grid">
          <label className="span-2">
            Project name
            <input value={f.name} onChange={(e) => d.set("name", e.target.value)} placeholder="e.g. Harbor Pointe – 2 pickleball courts" required />
          </label>
          <label>
            Court type <span className="optional">(if known)</span>
            <select value={f.court_type} onChange={(e) => d.set("court_type", e.target.value)}>
              <option value="">Not sure yet</option>
              {COURT_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Scope <span className="optional">(if known)</span>
            <select value={f.scope_type} onChange={(e) => d.set("scope_type", e.target.value)}>
              <option value="">Not sure yet</option>
              {SCOPE_TYPES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label className="span-2">
            Description
            <span className="help field-help">Court count and sizes, what's there now, wants and must-haves, budget, timing, who decides.</span>
            <textarea rows={5} value={f.description} onChange={(e) => d.set("description", e.target.value)} />
          </label>
          <label>
            Bid due <span className="optional">(optional)</span>
            <input type="date" value={f.bid_due} onChange={(e) => d.set("bid_due", e.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel">
        <h3>Where</h3>
        <AddressFields section="site" value={site} onChange={(v) => d.set("site", v)} />
        <div className="grid">
          <label className="span-2">
            <span>
              Parcel ID <span className="optional">(optional)</span>
            </span>
            <input value={f.parcel_id} onChange={(e) => d.set("parcel_id", e.target.value)} maxLength={60} />
          </label>
        </div>
      </section>

      <section className="panel">
        <h3>Site checklist</h3>
        {f.scope_type ? (
          <>
            <p className="help">
              Fill this in on site. Every answer goes straight into the estimate, so the more exact it is, the closer the bid. Follow-up questions show up as you answer.
            </p>
            <ChecklistForm lists={lists} scope={f.scope_type} courtType={f.court_type} survey={survey} onChange={(v) => d.set("survey", v)} />
          </>
        ) : (
          <p className="help">Pick the scope above (resurfacing, repair or new construction) and its checklist shows up here.</p>
        )}
      </section>

      <section className="panel">
        <LinksField id="lead-links" value={f.links} onChange={(v) => d.set("links", v)} />
      </section>

      <section className="panel">
        <Photos kind="lead" id={leadId} pending={pending} onPending={setPending} />
      </section>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="editor-actions">
        <button type="button" className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn" disabled={saving}>
          {saving ? sending ?? "Saving…" : leadId ? "Save changes" : "Save lead"}
        </button>
      </div>
    </form>
  );
}
