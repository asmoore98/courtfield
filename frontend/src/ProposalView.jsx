// The proposal the client gets: who we are, what we'll build, what it costs.
// Never shows our costs, markups or margins (the server doesn't send them).
// "Print / Save as PDF" uses the browser's print dialog; pick "Save as PDF".
import { useEffect } from "react";
import { COURT_LABEL, SCOPE_LABEL, fmtDate, useApi } from "./bits";

const price = (n) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export default function ProposalView({ id, onBack }) {
  const { data: p, error } = useApi(`/api/estimates/${id}/proposal`);
  // The PDF is named after the page title, so name it after the proposal.
  useEffect(() => {
    if (!p) return;
    const before = document.title;
    document.title = `${p.number} ${p.client.name} proposal`;
    return () => {
      document.title = before;
    };
  }, [p]);
  if (error && !p) return <p className="empty">Couldn't load the proposal: {error}</p>;
  if (!p) return <p className="empty">Loading proposal…</p>;
  const c = p.company;
  const hasHeader = c.address || c.phone || c.email || c.license;

  return (
    <div className="proposal-wrap">
      <div className="proposal-tools no-print">
        <button className="link back" onClick={onBack}>
          Back to estimate
        </button>
        <button className="btn" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
        {!hasHeader && <p className="help">The company details at the top are set by the GM under Settings.</p>}
      </div>

      <article className="proposal">
        <header className="pr-head">
          <div className="pr-company">
            {c.logo_url && <img src={c.logo_url} alt="" className="pr-logo" />}
            <h1>{c.name}</h1>
            {c.address && <p>{c.address}</p>}
            {(c.phone || c.email) && <p>{[c.phone, c.email].filter(Boolean).join(" · ")}</p>}
            {c.license && <p>License {c.license}</p>}
          </div>
          <div className="pr-meta">
            <h2>Proposal</h2>
            <p>
              <b>{p.number}</b>
              {p.version > 1 && ` (revision ${p.version})`}
            </p>
            <p>Date: {fmtDate(p.issued)}</p>
            <p>Good until: {fmtDate(p.valid_until)}</p>
          </div>
        </header>

        <section className="pr-parties">
          <div>
            <h3>Prepared for</h3>
            <p>
              <b>{p.client.name}</b>
            </p>
            {p.client.contact_name && <p>Attn: {p.client.contact_name}</p>}
            {p.client.billing_address && <p>{p.client.billing_address}</p>}
            {(p.client.phone || p.client.email) && <p>{[p.client.phone, p.client.email].filter(Boolean).join(" · ")}</p>}
          </div>
          <div>
            <h3>Project</h3>
            <p>
              <b>{p.name}</b>
            </p>
            {p.site_address && <p>{p.site_address}</p>}
            {p.parcel_id && <p>Parcel {p.parcel_id}</p>}
            <p>
              {COURT_LABEL[p.court_type]}, {SCOPE_LABEL[p.scope_type].toLowerCase()}
            </p>
          </div>
        </section>

        <section>
          <h3>Scope of work</h3>
          {p.scope_text && <p className="pre">{p.scope_text}</p>}
          {p.work_items.length > 0 && (
            <>
              <p>The work includes:</p>
              <ul>
                {p.work_items.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </>
          )}
        </section>

        {p.exclusions && (
          <section>
            <h3>Not included</h3>
            <p className="pre">{p.exclusions}</p>
          </section>
        )}

        <section className="pr-price">
          <h3>Price</h3>
          <p className="pr-total">{price(p.price)}</p>
          <p className="pr-small">
            This proposal is good for {p.valid_days} days, until {fmtDate(p.valid_until)}.
          </p>
        </section>

        {c.terms && (
          <section>
            <h3>Terms</h3>
            <p className="pre pr-small">{c.terms}</p>
          </section>
        )}

        <section className="pr-sign">
          <h3>Acceptance</h3>
          <p className="pr-small">Signing below accepts this proposal, its scope, price and terms.</p>
          <div className="pr-sign-grid">
            <div>
              <span className="pr-line" />
              <span>Client signature</span>
            </div>
            <div>
              <span className="pr-line" />
              <span>Date</span>
            </div>
            <div>
              <span className="pr-line" />
              <span>Printed name and title</span>
            </div>
            <div>
              <span className="pr-line" />
              <span>For {c.name}</span>
            </div>
          </div>
        </section>
      </article>
    </div>
  );
}

