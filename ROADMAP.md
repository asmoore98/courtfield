# Courtfield roadmap

What's planned and what's parked for later. Newest ideas get added at the bottom of "Down the road". When something ships, it moves to CHANGELOG.md.

## Next up

1. **Batch 4: Material library**
   - Materials get the same search and naming rules as tasks (other names, one name per item); today the price list is searchable by name only
   - Coverage saved with each material (today it's typed on the estimate line; court size and the math already work)
   - Tasks suggest their materials (paint task → add paint, then pick type, color, amount)
2. **Batch 5: Documents and insurance**
   - Real file uploads for plans (needs file storage; Google Drive links are the placeholder until then)
   - Insurance certs: ours naming a client (kept with the client), subs' naming us (kept with the sub)
   - Expiration alerts to the GM / PM before a cert runs out

## Down the road

- **Scheduling and material planning for a big job list.** The company has ~17 open jobs and 60+ on backorder. Needs a way to see active vs. upcoming jobs at a glance, schedule crews and dates, and plan material purchasing and deliveries so no job is missed and material is ordered and on site on time
  - Creating a job puts it on the calendar: set a start date (and expected end) as part of creating it
  - Interactive schedule of active and upcoming jobs showing when each starts and ends. With this many jobs at once it has to be streamlined and simple, but still carry the info that matters (crew, dates, status, material ready or not). Details to be worked out together
  - Assign crews when a job goes on the calendar. The crew assignment carries over to the Field tab
  - Field tab shows only active, current jobs. Jobs tab shows all active and upcoming jobs, with completed jobs tucked away in a separate, hidden-by-default section
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
- **Real production rates from finished jobs.** When a job closes, the crew lead enters how much got done (LF, SF); the app works out the actual rate per task (e.g. crack fill ran 32 LF/hr, not 40) and shows it next to the library rate so the GM can adjust. Needs consistent hour tracking per task first
- GM can edit the site checklist questions in the app (today they're in `checklists.py`)
- Site checklist for turf fields, and more court-type-specific questions
- Photos attached to a checklist answer (needs file storage, Batch 5)
- "Send back to sales" when the checklist is missing answers the estimator needs
