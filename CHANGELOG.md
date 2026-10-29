# Courtfield change log

Each batch of changes gets an entry: what changed, where, why, and how to undo it. Newest first.

To undo a whole batch after it's merged: open its pull request on GitHub and click **Revert**. To keep only part of a batch, use the "Files" list below to see where each piece lives.

---

## v0.4.0 — Batch 2: Leads, estimates, clients, proposals

**Date:** October 29, 2026 · **Branch:** `drew/batch2-estimates-clients` · **By:** Drew Moore

The flow is now **Lead → Estimate → Job**. Sales brings in a lead, an estimator prices it, the estimate goes out as a proposal, and a won estimate becomes a job with one tap. The GM can still start a job with no estimate (callbacks, small patches).

### What changed

| Change | Why | Where |
|---|---|---|
| **Clients** tab: name, contact, phone, email, billing address, notes, plans & documents links. Each client shows its leads, estimates and jobs. Clients are never deleted; the GM can turn one off | One place per customer, tied to everything done for them | `ClientsView.jsx`, `routers/clients.py` |
| **Leads** tab: client (pick a returning one or "+ New client"), project, site address, parcel, court type/scope if known, description, Google Drive links, bid due date, salesperson. A lead's "Details" section holds the description. Statuses New → Being estimated → Estimate sent, or Dropped (with a reason). "Start the estimate" opens an estimate filled in from the lead | Sales hands the estimator everything in one place | `LeadsView.jsx`, `routers/leads.py` |
| **Estimates** tab: numbered E-2026-001…; statuses Draft, Sent, Won, Lost, No bid, Expired; filter by status | Estimates are separate from jobs, so lost bids don't clutter the job list and are kept to learn from | `EstimatesView.jsx`, `routers/estimates.py` |
| **Locked versions:** every save makes the next version (v1, v2…). Old versions can't be changed; pick any version from the dropdown to see it. Only the GM can remove a version, with a reason, and it stays on record as removed | A trail of every change | same |
| **History** on every client, lead and estimate: who did what, when, and why | People can be sneaky; this keeps a trail | `app/activity.py`, `Activity` table |
| **Follow-ups:** "Needs follow-up" list at the top of Estimates when a sent estimate has gone 15 days without a logged follow-up. Expired automatically after 30 days (adjustable per estimate and in Settings). "Log a follow-up" records who you talked to | Don't let bids go cold | `routers/estimates.py` |
| Lost and No bid require a reason | Learn what we're high on or missing | same |
| **Printable proposal:** company header, client, project, scope of work, work included, not included, price, terms, signature lines. "Print / Save as PDF". Never shows costs, markups, margins or internal notes, whoever opens it | Something to send the client | `ProposalView.jsx` |
| **Create job from a won estimate:** site, tasks, hours and cost lines carry over; the job is linked to the client | No retyping | `routers/estimates.py`, `routers/jobs.py` |
| **Jobs tab shows "Won, ready to become jobs"** at the top: every won estimate without a job yet, each with a Create job button | Marking an estimate won didn't put anything on the Jobs tab | `OfficeView.jsx` |
| **Settings** tab (GM): proposal header (name, address, phone, email, license, logo link), standard terms, default days an estimate is good for | Placeholder until the real letterhead is known | `SettingsView.jsx`, `routers/reports.py` |
| **New roles: Sales and PM.** Sales: leads, clients, their own estimates' status and price, proposals, follow-ups; never costs or margins, never other salespeople's leads/estimates. PM: same as estimator for now | Sales enters leads; roles get tightened later | `models.py`, `auth.py`, `TeamView.jsx` |
| Only the GM can start a job without an estimate ("New job without an estimate" on Jobs). Estimators and PMs make jobs from won estimates | Jobs come from estimates | `routers/jobs.py`, `OfficeView.jsx` |
| Job and estimate forms share one form (tasks, cost lines, location, drafts, highlighting from Batch 1) | Fixes in one place apply to both | `JobEditor.jsx` (`ScopeEditor`) |
| Tests: 9 new for clients, leads, estimates, versions, follow-ups, expiry, proposals, sales never seeing costs | Keep it working | `tests/test_estimates.py`; existing tests updated for GM-only direct jobs |

### Database change

