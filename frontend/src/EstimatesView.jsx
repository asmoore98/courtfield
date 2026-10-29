// Estimates: list with follow-ups, detail with locked versions and history,
// the estimate form, and the printable proposal.
import { useEffect, useState } from "react";
import { api } from "./api";
import { ClientPicker, saveClient } from "./ClientPicker";
import { EstimateTable, ScopeEditor, blankJob, formFrom, money2, num, starterTasks } from "./JobEditor";
import {
  ActivityList, COURT_LABEL, ESTIMATE_STATUS, LinkList, LinksField, NoteAction, SCOPE_LABEL, StatusChip, fmtDate, fmtWhen, money0, useApi, useScreen,
} from "./bits";
import ProposalView from "./ProposalView";

const SCREEN_KEY = "cf.estimates.screen";
const CAT_LABEL = { material: "Material", equipment: "Rental", subcontractor: "Sub", other: "Other" };
const asEst = (t) => t && { ...t, contract: t.price };

export default function EstimatesView({ me, go, initial }) {
  // An open estimate form is remembered across tab switches; its unsaved work
  // is kept as a draft by the form itself.
  const [screen, setScreen] = useScreen(SCREEN_KEY, initial);
  const toList = () => setScreen({ view: "list" });
  const open = (id) => setScreen({ view: "detail", id });

  if (screen.view === "edit")
    return (
      <EstimateEditor
        me={me}
        estimateId={screen.id}
        leadId={screen.leadId}
        onDone={(id) => open(id)}
        onCancel={() => (screen.id ? open(screen.id) : toList())}
      />
    );
  if (screen.view === "proposal") return <ProposalView id={screen.id} onBack={() => open(screen.id)} />;
  if (screen.view === "detail")
    return (
      <EstimateDetail
        me={me}
        id={screen.id}
        go={go}
        onBack={toList}
        onEdit={() => setScreen({ view: "edit", id: screen.id })}
        onProposal={() => setScreen({ view: "proposal", id: screen.id })}
      />
    );
  return <EstimateList me={me} onOpen={open} onNew={() => setScreen({ view: "edit" })} />;
}

// ---------- list ----------

