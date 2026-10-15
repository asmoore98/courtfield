# Courtfield

Job-costing software for court and sports-field contractors. It tracks crew hours by task against the estimate, from the first day on site to closeout.

This is **Phase 1: labor hours versus the estimate.** Materials (Phase 2), estimating (Phase 3), and change orders, scheduling and maintenance (Phase 4) come later.

> All data in this repo is fictional sample data. No customer data belongs here.

## What works today

- **Crew lead on a phone:** pick the job, check off crew members, and tap a task to clock them in. Tapping a different task switches them over, closing the first task at the same moment. A clock-out bar appears when anyone selected is on the clock.
- **Works without signal:** every tap is saved on the phone first and synced when there's a connection. Resending is safe: the server ignores duplicates, and the newest edit wins.
- **GPS stamp** on clock-in and clock-out. Entries more than 400 m from the job pin are flagged "Off site" in the time log.
- **Job and estimate entry (GM, estimator):** create or edit a job with its court type, scope, contract amount, the labor rate used in the estimate, and the job's location (or "Use my current location" from a phone on site). Tasks get estimated hours and can be added, renamed, reordered and removed, starting from a task list that matches the court type and scope. A task with crew time logged on it can't be removed. Live totals show estimated crew hours, labor dollars, and labor as a share of the contract.
- **Time corrections (GM):** add time from the office (a dead phone, a forgotten clock-in), fix an entry's crew member, task or times, or remove it. Every change needs a reason and is kept in the entry's history with who made it and what it was before. Removed time is kept, not deleted, and stops counting toward hours and cost. Once the office corrects an entry, the field app can still clock it out but can't undo the correction.
- **Installs like an app:** on Android, an Install button; on iPhone, Add to Home Screen. Once installed it opens full-screen and loads with no signal, using the jobs and crew saved from the last sync.
- **Job status (GM):** start, complete or reopen a job. Crew leads only see jobs that aren't complete.
- **Office view (GM, owner, estimator):** every job's hours against the estimate, labor dollars against the labor budget, and a per-task breakdown with the time log.
- **Sign-in:** email and password, with passwords stored as salted scrypt hashes. Each phone or computer gets its own sign-in that lasts 90 days, and the GM can end it at any time. New people and password resets use one-time links that expire in 7 days. Repeated wrong passwords are slowed down.
- **Team (GM):** add people with their role and labor cost per hour, send sign-in links, sign a lost phone out, or turn someone off. Plain crew members don't need an email; their crew lead clocks them in.
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

Sign in with a sample account from the sign-in screen (crew lead, general manager, owner or estimator). Each is `<role>@sample.test` with password `courtfield-dev`. Sample accounts only exist in development; `python -m app.seed` refuses to run unless `COURTFIELD_ENV=dev`.

## Put it online

See [DEPLOY.md](DEPLOY.md). It covers a Render Blueprint (`render.yaml`) and a `Dockerfile` that builds the web app and runs the API, applying database migrations on startup.

### Clickable preview without a server

`npm run build:demo` in `frontend/` builds `dist-demo/index.html`, a single file with a stand-in server and the sample data inside it. It's for showing the app to someone: changes save only in that browser, and "Reset sample data" starts over.

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

## Database changes

Production uses Postgres with Alembic migrations in `backend/migrations`. After changing `models.py`:

```bash
cd backend
alembic revision --autogenerate -m "what changed"   # review the generated file
alembic upgrade head
```

## Still to do

- **Payroll export** and an accounting export (QuickBooks or whatever the pilot uses).
- **Address lookup.** Job location is entered as coordinates or taken from the device; turning an address into a map pin needs a geocoding service.
- **Email delivery of sign-in links.** Links are copied and texted by the GM for now.