Migration `30a23cf6e287`: new tables `clients`, `leads`, `estimates`, `estimate_versions`, `activity`; proposal settings on `companies`; `jobs.client_id`; roles `sales` and `pm`. Existing jobs are untouched (they just have no client record linked). Tested up, down and up on Postgres, including a database with existing jobs. Render applies it on deploy.

### Placeholders and known limits

- **Plans & documents** are links (Google Drive, Dropbox) pasted one per line, not uploads. Real uploads, and insurance certs, come in a later batch.
- **Follow-up reminders** show inside the app only. Email or text alerts need a sending service.
- **Proposal header** fields are placeholders until we know what goes there.
- **Markups and charge rates** come in Batch 3; for now the proposal price is typed in.
- **Sales and PM permissions** are first passes; we'll tighten them when all the roles are sorted out.

### How to undo

- **Everything:** revert this batch's pull request on GitHub. The new tables stay in the database, unused. To remove them too, run `alembic downgrade 92a2e076f67e` from the Render Shell (this deletes all clients, leads and estimates).
- **Just GM-only direct jobs:** in `backend/app/auth.py`, set `CREATES_JOBS = {Role.gm, Role.estimator, Role.pm}`.

---

## v0.3.0 — Batch 1: New job screen fixes

**Date:** October 29, 2026 · **Branch:** `drew/batch1-quick-fixes` · **By:** Drew Moore

### What changed

| Change | Why | Where |
|---|---|---|
| Money and quantity boxes show commas as you type (65000 → 65,000) | Easier to read and check big numbers | New `frontend/src/NumInput.jsx`; used in `JobEditor.jsx` |
| Labor rate shows cents in the summary ($25.50/hr, not $26/hr) | The rounded rate didn't match what was entered | `JobEditor.jsx` |
| When a task or cost line is missing a name, that row is outlined in red, the screen scrolls to it, and the cursor goes into it. The message names the line and its type ("Line 3 (Rental) needs a name") | Hard to tell which line the error meant | `JobEditor.jsx`, `styles.css` |
| On phones, each cost line is its own card with a colored edge by type (blue material, orange rental, green sub) and labels on every box (Qty, Unit, Cost per unit, For task, Line total) | Lines ran together and boxes had no labels | `JobEditor.jsx`, `styles.css` |
| Unsaved work on the job form is kept on the device. Switching tabs and coming back reopens the form with everything filled in; a note says it picked up unsaved work, with "Start over" to clear it. Drafts clear on save and on sign-out | Tapping another tab lost everything typed | `JobEditor.jsx`, `OfficeView.jsx`, `App.jsx`, `api.js` |
| Job location section reworked: street address and new **Parcel ID** live here, plus a **Find this address** button that sets the map pin from the address. "Check it on the map" opens the pin in Google Maps. Location messages show next to the buttons instead of at the bottom of the page | Only GPS or typed coordinates worked; new construction lots often have a parcel ID but no address | `JobEditor.jsx`, `styles.css` |
| Parcel ID saved on jobs (optional, up to 60 characters) | See above | `backend/app/models.py`, `schemas.py`, migration `92a2e076f67e_job_parcel_id.py`, `demoServer.js` |
| Address lookup service: `GET /api/geocode?address=…` (GM and estimator only) using the free U.S. Census geocoder, no account or key | Powers "Find this address" | New `backend/app/routers/geocode.py`, `main.py` |
| Tests for parcel ID and the address lookup | Keep them working | New `backend/tests/test_job_location.py` |

### Database change

Adds one column, `jobs.parcel_id` (text, empty by default). Render applies it automatically on deploy. Existing jobs get an empty parcel ID; nothing else is touched.

### Known limits

- The Census lookup only knows addresses that existed at its last update, so brand-new lots may come back "not found." Use the parcel ID plus "Use my current location" on site, or type the coordinates.
- Drafts live on the device they were typed on. Starting a job on the phone and finishing it on the computer still needs a save in between.

### How to undo

- **Everything:** revert this batch's pull request on GitHub. The parcel ID column stays in the database but is unused (harmless). To remove it too, run `alembic downgrade de86e4c5fba4` from the Render Shell.
- **Just the draft saving:** in `JobEditor.jsx`, remove the "Keep a copy of unsaved work" effect and the `restored` banner; in `OfficeView.jsx`, go back to `useState({ view: "list" })`.
- **Just the commas:** swap `<NumInput … />` back to `<input type="number" … />` in `JobEditor.jsx`.
