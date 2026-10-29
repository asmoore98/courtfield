# Courtfield change log

Each batch of changes gets an entry: what changed, where, why, and how to undo it. Newest first.

To undo a whole batch after it's merged: open its pull request on GitHub and click **Revert**. To keep only part of a batch, use the "Files" list below to see where each piece lives.

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