function EstimateList({ me, onOpen, onNew }) {
  const { data, error } = useApi("/api/estimates");
  const [filter, setFilter] = useState("open");
  if (error && !data) return <p className="empty">Couldn't load estimates: {error}</p>;
  if (!data) return <p className="empty">Loading estimates…</p>;

  const counts = Object.fromEntries(ESTIMATE_STATUS.map(([s]) => [s, data.filter((e) => e.status === s).length]));
  const filters = [["open", "Open", data.filter((e) => ["draft", "sent"].includes(e.status)).length], ...ESTIMATE_STATUS.map(([s, l]) => [s, l, counts[s]]), ["all", "All", data.length]];
  const shown = data.filter((e) => filter === "all" || (filter === "open" ? ["draft", "sent"].includes(e.status) : e.status === filter));
  const followUps = data.filter((e) => e.follow_up);

  return (
    <div className="sales">
      <div className="list-head spread">
        <h2 className="detail-title">Estimates</h2>
        {me.estimates && (
          <button className="btn" onClick={onNew}>
            New estimate
          </button>
        )}
      </div>

      {followUps.length > 0 && (
        <section className="panel follow-ups">
          <h3>Needs follow-up</h3>
          <ul className="row-list">
            {followUps.map((e) => (
              <li key={e.id}>
                <button className="row-btn" onClick={() => onOpen(e.id)}>
                  <span className="row-main">
                    <b>{e.client_name}</b> · {e.name}
                    <span className="sub">{e.follow_up}</span>
                  </span>
                  <span className="row-side">
                    <StatusChip status={e.status} />
                    <span className="sub">{e.number}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="filter-row" role="group" aria-label="Show estimates">
        {filters.map(([k, l, n]) => (
          <button key={k} className="filter" aria-pressed={filter === k} onClick={() => setFilter(k)}>
            {l} <span className="count">{n}</span>
          </button>
        ))}
      </div>

      {!shown.length ? (
        <p className="empty">{data.length ? "Nothing here." : me.estimates ? "No estimates yet. Start one with New estimate, or from a lead." : "No estimates of yours yet."}</p>
      ) : (
        <ul className="joblist">
          {shown.map((e) => (
            <li key={e.id}>
              <button className="jobrow" onClick={() => onOpen(e.id)}>
                <span className="jobrow-head">
                  <span className="jobrow-name">{e.name}</span>
                  <StatusChip status={e.status} />
                </span>
                <span className="jobrow-foot">
                  <span>
                    {e.number} · v{e.version} · {e.client_name}
                  </span>
                  {e.salesperson && <span>Sales: {e.salesperson}</span>}
                  {e.status === "sent" && e.valid_until && <span>Good until {fmtDate(e.valid_until)}</span>}
                  <span className="money">
                    <b>{money0(e.price)}</b>
                    {e.margin_pct != null && <span className={e.margin_pct < 0 ? "t-over" : e.margin_pct < 0.15 ? "t-near" : ""}> · {Math.round(e.margin_pct * 100)}% margin</span>}
                  </span>
                </span>
                {e.follow_up && <span className="row-flag">{e.follow_up}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------- detail ----------

function EstimateDetail({ me, id, go, onBack, onEdit, onProposal }) {
  const { data: e, error, reload } = useApi(`/api/estimates/${id}`);
  const [pick, setPick] = useState(null); // version number being viewed; null = current
  const [actError, setActError] = useState(null);
  const [busy, setBusy] = useState(false);
  const viewing = pick ?? e?.version;
  const old = useApi(me.estimates && e && pick && pick !== e.version ? `/api/estimates/${id}/versions/${pick}` : null);

  if (error && !e) return <p className="empty">Couldn't load the estimate: {error}</p>;
  if (!e) return <p className="empty">Loading estimate…</p>;

  const shownData = pick && pick !== e.version ? old.data?.data : e.data;
  const shownTotals = pick && pick !== e.version ? old.data?.totals : e.totals;
  const shownMeta = e.versions.find((v) => v.version === viewing);
  const locked = !!e.job_id;

  async function act(fn) {
    setActError(null);
    setBusy(true);
    try {
      await fn();
      reload();
    } catch (err) {
      setActError(err.message);
      throw err;
    } finally {
      setBusy(false);
    }
  }
  const setStatus = (status, note = "") => act(() => api(`/api/estimates/${id}/status`, { method: "POST", body: { status, note } }));

  async function makeJob() {
    setActError(null);
    setBusy(true);
    try {
      const { job_id } = await api(`/api/estimates/${id}/create-job`, { method: "POST" });
      go("office", { view: "job", id: job_id });
    } catch (err) {
      setActError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="detail sales">
      <button className="link back" onClick={onBack}>
        All estimates
      </button>
      <div className="detail-head">
        <div>
          <p className="eyebrow">
            {e.number} · <StatusChip status={e.status} />
          </p>
          <h2 className="detail-title">{e.name}</h2>
          <p className="detail-sub">
            <button className="link" onClick={() => go("clients", { view: "client", id: e.client_id })}>
              {e.client.name}
            </button>
            {e.client.contact_name && ` · ${e.client.contact_name}`}
            {e.client.phone && (
              <>
                {" · "}
                <a href={`tel:${e.client.phone}`}>{e.client.phone}</a>
              </>
            )}
            {e.salesperson && ` · Sales: ${e.salesperson}`}
            {e.lead_id && (
              <>
                {" · "}
                <button className="link" onClick={() => go("leads", { view: "lead", id: e.lead_id })}>
                  From a lead
                </button>
              </>
            )}
          </p>
        </div>
        <div className="detail-figures tight">
          <div>
            <span className="fig">{money0(shownMeta?.price ?? e.price)}</span>
            <span className="fig-label">proposal price</span>
          </div>
          {shownMeta?.total_cost != null && (
            <div>
              <span className="fig">{money0(shownMeta.total_cost)}</span>
              <span className="fig-label">our cost</span>
            </div>
          )}
        </div>
      </div>

      {e.follow_up && (
        <p className="follow-note" role="status">
          <b>Follow up:</b> {e.follow_up}
        </p>
      )}
      {e.status === "sent" && e.valid_until && !e.follow_up && <p className="help">Sent {fmtDate(e.sent_at)}. Good until {fmtDate(e.valid_until)}.</p>}

      {/* status and next steps */}
      <section className="panel">
        <h3>What's next</h3>
        {locked ? (
          <p>
            Won, and a job was made from it.{" "}
            <button className="link" onClick={() => go("office", { view: "job", id: e.job_id })}>
              Open the job
            </button>
          </p>
        ) : (
          <div className="action-row">
            {me.estimates && e.status !== "won" && (
              <button className="btn" onClick={onEdit}>
                Edit (saves as v{Math.max(...e.versions.map((v) => v.version)) + 1})
              </button>
            )}
            {me.estimates && e.status === "won" && (
              <button className="btn" onClick={makeJob} disabled={busy}>
                Create job from this estimate
              </button>
            )}
            {["draft", "lost", "no_bid"].includes(e.status) && (
              <button className="btn-ghost" disabled={busy} onClick={() => setStatus("sent").catch(() => {})}>
                Mark sent to client
              </button>
            )}
            {["sent", "expired"].includes(e.status) && (
              <>
                <NoteAction label="Mark won" prompt="Anything to note? (signed date, deposit…) Next you'll make it a job." required={false} onSubmit={(n) => setStatus("won", n)} />
                <NoteAction label="Log a follow-up" prompt="Who did you talk to and what did they say?" placeholder="Called Dana, board votes on the 15th" onSubmit={(n) => act(() => api(`/api/estimates/${id}/follow-up`, { method: "POST", body: { note: n } }))} />
                <NoteAction label="Re-send" prompt="What changed? (restarts the 30-day clock)" required={false} onSubmit={(n) => setStatus("sent", n)} />
                <NoteAction label="Mark lost" tone="danger" prompt="Why did we lose it? (price, timing, went with someone else…)" onSubmit={(n) => setStatus("lost", n)} />
              </>
            )}
            {["draft", "sent", "expired"].includes(e.status) && (
              <NoteAction label="No bid" tone="danger" prompt="Why aren't we bidding it?" onSubmit={(n) => setStatus("no_bid", n)} />
            )}
            {e.status === "won" && (
              <NoteAction label="Undo won" prompt="Why? (marked by mistake, deal fell through…)" onSubmit={(n) => setStatus("sent", n)} />
            )}
            {["lost", "no_bid"].includes(e.status) && (
              <NoteAction label="Back to draft" prompt="Why reopen it?" onSubmit={(n) => setStatus("draft", n)} />
            )}
            <button className="btn-ghost" onClick={onProposal}>
              Proposal (print / PDF)
            </button>
          </div>
        )}
        {locked && (
          <div className="action-row">
            <button className="btn-ghost" onClick={onProposal}>
              Proposal (print / PDF)
            </button>
          </div>
        )}
        {actError && (
          <p className="alert" role="alert">
            {actError}
          </p>
        )}
      </section>

      {/* versions */}
      <section className="panel">
        <div className="panel-head">
          <h3>Version</h3>
          <label className="inline-field">
            <span className="sr-only">Version to view</span>
            <select value={viewing} onChange={(ev) => setPick(Number(ev.target.value))}>
              {e.versions.map((v) => (
                <option key={v.version} value={v.version}>
                  v{v.version} · {fmtDate(v.created_at)} · {v.by}
                  {v.version === e.version ? " (current)" : ""}
                  {v.removed ? " (removed)" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        {shownMeta && (
          <p className="help">
            {viewing === e.version ? "Current version" : "Older version, locked"}, saved {fmtWhen(shownMeta.created_at)} by {shownMeta.by}.
            {shownMeta.note && <> What changed: “{shownMeta.note}”</>}
            {shownMeta.removed && <b className="t-over"> Removed by the GM: {shownMeta.removed_reason}</b>}
          </p>
        )}
        {me.role === "gm" && shownMeta && !shownMeta.removed && e.versions.filter((v) => !v.removed).length > 1 && !(locked && viewing === e.version) && (
          <NoteAction
            label={`Remove v${viewing}`}
            tone="danger"
            prompt="Why remove it? It stays on record, marked removed."
            onSubmit={(n) =>
              act(() => api(`/api/estimates/${id}/versions/${viewing}/remove`, { method: "POST", body: { reason: n } })).then(() => setPick(null))
            }
          />
        )}
        {!me.estimates ? (
          <p className="help">Open the proposal to see the scope and price the client gets.</p>
        ) : !shownData ? (
          <p className="empty">Loading v{viewing}…</p>
        ) : (
          <VersionSummary d={shownData} t={shownTotals} />
        )}
      </section>

      <ActivityList items={e.activity} />
    </div>
  );
}

function VersionSummary({ d, t }) {
  const lines = d.cost_lines ?? [];
  return (
    <div className="version-summary">
      <dl className="facts">
        <div>
          <dt>Site</dt>
          <dd>{d.site_address || "No address yet"}{d.parcel_id && <span className="sub">Parcel {d.parcel_id}</span>}</dd>
        </div>
        <div>
          <dt>Work</dt>
          <dd>
            {COURT_LABEL[d.court_type]}, {SCOPE_LABEL[d.scope_type].toLowerCase()}
          </dd>
        </div>
        <div>
          <dt>Labor rate</dt>
          <dd>{money2(d.estimated_labor_rate)}/hr</dd>
        </div>
      </dl>
      <div className="est-layout">
        <EstimateTable est={asEst(t)} taxPct={d.sales_tax_pct} priceLabel="Proposal price" />
        <div className="est-lines">
          <h4>Tasks</h4>
          <table className="lines-table">
            <tbody>
              {d.tasks.map((x, i) => (
                <tr key={i}>
                  <th scope="row">{x.name}</th>
                  <td className="num">{x.estimated_hours} h</td>
                </tr>
              ))}
            </tbody>
          </table>
          {lines.length > 0 && (
            <>
              <h4>Materials and other costs</h4>
              <table className="lines-table">
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i}>
                      <th scope="row">
                        {l.description}
                        <span className="sub">
                          {CAT_LABEL[l.category]}
                          {l.task_index != null && d.tasks[l.task_index] ? ` · ${d.tasks[l.task_index].name}` : ""}
                        </span>
                      </th>
                      <td className="num">
                        {l.quantity} {l.unit}
                      </td>
                      <td className="num">{money2(l.quantity * l.unit_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
      {(d.scope_text || d.exclusions) && (
        <div className="prose-pair">
          {d.scope_text && (
            <div>
              <h4>Scope of work (on the proposal)</h4>
              <p className="pre">{d.scope_text}</p>
            </div>
          )}
          {d.exclusions && (
            <div>
              <h4>Not included (on the proposal)</h4>
              <p className="pre">{d.exclusions}</p>
            </div>
          )}
        </div>
      )}
      <h4>Plans &amp; documents</h4>
      <LinkList text={d.links} />
      {d.notes && (
        <>
          <h4>Internal notes</h4>
          <p className="pre">{d.notes}</p>
        </>
      )}
    </div>
  );
}

// ---------- the estimate form ----------

const blankEstimate = (extra = {}) => ({
  ...blankJob(),
  client_id: "",
  new_client: null,
  salesperson_id: "",
  valid_days: "",
  scope_text: "",
  exclusions: "",
  links: "",
  notes: "",
  note: "",
  ...extra,
});

function EstimateEditor({ me, estimateId, leadId, onDone, onCancel }) {
  const [ctx, setCtx] = useState(null); // { estimate?, lead?, people }
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      estimateId ? api(`/api/estimates/${estimateId}`) : null,
      leadId ? api(`/api/leads/${leadId}`) : null,
      api("/api/estimates/people").catch(() => []),
    ])
      .then(([estimate, lead, people]) => setCtx({ estimate, lead, people }))
      .catch((e) => setError(e.message));
  }, [estimateId, leadId]);

  if (error) return <p className="empty">Couldn't open the estimate: {error}</p>;
  if (!ctx) return <p className="empty">Loading…</p>;

  const { estimate: e, lead, people } = ctx;
  const nextV = e ? Math.max(...e.versions.map((v) => v.version)) + 1 : 1;
  const fromLead = lead
    ? {
        client_id: lead.client_id,
        name: lead.name,
        address: lead.site_address,
        parcel_id: lead.parcel_id,
        court_type: lead.court_type ?? "pickleball",
        scope_type: lead.scope_type ?? "resurfacing",
        links: lead.links,
        notes: lead.description ? `From the lead: ${lead.description}` : "",
        salesperson_id: lead.salesperson_id ?? "",
      }
    : {};
  const loaded = e && {
    ...formFrom({
      name: e.name,
      client: "",
      address: e.data.site_address,
      parcel_id: e.data.parcel_id,
      lat: e.data.lat,
      lng: e.data.lng,
      court_type: e.data.court_type,
      scope_type: e.data.scope_type,
      contract_amount: e.data.price,
      estimated_labor_rate: e.data.estimated_labor_rate,
      sales_tax_pct: e.data.sales_tax_pct,
      tasks: e.data.tasks.map(({ id, ...t }) => t),
      cost_lines: e.data.cost_lines.map(({ id, ...c }) => c),
    }),
    client_id: e.client_id,
    new_client: null,
    salesperson_id: e.salesperson_id ?? "",
    valid_days: String(e.valid_days),
    scope_text: e.data.scope_text,
    exclusions: e.data.exclusions,
    links: e.data.links,
    notes: e.data.notes,
    note: "",
  };

  return (
    <ScopeEditor
      draftKey={`cf.draft.estimate.${estimateId ?? (leadId ? `lead-${leadId}` : "new")}`}
      load={e ? () => Promise.resolve(loaded) : undefined}
      blank={() => {
        const b = blankEstimate(fromLead);
        return lead ? { ...b, tasks: starterTasks(b.court_type, b.scope_type) } : b; // starter tasks for the lead's court and scope
      }}
      title={e ? `Edit ${e.number}` : lead ? "New estimate from a lead" : "New estimate"}
      backLabel={e ? "Back to estimate" : "All estimates"}
      submitLabel={e ? `Save as v${nextV}` : "Save estimate (v1)"}
      labels={{
        panel: "Estimate",
        name: "Estimate name",
        namePlaceholder: "e.g. Harbor Pointe – 2 pickleball courts",
        price: "Proposal price (what the client pays)",
        priceRow: "Proposal price",
        where: "Job site",
        summary: "Cost and margin",
      }}
      clientField={(f, set) => (
        <ClientPicker
          clientId={f.client_id}
          newClient={f.new_client}
          onChange={(cid, nc) => {
            set("client_id", cid);
            set("new_client", nc);
          }}
        />
      )}
      extraTop={(f, set) => (
        <div className="grid extra-top">
          <label>
            Salesperson
            <select value={f.salesperson_id ?? ""} onChange={(ev) => set("salesperson_id", ev.target.value)}>
              <option value="">None</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Proposal good for
            <span className="affix">
              <input type="number" inputMode="numeric" min="1" max="365" value={f.valid_days} onChange={(ev) => set("valid_days", ev.target.value)} placeholder="30" />
              <span aria-hidden="true">days</span>
            </span>
          </label>
        </div>
      )}
      extraPanels={(f, set) => (
        <section className="panel">
          <h3>Proposal and plans</h3>
          <div className="stack">
            <label>
              Scope of work <span className="optional">(prints on the proposal)</span>
              <textarea rows={4} value={f.scope_text} onChange={(ev) => set("scope_text", ev.target.value)} placeholder="Build two new pickleball courts with acrylic surfacing, lines, posts and nets…" />
            </label>
            <label>
              Not included <span className="optional">(prints on the proposal)</span>
              <textarea rows={2} value={f.exclusions} onChange={(ev) => set("exclusions", ev.target.value)} placeholder="Permits, lighting, landscaping repair…" />
            </label>
            <LinksField id="est-links" value={f.links} onChange={(v) => set("links", v)} />
            <label>
              Internal notes <span className="optional">(never on the proposal)</span>
              <textarea rows={3} value={f.notes} onChange={(ev) => set("notes", ev.target.value)} />
            </label>
          </div>
        </section>
      )}
      footer={(f, set) => (
        <label className="version-note">
          {e ? `What changed in v${nextV}?` : "Note (optional)"}
          <input value={f.note} onChange={(ev) => set("note", ev.target.value)} placeholder={e ? "e.g. Dropped lighting, fence to 10 ft" : ""} maxLength={1000} />
        </label>
      )}
      validate={(f) => {
        if (!f.client_id) return { message: "Choose a client at the top, or pick “+ New client”." };
        if (f.client_id === "__new" && !f.new_client?.name?.trim()) return { message: "Give the new client a name (at the top)." };
        return null;
      }}
      submit={async (f, body) => {
        const client_id = await saveClient(f.client_id, f.new_client);
        const data = {
          site_address: body.address,
          parcel_id: body.parcel_id,
          lat: body.lat,
          lng: body.lng,
          court_type: body.court_type,
          scope_type: body.scope_type,
          price: body.contract_amount,
          estimated_labor_rate: body.estimated_labor_rate,
          sales_tax_pct: body.sales_tax_pct,
          tasks: body.tasks.map(({ id, ...t }) => t),
          cost_lines: body.cost_lines.map(({ id, ...c }) => c),
          scope_text: f.scope_text,
          exclusions: f.exclusions,
          links: f.links,
          notes: f.notes,
        };
        const payload = {
          client_id,
          name: body.name,
          salesperson_id: f.salesperson_id || (e ? "" : null),
          valid_days: num(f.valid_days) || null,
          data,
          note: f.note ?? "",
          ...(leadId && !e ? { lead_id: leadId } : {}),
        };
        const saved = e
          ? await api(`/api/estimates/${e.id}/versions`, { method: "POST", body: payload })
          : await api("/api/estimates", { method: "POST", body: payload });
        return saved.id;
      }}
      onDone={onDone}
      onCancel={onCancel}
    />
  );
}
