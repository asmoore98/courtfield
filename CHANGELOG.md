# Courtfield change log

Each batch of changes gets an entry: what changed, where, why, and how to undo it. Newest first.

To undo a whole batch after it's merged: open its pull request on GitHub and click **Revert**. To keep only part of a batch, use the "Files" list below to see where each piece lives.

---

## v0.7.0 — Batch 5: Built-up task prices, settings, suggestion box, phone menu, dark mode

**Date:** November 5, 2026 · **Branch:** `drew/batch5-pricing` · **By:** Drew Moore

The framework for pricing tasks from their parts (real prices come later, once the company's numbers are in), a Settings page for everyone with a suggestion box, and a cleaner look on phones.

### What changed

| Change | Why | Where |
|---|---|---|
| **Two ways to price a crew task** on an estimate: **Built up** (the labor at its rate plus each material, machine or other line with its markup; the default, and how every saved estimate already works) or **By the unit, all in** (one price per acre, ton, SF… covers everything; the task's materials and machine time are our cost inside it, and its markup is over all of it) | "Some tasks are simply priced by the unit; others are built up. The estimator picks per task" | `totals()` in `routers/estimates.py`, `estimateOf()` and `TaskRow` in `JobEditor.jsx` |
| **One markup for a built-up task:** "Markup on all of it" sets the labor and every line on that task in one go | Price the whole task, not each piece | `JobEditor.jsx` |
| **Price breakdown** gets a "Priced by the unit, all in" row, so labor and materials show their own markups | An all-in price was showing as a huge labor markup | `PriceTable` in `JobEditor.jsx` |
| **Quantities from a size:** a task measured in SF, SY, CY or tons can be worked out from length × width (× depth for CY and tons, with tons per CY, 1.4 to start). E.g. 120 × 60 ft × 4 in = 88.9 CY = 124.4 tons | Base rock and fill by length × width × depth | `size_quantity` in `quantities.py`, `qty.js`, `TaskRow` |
| **Lines that follow their task:** any line on a task can be "this much for every so many of the task": 1.05 ton of rock for every ton (waste), 1 truckload for every 20 ton, 1 pail for every 600 SF a coat. Per load or batch counts whole loads; materials are bought in whole units | Machine time per load, material per unit, worked out instead of typed | `per_task_qty`, line editor in `JobEditor.jsx` |
| **Court border band:** length × width is the playing area; "Border all around (ft)" makes the surfaced size (94 × 50 + 5 ft = 104 × 60). Tasks and paint can follow the surface, the playing area, the border band or the paintable area, so the border can be its own color | Many courts have a border | `CourtInfo` in `sales_schemas.py`, `Checklist.jsx`, `qty.js` |
| **Library tasks bring their parts:** the GM sets what a task brings onto an estimate (materials, machine time, fees, with amounts per unit of the task) and whether it's priced all in. Picking the task on an estimate adds those lines; they can be changed there. Starter tasks come with ballpark parts (base rock, resurfacer, color, lines, crack fill, concrete…); "Add the starter parts" fills them in for tasks that have none | Tasks bring their materials | `TaskTemplate.parts`, `routers/library.py`, `LibraryView.jsx`, `linesFromParts` in `library.js` |
| **Starter material list:** about 35 common items (acrylics, base rock, concrete, rebar, asphalt, fence, nets, rentals) with ballpark prices, each marked **Starter price** until someone fixes it or taps "It's right". Coatings carry how many SF one unit covers | Something to price from on day one; real prices replace them | `materials_starter.py`, `routers/materials.py`, `MaterialsView.jsx` |
| **Settings for everyone** (menu → Settings and suggestions): your name and phone, light or dark screen (or match the phone), normal or large text, which tab the app opens on, change your password (signs out your other devices), and where you're signed in with "sign out everywhere else". The GM's company settings are underneath | Nothing in Settings didn't feel legit | `routers/account.py`, `SettingsView.jsx`, `prefs.js` |
| **Suggestion box:** an idea or "something's wrong", where in the app, and screenshots. It's saved, listed for the GM (mark seen / done), and emailed with the screenshots attached once email is set up on the server (see below) | Direct feedback from the people using it | `Feedback` model, `routers/account.py`, `mailer.py`, `SettingsView.jsx` |
| **Phone menu:** on a phone the row of tabs is gone; the header shows the page you're on and a ⋯ button that opens the list of pages, Settings and Sign out. Red counts show on the button. Desktop keeps the tabs | Too cluttered and unprofessional on a phone | `App.jsx`, `styles.css` |
| **Dark mode** across the app, and small polish: header, menu, links and form fields | Easier on the eyes, looks finished | `styles.css` |
| Tests: pricing math (built up, all in, sizes, per-load machine time, border), library parts and starter materials, settings, the suggestion box and building the email. 119 pass | Keep it working | `tests/test_pricing.py`, `tests/test_account.py` |

### Database change

Migration `f4c2a9b7e3d1`: `all_in` and `parts` on task templates; `coverage_sf` and `starter_price` on price-list items; `phone` and `prefs` on people; new table `feedback`. Nothing existing changes: saved estimates price exactly as before (they're all "built up"). Tested up, down and up on Postgres with data.

### After it goes live

1. **Email for the suggestion box** (until this is set, suggestions are only saved in the app): in Render → the web service → **Environment**, add `SMTP_HOST` = `smtp.gmail.com`, `SMTP_PORT` = `587`, `SMTP_USER` = the Gmail address that sends, `SMTP_PASSWORD` = a Google **app password** for that account (Google Account → Security → 2-Step Verification → App passwords), and `FEEDBACK_TO` = where suggestions go. Save; Render restarts it.
2. GM: Materials → **Add the starter list** if the price list doesn't have it yet, then fix the prices as real quotes come in.
3. GM: Library → **Add the starter parts** to give the starter tasks their usual materials and machine time.

### How to undo

- **Everything:** revert this pull request on GitHub. To remove the columns and table, run `alembic downgrade d3a8f5c1e9b2` from the Render Shell (deletes suggestions and personal settings).

---

## v0.6.0 — Batch 4: Jobs out to the field

**Date:** November 5, 2026 · **Branch:** `drew/batch4-field` · **By:** Drew Moore

From Andrew's run-through and Drew's field test: a won estimate becomes a job with a start date and a crew and goes to the crew lead's phone. On site the crew lead clocks the crew in first, walks the site against the estimate, then runs the work: tasks marked done or partly done with photos, more material asked for and signed for, problems sent to the office, and the crew's hours checked and fixed with a full record.

### What changed

| Change | Why | Where |
|---|---|---|
| **Crews:** on the Team tab the GM sets up each crew lead's usual crew (Set up a crew → lead, optional name, who's on it). Someone is on one crew at a time; adding them to a crew moves them off their old one. When a job is sent out, picking the crew lead fills in their crew, and it can still be changed for that one job (someone off, a helper) | "Pre-create the crews and you just select the lead and his guys move along with him" | `Crew`, `CrewMember` models, `routers/crews.py`, `CrewSetup.jsx`, `TeamView.jsx`, `CrewForm.jsx` |
| **Schedule it:** on the Jobs tab, each won estimate has "Schedule it" (GM and PMs). Pick the start date, the crew lead and who's on the crew, and the job is made and sent out in one step. Estimators still make the job; the GM or a PM sends it out | Start dates and crews are set where the job is made | `CrewForm.jsx`, `OfficeView.jsx`, `routers/estimates.py` |
| **Who's on what, right now:** the GM's job page has an **On the clock now** panel: each task with who's on it and since when (e.g. Fence: Marco, Tyler · Color coats: Luis). In-progress jobs in the Jobs list show the same in one line. It refreshes every 30 seconds | "I should be able to see what task the workers are doing at any time… who is doing what" | `job_costing` in `costing.py` (`on_clock`), `OnTheClock` in `OfficeView.jsx` |
| **Crew and start date on the job page,** changeable by the GM and PMs. Every change is in the job's history | Crews and dates move | `routers/jobs.py` (`PUT /crew`), `OfficeView.jsx` |
| **Jobs tab grouped:** In progress, Scheduled (by start date), Not sent to a crew yet, and Complete folded away at the bottom. Each job shows its crew lead, crew size, start date and any problems from the site | See what's running, what's next and what's waiting | `OfficeView.jsx` |
| **Crew leads see only their own jobs,** server-side: other jobs don't list and don't open | "They should only see the job they're assigned to" | `load_job` and `list_jobs` in `routers/jobs.py` |
| **Field tab is a list of jobs,** not a dropdown: the crew lead's jobs (in progress first, then by start date). Tap one to open it | Clearer than "pick from the dropdown" | `JobPicker` in `FieldView.jsx` |
| **Clock in first:** "At the job?" with the job's crew already picked → **We're here: clock in**. That sets the site pin (if there isn't one), marks the job in progress and puts everyone on a "Site walk and setup" task, so nobody walks the site unpaid | "They will not be sitting there doing work for no reason if they're not getting paid" | `OnSite` in `FieldView.jsx`, `POST /api/jobs/{id}/start` |
| **Walk the site** with what's on the estimate in front of you: the scope written for the customer, each task with its amount and planned labor hours, and the subs. Save notes or report problems as you go, with photos, then **Done walking: start the work**. Tasks show after the walk; "What's on the estimate" stays on the job screen after | "I don't see the estimate anywhere. Or a summary of what is supposed to be done" | `SiteWalk`, `EstimateSummary` in `FieldView.jsx`, `POST /walked`, `jobs.scope_text` |
| **Notes and problems stay on the screen** after they're saved, with whether the office has handled each problem and what they said | "I typed in a note and saved it then it disappeared" | `ReportBox` in `FieldView.jsx`, `GET /api/jobs/{id}/reports` |
| **How far along is each task:** the crew lead taps 25%, 50%, 75% or Done (or types a percent), adds a note and photos of the work. Hours come from the clock, so next to it the app says how the hours compare: "On pace", "Behind: 14 hrs used for 50% (about 10 planned)", or "Done in 22 of 20 hrs planned". The office sees the same on the job page under Hours by task, with the photos | "Just make it a percentage… we will know the hours based on how long it took them" | `TaskProgress` in `FieldView.jsx`, `Pace` in `HoursBar.jsx`, `POST /tasks/{id}/progress`, task photos in `routers/photos.py` |
| **Material checked twice:** the shop checks the truck before it leaves (Materials tab → Job material lists → open the job → **Check the truck**), and the crew lead checks it again on site during the site walk (or any time from Materials on the job screen). Item by item: **Here** or **Short** and how many are there, with a reason for anything short. Anything short on site goes to the office as a problem. The shop's job list shows "Truck checked" / "Short on site" for each job, soonest start first | "There should be something for the crew lead to verify that all material is on site. It really should be verified before they even get there" | `MaterialCheck` model, `routers/requests.py`, `MaterialCheck.jsx`, `MaterialsView.jsx`, `FieldView.jsx`, `OfficeView.jsx` |
| **Labor hours spelled out:** each task shows "3 people × 8 hrs = 24 labor hrs", and the Tasks list says hours are everyone's time added up. (Time was already counted per person; estimates already priced people × hours) | "If I have 3 guys working on 1 task for an hour that's actually 3 hours" | `FieldView.jsx`, `OfficeView.jsx` |
| **Ask for more material,** signed: what, how many, why, the crew lead's full name and "I'm asking for this and I'm responsible for it". The crew lead sees each request's status | The crew lead personally signs off on what he asks for | `MaterialRequest` model, `routers/requests.py`, `MaterialAsk` in `FieldView.jsx` |
| **Requests on the Materials tab** ("Asked for from the field") for the shop, GM and PMs: **Mark sent** or **Decline** with a reason. Also on the job page. Every step is in the job's history | Someone has to see it and act on it | `MaterialRequests.jsx`, `MaterialsView.jsx`, `OfficeView.jsx` |
| **Red counts on the tabs:** open problems from the site on **Jobs** (GM, PMs) and waiting material requests on **Materials** (shop, GM, PMs). Email or text alerts come later | "A notification should probably be sent to the PM and or the GM" | `GET /api/alerts`, `App.jsx` |
| **Crew leads check and fix their crew's hours** on the job screen (Crew hours → Check or fix hours): add missed time, fix a time or task, remove a mistake. Each change needs a reason and keeps what the entry was before and after. It's written on the job's history ("Changed Luis Vega's time: was…, now…, why…"), and the office's time log flags it **Changed by crew lead**. A crew lead can only change time on jobs they run, from the last 7 days, and not an entry the office already corrected. When adding or fixing, he picks from the job's crew; "Show everyone" brings up the rest for a helper that day | Crew leads log the hours, so they fix the mistakes; "very logged… so nothing fishy is going on" | `routers/time.py`, `TimeLog.jsx`, `CrewHours` in `FieldView.jsx` |
| Fixed: fixing only the task on a time entry no longer also cuts the seconds off its times (which could make it look like it overlapped the entry before it) | Found while testing | `TimeLog.jsx` |
| Crew leads only get time entries for their own jobs (they were getting the whole company's list from the server, though the app didn't show it) | Tightening | `list_time` in `routers/time.py` |
| **This job's crew comes first** on the clock-in list; "Show everyone" brings up the rest of the team for a helper | Less scrolling past people on other jobs | `FieldView.jsx` |
| **Problems from the site:** the crew lead reports a problem or a note (with photos) any time. The office sees a red count on the job in the list and on the job page, marks each one handled with what was done, and it's all in the job's history | Damage or extra work found on site gets to the office before the crew works around it | `JobReport` model, `routers/jobs.py`, `OfficeView.jsx`, `FieldView.jsx` |
| **Photos on jobs** (site photos), for the crew lead and the office | Problems are easier to show than to describe | `routers/photos.py`, `Photos.jsx` |
| The GM's "Start job" button is now "Mark in progress" and only shows for jobs with no crew lead (crew leads start their own jobs on site) | There were two different "start" buttons | `OfficeView.jsx` |
| Jobs tab wording: "Work that never had an estimate, like a warranty callback or a quick patch, can be added here without one: Add a job with no estimate" | "For a callback…" didn't say what to do | `OfficeView.jsx` |
| **Line painting by the linear foot** (and line layout and pickleball conversions) | That's how lines are measured and their paint taken off | `library_starter.py` |
| Who sees what (checked, already in place): a crew lead signs in to the Field tab only, and never sees dollars. The warehouse (shop manager) signs in to the Materials tab only. GM sees everything | Andrew's notes 6 and 7 | `App.jsx`, `auth.py` |
| **Where material is sent from:** Materials tab → Job material lists → pick the job → Send (unchanged; answering the question) | | `MaterialsView.jsx` |
| Tests: 5 new (sending a job out and handling a problem; clock in, walk and task progress; asking for material and signing; checking material loaded and on site; a crew lead fixing time with the trail and limits; setting up crews); existing ones send their test job to the crew lead first. 110 pass | Keep it working | `tests/` |

### Database change

Migration `d3a8f5c1e9b2`: `crew_lead_id`, `start_date`, `started_at`, `site_walk_at` and `scope_text` on `jobs`; progress columns on `job_tasks` (a percent); new tables `crews`, `crew_members`, `job_crew`, `job_reports`, `material_requests` and `material_checks`. Existing jobs have no crew lead, so they show under **Not sent to a crew yet** and **crew leads won't see them until they're sent out**. Tested up, down and up on Postgres with data.

### After it goes live

1. GM: Jobs tab → open each open job → **Crew and start date → Send to a crew**. Until then crew leads' Field tabs are empty.
2. GM: Library → Tasks → tap **Line painting** and set its price and rate per LF (it was per court).
3. Make sure the crew leads and crew are on the **Team** tab with the right roles, then set up each crew under **Team → Crews**.

### How to undo

- **Everything:** revert this pull request on GitHub. To remove the columns and tables, run `alembic downgrade c7e19a4d2b55` from the Render Shell (deletes crew assignments, site reports, task progress, material requests and material checks).
- **Crew leads fixing time only:** set `CORRECTS_TIME = (Role.gm,)` in `routers/time.py`.

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
