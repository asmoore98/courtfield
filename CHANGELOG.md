# Courtfield change log

Each batch of changes gets an entry: what changed, where, why, and how to undo it. Newest first.

To undo a whole batch after it's merged: open its pull request on GitHub and click **Revert**. To keep only part of a batch, use the "Files" list below to see where each piece lives.

---

## v0.5.1 — Batch 3.1: Lead fixes, checklist by court type, photos, hand-off to estimating

**Date:** November 3, 2026 · **Branch:** `drew/batch3.1-lead-fixes` · **By:** Drew Moore

Fixes from going through a lead and an estimate on the phone, photos straight from the camera roll, and a clean hand-off from sales to the estimators.

### What changed

| Change | Why | Where |
|---|---|---|
| **Addresses in parts:** street, city, state (FL to start) and ZIP on leads, clients (billing), estimates and jobs. Phones and browsers can fill them in. The one-line address is still built for lists, the map pin and the proposal. Old one-line addresses are split the first time they're edited | Neater, and the address carries from lead to estimate to job without retyping | `addresses.py`, `AddressFields` in `bits.jsx` |
| **"Other" opens a box** to say what it is, on every choice that has Other (surface, net type, goal type, fence height…) | "Other" on its own tells the estimator nothing | `checklists.py` (`_with_other_boxes`), `Checklist.jsx` |
| **"+ Add a note"** under every checklist question. Notes show on the lead, in the estimator's view, and in the history | Room for the details a yes/no can't hold | `Checklist.jsx`, `tidy()` in `checklists.py` |
| **Questions follow the court type:** net and post questions only for tennis, pickleball and multi-court; a **Basketball goals** section only for basketball and multi-court. With no court type picked yet, everything shows. Basketball estimates no longer start with net tasks | No questions that don't apply | `checklists.py`, `starterTasks` in `JobEditor.jsx` |
| **Replace or install new:** goals, net posts, fence and windscreen ask whether it's replacing what's there or new. Replace adds the tear-out to the estimate (goal removal, post removal, fence removal, windscreen removal) and asks follow-ups (old goals in concrete? post sleeves OK?). Fence asks repair, replace or new | Tearing out costs more; the bid has to show it | `checklists.py`, `tasksFromChecklist` in `Checklist.jsx` |
| Four new starter tasks: Net post removal, Basketball goal removal, Fence removal, Windscreen removal | For the tear-out work | `library_starter.py` |
| **Photos on leads and estimates:** Add photos picks from the camera roll (or takes one). Each is shrunk on the phone first (about 0.3 MB) so it uploads fast. On a new lead they upload when it's saved. Tap one to see it full size, save it, or remove it (with a reason; it's kept and in the history). The estimate shows the lead's photos. Kept in the app's database for now; ready to move to the company Google Drive later | Sales shouldn't have to upload to Drive and paste links | `routers/photos.py`, `Photos.jsx`, `models.py` (`Photo`) |
| **Open Google Drive** button next to every link box. It opens the company Drive folder set in **Settings → Google Drive** (or Drive's home page), then you copy the share link and paste it | Faster than hunting for Drive in another app | `LinksField` in `bits.jsx`, `SettingsView.jsx` |
| **Send to estimating:** sales taps it on the lead when it's wrapped up (unanswered checklist questions are listed first). The Estimates tab shows **New leads to be estimated**, oldest first, with how much of the checklist is done. The Leads tab shows which leads haven't been sent. Sales can take a lead back until an estimate is started | Sales and estimating are different people | `routers/leads.py`, `LeadsView.jsx`, `EstimatesView.jsx` |
| **Enter doesn't save** a lead, estimate or client any more; it moves to the next box. Saving takes the Save button | Every accidental Enter was making a new estimate version | `noEnterSubmit` in `bits.jsx` |
| **The starter task list is there from the start:** a company's library fills itself the first time it's opened | The phone showed an empty list until someone tapped Load | `routers/library.py` |
| **Our cost vs. customer price** on every crew task, in two labeled boxes. Price per unit (or per hour) and markup are in the customer box; crew hours and cost per hour in ours. The production rate hides behind "Work out the hours from a production rate" until it's used | Nobody could tell which numbers were ours and which were the customer's | `TaskRow` in `JobEditor.jsx` |
| **What sales said shows on the task** the checklist added ("What's there now? Light brush · How much of the land needs clearing: 0.75 acres") | The estimator sees the reason next to the work | `tasksFromChecklist` in `Checklist.jsx` |
| Checklist tasks land **in work order** (site work, drainage, the slab, prep, coatings, lines…) | The slab was showing up after the color coats | `Checklist.jsx` |
| **Clearing by the acre** in three levels: grass, light brush, heavy woods. Rough and fine grading by the acre too. The new-construction checklist asks what's there and **how much of the land needs clearing and grading** (court area or the whole lot) | That's how clearing is priced, and the lot can be far bigger than the courts | `library_starter.py`, `checklists.py` |
| **Lighting:** "About how far is the nearest electrical service from the court?" | Power a quarter mile away is a big part of the price | `checklists.py` |
| **Buildings** (concession stand, restrooms, storage, pavilion, office): have plans → get the plans and their permit status. No plans → size, construction, roof, matching, location, restroom fixtures, concession food and equipment, storage, pavilion, water, sewer and power distances, A/C, extras, budget, and whether we get plans drawn. Adds Building construction and, without plans, Building plans and engineering | Plans cost money; ask everything once | `checklists.py`, `library_starter.py` |
| **Permit and city fees:** a Fee line passes through at cost, with no markup and no whole-job markup. Adding a permits task adds a fee line for it. The proposal lists each fee as included in the price | The customer sees we've covered the fees, not that they'll owe them on top | `routers/estimates.py`, `JobEditor.jsx`, `ProposalView.jsx` |
| **Notes at the bottom of the estimate:** internal notes (never printed) and notes for the customer (printed, marked in orange) | One place for extras, with the two kept apart | `EstimatesView.jsx` |
| **Read before it's sent:** "Mark sent" and "Re-send" show everything the customer will read (price, fees, scope, work, exclusions, customer notes) and need a tick. The server refuses a send without it | A note meant for the office never goes to the customer | `SendReview` in `EstimatesView.jsx`, `routers/estimates.py` |
| "Flood test" is now "Flood test (find low spots)": flooding the court to find birdbaths before coating | Plain names | `library_starter.py` |
| **People × hours:** a crew task asks how many people and how many hours to finish (4 people for 8 hours = 32 labor hours). Labor hours are what's compared with the time clocked on the job. Saved on the estimate and the job | "Crew hours" read as clock hours, not everyone's hours together | `TaskRow` in `JobEditor.jsx`, `JobTask.crew_size` |
| **Materials on the task:** "+ Add material", "+ Add equipment" and "+ Other cost" right on the task. Each task shows its total: our cost, customer price and margin with its materials in. The bottom list is for whole-job costs. Every line has a clear **Remove** button, and a line added by mistake and left blank is dropped on save | Base rock showed a 2,000% markup because the rock wasn't on the task | `JobEditor.jsx` |
| **Customer price stands out** on every task: the labor price in big blue in the customer box, and the task total at the bottom of the card | See what each task charges without hunting | `JobEditor.jsx`, `styles.css` |
| **+ between the arrows** adds a task right below that one | No scrolling to the bottom and back | `JobEditor.jsx` |
| **Court slab in its parts:** forms, vapor barrier, rebar and mesh, pour and place, finish. Post-tensioned is gone; the checklist asks Asphalt or Concrete. **Sidewalks and flatwork** has its own question. Buildings get their own type of work, with **Building slab and footings** | A slab is bid by its parts; a court finish isn't a building pad | `library_starter.py`, `checklists.py` |
| **Buildings:** right after which buildings, it asks one building or separate (and how many). One building gets length and width; separate ones get each building's size. Men's and women's restrooms ask toilets in each and urinals in the men's | Two buildings is a very different job from one | `checklists.py` |
| Typing ".5" keeps the decimal (it shows 0.5) | It was turning into 5 | `NumInput.jsx` |
| The production-rate box no longer vanishes when it's cleared to retype | Backspacing one too many lost the box | `JobEditor.jsx` |
| Tests: 7 new (court types, Other and notes, addresses through to the job, photos and who can see or remove them, the Drive link, fees at cost and on the proposal, the read-before-send check, the hand-off, notes on tasks) | Keep it working | `tests/test_units_checklist.py`, `tests/test_library.py`, `tests/test_estimates.py` |

### Database change

Migration `c7e19a4d2b55`: street, city, state and ZIP columns on `jobs`, `leads` and `clients`; `drive_folder_url` on `companies`; a new `photos` table; `sent_at` and `sent_by_id` on `leads`; a new "fee" kind of cost line; `crew_size` on job tasks; a "building" type of work. Nothing existing changes. Tested up, down and up on Postgres with data.

**Storage:** photos live in the Postgres database for now. Check the Render database plan's storage; at about 0.3 MB a photo, 1 GB holds roughly 3,000 photos. When the company Google Drive is connected, they move there.

### After it goes live

1. GM: **Library → Tasks → Load the starter list** again to add the new tasks (tear-outs, clearing levels, buildings). Tasks already there are skipped. If the library was empty, it fills itself.
2. GM: set prices per acre on the clearing levels and grading (Library → tap the task).
3. GM: **Settings → Google Drive**: paste the company's Drive folder link.

### How to undo

- **Everything:** revert this pull request on GitHub. To remove the new columns and the photos table, run `alembic downgrade b41d7e2c9a10` from the Render Shell (deletes any photos added).

---

## v0.5.0 — Batch 3: Task library, per-task rates, subs, built prices, site checklist

**Date:** October 29, 2026 · **Branch:** `drew/batch3-library` · **By:** Drew Moore

Estimates now price themselves. Each task has what it costs us and what we charge; materials, equipment, subs and other costs get a markup; the proposal price adds itself up as you go, with an adjustment (and a reason) if you want to round it.

Most work is measured, not guessed: a task is priced by the SF, LF or each, and its crew hours come from the quantity and how fast a person does it. The court size is entered once and fills in the area work. Sales fills in a site checklist on the lead, and the estimate starts from what they found.

### What changed

| Change | Why | Where |
|---|---|---|
| **Library tab** (GM, estimator, PM) with three parts: **Tasks**, **Subs**, **Rates & markups** | One place for the names and numbers everyone estimates with | `LibraryView.jsx`, `routers/library.py` |
| **Task library:** each task has one official name plus the other names people use for the *same* work, a type of work, whether a crew or a sub usually does it, and its cost and charge rates. Only the GM adds or edits tasks. A name can only belong to one task, so "power wash" can't end up on two different tasks. Tasks are turned off, never deleted. Every edit is in the task's history | Definitive names so hours and costs compare job to job | `models.py` (`TaskTemplate`), `routers/library.py` |
| **Starter list:** 57 court, site, drainage, paving, fence, lighting and turf tasks with their other names, all set to our own crew (any can be switched to a sub). Different work stays separate (Broom clean vs. Pressure wash). Rates start blank and use the company defaults until set | A curated list to start from | `library_starter.py`; GM can load it from the Library tab |
| **Task search on estimates and jobs:** type any part of the name, any order ("cleaning court", "grade", "power"). It lists every match and never picks for you. Not in the library? Use it just on this estimate (marked "Not in the library"), or the GM can add it to the library right there | No more "clean court" vs. "court cleaning" | `Picker.jsx`, `search.js`, `JobEditor.jsx` |
| **Per-task rates:** every crew task has its own cost / hr and charge / hr, filled from the library. The single "labor rate" box is gone. Older jobs and estimates keep working: their tasks take the old single rate | Grading with equipment isn't priced like a guy with a rake | `JobEditor.jsx`, `costing.py`, `models.py` (`JobTask`) |
| **Sub tasks:** switch any task to **Sub**, pick the sub (or add a new one right there), enter their price and a link to their quote. Tap to see the sub's phone, email and documents without leaving the estimate | Subs belong on the task they do | `JobEditor.jsx` |
| **Subs list:** company, trade, contact, phone, email, notes, documents. Each sub's page shows the estimates and jobs they're on with their price. GM can turn a sub off | Click through to a sub's info and quote | `LibraryView.jsx`, `models.py` (`Subcontractor`) |
| **Equipment: Rental or In-house** on each equipment line | Not every machine is rented | `CostLine.in_house` |
| **Markups, all adjustable per estimate:** every material, equipment and other line has its own markup % (paint 7%, sealant 2%…), every sub has its own, and every crew task has a markup % tied to its charge rate (change either one). Anything left blank uses the estimate's default for its kind (materials are marked up with their tax). "Set every crew task to __%" does all labor at once. **Markup on the whole job** adds a % on top of everything. Company defaults live on Library → Rates & markups (GM) | Some jobs can carry more markup on certain things; others need it cut to win the job | `routers/estimates.py`, `JobEditor.jsx` |
| **Total markup over cost, profit margin and expected profit** shown under the price, with each kind's markup in the table. Our side only: never on the proposal or to Sales | See at a glance if we're marking up too high | `PriceTable` in `JobEditor.jsx` |
| **Price adds itself up:** the price section shows cost, markup and price for labor, materials, equipment, subs and other, then the subtotal, the whole-job markup, the adjustment and the proposal price. The server works out the price itself; it's never taken from the screen. An adjustment needs a reason, and it's written to the history | Figure out the price from the work instead of guessing first | `PriceTable` in `JobEditor.jsx`, `totals()` in `routers/estimates.py` |
| Opening an estimate saved before this batch carries its typed price over as an adjustment, so the price doesn't jump until someone sets the rates | Old estimates stay as they were | `carryOverPrice` in `EstimatesView.jsx` |
| Jobs made from estimates keep each task's rates, sub and price. On the job page, sub tasks say "Done by a sub" with the sub's price instead of an hours bar. Crew leads don't see sub tasks on the Field screen and never see sub prices | Crews don't clock in on a sub's work | `routers/estimates.py`, `OfficeView.jsx`, `FieldView.jsx` |
| New types of work: Site work, Paving & concrete, Turf, Drainage, Cleanup | New construction | `TaskType` |
| **Tasks measured by the unit:** each task is measured in hours, SF, SF per coat, LF, SY, CY, tons, each or lump sum. With a **production rate** (what one person does in an hour, e.g. 40 LF of crack fill; for things counted one at a time, the hours each takes) the crew hours work themselves out from the quantity. **Price per unit** (e.g. $1.40 / LF) is what we charge; left blank, it's hours × charge / hr. Markup works on either. The starter list comes with each task's unit (crack fill by LF, coatings by SF per coat, posts each…); production rates and prices are the company's to set | Price the way the work is sold, and stop guessing hours | `quantities.py`, `qty.js`, `JobEditor.jsx`, `library_starter.py` |
| **Court size, entered once on the estimate:** number of courts × length × width, or a measured total for odd shapes, plus a **paintable area** that's the same as the surface unless changed. Pressure wash and other surface work pick up the surface; resurfacer and color pick up the paintable area × their coats; line painting picks up the number of courts. Type a quantity on any task to override it. Common sizes (tennis, pickleball, basketball) are one tap | Put the area in once and the paint multiplies itself | `CourtSizeFields` in `Checklist.jsx`, `EstimateData.court` |
| **Materials worked out from the area:** a material line can follow the paintable or surface area with its coats and coverage (SF one pail covers per coat). Pails round up. Type a quantity to override it | 13,000 SF × 2 coats ÷ 1,200 SF a pail = 22 pails, no calculator | `JobEditor.jsx`, `sales_schemas.py` |
| **Site checklist on the lead:** sales fills it in on site, by scope (resurfacing, repair, new construction): court count and size, surface, cracks (how many feet, how wide), low spots, peeling, mildew, lines and colors, nets (what kind, how many), posts (how many, sleeves OK?), windscreen, fence, goals, lighting, water, power, truck access, HOA rules, timeline, photos. Follow-up questions only show after a yes. The lead page and the lead list show how much is answered and what's missing. Every change is in the lead's history, answer by answer | Sales is on site; the bid is only as good as what they bring back | `checklists.py`, `Checklist.jsx`, `LeadsView.jsx`, `routers/leads.py` |
| **Estimates start from the checklist:** the court size comes over; a yes adds its task with the quantity filled in (140 LF of crack fill, 4 posts), and a no takes it off the starter list. The estimator sees what sales found at the top of the form | Enter it once, on site | `tasksFromChecklist` in `Checklist.jsx`, `EstimatesView.jsx` |
| The job page and the crew's Field screen show how much work each task is (120 LF, 13,000 SF × 2 coats). Crew leads no longer receive any task rates or prices from the server (they weren't shown, but they were sent) | Crews see the work, never the money | `costing.py`, `routers/jobs.py`, `FieldView.jsx`, `OfficeView.jsx` |
| Tests: 10 new for the library, subs, pricing, per-line and whole-job markups, adjustments, Sales never seeing the breakdown, jobs from priced estimates, old single-rate jobs. 6 more for quantities, production rates, court size, materials from coverage, the checklist and its history, and crews not seeing money | Keep it working | `tests/test_library.py`, `tests/test_units_checklist.py` |

