# Courtfield

Job-costing software for court and sports-field contractors. It tracks crew hours by task against the estimate, from the first day on site to closeout.

This is **Phase 1: labor hours versus the estimate.** Materials (Phase 2), estimating (Phase 3), and change orders, scheduling and maintenance (Phase 4) come later.

> All data in this repo is fictional sample data. No customer data belongs here.

## What works today

- **Crew lead on a phone:** pick the job, check off crew members, and tap a task to clock them in. Tapping a different task switches them over, closing the first task at the same moment. A clock-out bar appears when anyone selected is on the clock.
- **Works without signal:** every tap is saved on the phone first and synced when there's a connection. Resending is safe: the server ignores duplicates, and the newest edit wins.
- **GPS stamp** on clock-in and clock-out. Entries more than 400 m from the job pin are flagged "Off site" in the time log.
- **Office view (GM, owner, estimator):** every job's hours against the estimate, labor dollars against the labor budget, and a per-task breakdown with the time log.
- **Roles:** crew leads see hours only, never dollars. The owner is read-only. Only the GM and estimators create jobs.
- **Multi-tenant from day one:** every row carries a company id, and every query is scoped to the signed-in user's company.

## Run it locally

```bash
# Backend (Python 3.11+)
cd backend
pip install -r requirements.txt
python -m app.seed                 # loads sample company, crew and jobs
uvicorn app.main:app --reload      # http://localhost:8000

# Front end (Node 20+), in a second terminal
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

To serve everything from one port instead, run `npm run build` in `frontend/`. The backend serves `frontend/dist` automatically.

Sign in with a sample account from the sign-in screen: crew lead, general manager, owner or estimator.

## Tests

```bash
cd backend && python -m pytest
```

The tests cover tenant isolation, role limits, idempotent sync, stale edits, task switching inside one offline batch, overlap and sanity rejections, the off-site flag, and the estimate-versus-actual math.

## Layout

```
backend/app/
  models.py     companies, users/roles, jobs, job tasks, time entries
  costing.py    estimate-vs-actual math (pure functions)
  routers/      jobs + costing, field time sync
  auth.py       dev bearer tokens + role checks
  seed.py       fictional sample data
frontend/src/
  FieldView.jsx   crew lead's phone screen
  fieldStore.js   offline queue and sync
  OfficeView.jsx  job list and job detail
  HoursBar.jsx    hours against the estimate, with the estimate drawn as a painted line
```

## Before real use

- **Replace dev auth.** Sign-in currently uses static access codes. It needs real accounts with hashed passwords or an identity provider, plus short-lived sessions.
- **Move to Postgres** by setting `DATABASE_URL`, and add migrations (Alembic).
- **Payroll export** and an accounting export (QuickBooks or whatever the pilot uses).
- **A real job and estimate editor in the UI.** Jobs can be created through the API today.
