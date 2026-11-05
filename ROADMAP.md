# Courtfield roadmap

What's planned and what's parked for later. Newest ideas get added at the bottom of "Down the road". When something ships, it moves to CHANGELOG.md.

## Next up

1. **Batch 5: Built-up tasks and the material library**
   - A task holds all its parts: crew hours, machine time (e.g. 45 min per 20-ton load at $150/hr), materials and fees, plus a markup, as one price. Some tasks are simply priced by the unit (acres × price per acre); others are built up. The estimator picks per task
   - Base rock and fill by length × width × depth: works out cubic yards and tons, the material cost and the spreading time
   - Starter material list with average prices (concrete, rebar, base rock, sand, asphalt, acrylics, posts, nets, fence) to fix in the library later
   - Tasks bring their materials: pour concrete → concrete; color coat → color concentrate
   - Court size with a border: playing size (e.g. 94 × 50) plus a border band (e.g. 5 ft all around) works out the surfaced size (104 × 60). Lines go on the playing area; the border can be its own color
   - Materials get the same search and naming rules as tasks (other names, one name per item); today the price list is searchable by name only
   - Coverage saved with each material (today it's typed on the estimate line; court size and the math already work)
   - Tasks suggest their materials (paint task → add paint, then pick type, color, amount)
2. **Building construction broken down** (when they start bidding buildings): footings, block or framing, roof, doors and windows, plumbing rough-in and fixtures, electrical, HVAC, finishes, each with its own tasks and materials. And the estimate's task list grouped into Site work, Court and Buildings
3. **Batch 6: Documents and insurance**
   - Connect the company Google Drive: photos go to a Drive folder per lead instead of the database (move the ones already in the app), and pick a file from Drive inside the app instead of copying its link. Needs a Google Cloud project on the company Google account (Drew gets access when his dad starts)
   - Real file uploads for plans and documents (PDFs), to the same Drive
   - Insurance certs: ours naming a client (kept with the client), subs' naming us (kept with the sub)
   - Expiration alerts to the GM / PM before a cert runs out

## Down the road

- **Scheduling and material planning for a big job list.** The company has ~17 open jobs and 60+ on backorder. Needs a way to see active vs. upcoming jobs at a glance, schedule crews and dates, and plan material purchasing and deliveries so no job is missed and material is ordered and on site on time. They schedule in a Gantt program today (name to confirm, possibly GanttPRO): import their current schedule, keep the layout familiar, and work out whether the app replaces it or syncs with it. Need an export (Excel/CSV or MS Project XML) to see how it's set up
  - Expected end date on a job (the start date is set when it's sent out, since Batch 4)
  - Interactive schedule of active and upcoming jobs showing when each starts and ends. With this many jobs at once it has to be streamlined and simple, but still carry the info that matters (crew, dates, status, material ready or not). Details to be worked out together
- **GM approval before an estimate goes to the client.** Estimator taps "Ready to send", it goes to the GM, the GM taps "Good to send", and the proposal goes out to the client automatically from there (needs email sending)
- Follow-up and expiration reminders by email or text (in-app only today)
- Desktop layout tuned for estimating on a big screen
- Tighten roles once all positions are known (PM, Sales, and others; some PMs can see dollars, some can't)
- Same paper-trail approach for employee hours as for estimates
- Estimate numbering: match the company's current numbers once we see them
- Proposal header: real company details, logo, standard terms
- Intro / sign-in screen redesign and overall look ("beautifying")
- Change orders (add/deduct with customer sign-off)
- Maintenance and warranty tracking (resurfacing cycles, warranty by material lot number)
- QuickBooks / accounting export
- Emailing sign-in links instead of texting them
- **Real production rates from finished jobs.** When a task is marked done, the app takes its amount (LF, SF) and the hours the clock says it took, works out the actual rate (e.g. crack fill ran 32 LF/hr, not 40) and shows it next to the library rate so the GM can adjust
- GM can edit the site checklist questions in the app (today they're in `checklists.py`)
- Site checklist for turf fields, and more court-type-specific questions
- Photos attached to a checklist answer (needs file storage, Batch 5)
- "Send back to sales" when the checklist is missing answers the estimator needs
- Two crews on one big job
- Calendar of start dates by crew, and moving a job's date by dragging it
- Text or email the GM and the job's PM when a crew lead reports a problem or asks for material (today: red counts on the Jobs and Materials tabs)
- A day-end "how far along" prompt for the crew lead before clocking the crew out
- Charge extra material back to a crew: a report of signed material requests by crew lead, with the cost (the GM sees dollars, crews never do)
- Problem reports and task photos saved into the job's Google Drive folder (needs Drive storage)
- A weekly "time changed in the field" report for the GM: every hour a crew lead added, fixed or removed, with the reasons