### Database change

Two migrations. `69c6e867ba75`: new tables `task_templates` and `subcontractors`; per-task `kind`, `cost_rate`, `charge_rate`, `sub_id`, `sub_price`, `sub_quote_link`, `template_id` on job tasks; `in_house` on cost lines; default rates and markups on `companies`; five new types of work. Existing jobs and tasks are untouched (their tasks keep using the job's old single rate). `b41d7e2c9a10`: `unit`, `quantity`, `coats`, `production_rate`, `unit_price` on job tasks and library tasks, and `survey` (the checklist) on leads; existing tasks become "hours", as they were. Both tested up, down and up on Postgres, including a database with existing jobs.

### After it goes live

1. GM: **Library → Tasks → Load the starter list**.
2. GM: **Library → Rates & markups**: set the default cost and charge per hour and the markups.
3. Set real rates on the tasks that differ from the default (grading, clearing, anything with equipment).
4. For the tasks you price by the unit, set the **production rate** and **price per unit** (Library → Tasks → tap a task). Start with the common ones: pressure wash, crack fill, resurfacer, color coat, line painting, nets, posts. Until a task has a production rate, its hours are typed on the estimate like before.
5. Go through the site checklist questions with sales and send back what to add, cut or reword.

### How to undo

- **Everything:** revert this pull request on GitHub. The new tables and columns stay, unused. To remove them, run `alembic downgrade 30a23cf6e287` from the Render Shell (deletes the task library and subs).

---

## v0.4.1 — Batch 2 fixes

**Date:** October 29, 2026 · **Branch:** `drew/batch2-fixes` · **By:** Drew Moore

| Change | Why | Where |
|---|---|---|
| **Jobs tab: "Jobs ready to be scheduled"** box at the top lists every won estimate that isn't a job yet, each with a Create job button. The Jobs tab also shows a green count of how many are waiting | A won job can't get forgotten because it wasn't clear it was ready | `OfficeView.jsx`, `App.jsx` |
| **Leads follow their estimates:** a lead now shows Won, Lost, No bid or Estimate expired once its estimate does. Leads list filters: Open, Estimate sent, Won, Lost / dropped, All. Each estimate status change is written to the lead's history too | See the result right on the lead | `routers/leads.py`, `routers/estimates.py`, `LeadsView.jsx` |
| Lead section renamed "Details" (was "What they want") | Clearer | `LeadsView.jsx`, `routers/leads.py` |
| Street address on job and estimate forms lets the phone suggest addresses as you type, the same as the lead form | Suggestions showed on leads only | `JobEditor.jsx` |
| Note: the "Details" rename and the won-estimates box were meant to go out with Batch 2 but missed that push; they're in this one | | |

No database change.

**How to undo:** revert this pull request on GitHub.

---

## v0.4.0 — Batch 2: Leads, estimates, clients, proposals

**Date:** October 29, 2026 · **Branch:** `drew/batch2-estimates-clients` · **By:** Drew Moore

The flow is now **Lead → Estimate → Job**. Sales brings in a lead, an estimator prices it, the estimate goes out as a proposal, and a won estimate becomes a job with one tap. The GM can still start a job with no estimate (callbacks, small patches).

### What changed

| Change | Why | Where |
|---|---|---|
| **Clients** tab: name, contact, phone, email, billing address, notes, plans & documents links. Each client shows its leads, estimates and jobs. Clients are never deleted; the GM can turn one off | One place per customer, tied to everything done for them | `ClientsView.jsx`, `routers/clients.py` |
| **Leads** tab: client (pick a returning one or "+ New client"), project, site address, parcel, court type/scope if known, description, Google Drive links, bid due date, salesperson. Statuses New → Being estimated → Estimate sent, or Dropped (with a reason). "Start the estimate" opens an estimate filled in from the lead | Sales hands the estimator everything in one place | `LeadsView.jsx`, `routers/leads.py` |
| **Estimates** tab: numbered E-2026-001…; statuses Draft, Sent, Won, Lost, No bid, Expired; filter by status | Estimates are separate from jobs, so lost bids don't clutter the job list and are kept to learn from | `EstimatesView.jsx`, `routers/estimates.py` |
| **Locked versions:** every save makes the next version (v1, v2…). Old versions can't be changed; pick any version from the dropdown to see it. Only the GM can remove a version, with a reason, and it stays on record as removed | A trail of every change | same |
| **History** on every client, lead and estimate: who did what, when, and why | People can be sneaky; this keeps a trail | `app/activity.py`, `Activity` table |
| **Follow-ups:** "Needs follow-up" list at the top of Estimates when a sent estimate has gone 15 days without a logged follow-up. Expired automatically after 30 days (adjustable per estimate and in Settings). "Log a follow-up" records who you talked to | Don't let bids go cold | `routers/estimates.py` |
| Lost and No bid require a reason | Learn what we're high on or missing | same |
| **Printable proposal:** company header, client, project, scope of work, work included, not included, price, terms, signature lines. "Print / Save as PDF". Never shows costs, markups, margins or internal notes, whoever opens it | Something to send the client | `ProposalView.jsx` |
| **Create job from a won estimate:** site, tasks, hours and cost lines carry over; the job is linked to the client | No retyping | `routers/estimates.py`, `routers/jobs.py` |
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
