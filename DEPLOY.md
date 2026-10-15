# Putting Courtfield online

This puts the app on a real web address with HTTPS, a Postgres database, and automatic redeploys whenever new code is pushed to GitHub. It uses [Render](https://render.com) and the `render.yaml` file in this repo.

**Cost (as of October 2026):** about $13–14 a month.
- Web service on the Starter plan: $7/month. The free plan sleeps after 15 minutes idle and takes about a minute to wake, which is no good at 7 a.m. on a job site.
- Postgres on the Basic 256 MB plan: $6/month, plus storage at $0.30/GB/month. Free databases are deleted after 30 days, so don't use one for real hours.
- The Hobby workspace itself is free.

Check [render.com/pricing](https://render.com/pricing) before you sign up, since prices change.

## One-time setup (about 15 minutes)

1. **Create a Render account** at render.com and sign up with your personal GitHub account (the one that owns `asmoore98/courtfield`). Add a payment card.
2. **Let Render see the repo.** When Render asks for GitHub access, give it the `courtfield` repo.
3. **Create the Blueprint.** In the Render dashboard, choose **New → Blueprint**, pick `courtfield`, and confirm. Render reads `render.yaml` and plans a web service called `courtfield` and a database called `courtfield-db`.
4. **Fill in the three values it asks for:**
   - `INITIAL_COMPANY`: your company name as crews should see it
   - `INITIAL_GM_NAME`: your full name
   - `INITIAL_GM_EMAIL`: the email you'll sign in with
5. **Apply.** The first build takes a few minutes.
6. **Get your sign-in link.** Open the `courtfield` service, go to **Logs**, and find the block between the `=====` lines. It has a one-time link. Open it, set your password, and you're in as the GM.
7. **Add your people** from the **Team** screen. Each crew lead or office person gets their own sign-in link. Text it to them; it works once and expires in 7 days.
8. **On each crew lead's phone:** open the link, set a password, then add the app to the home screen. On iPhone, tap Share, then Add to Home Screen. On Android, tap Install when the app offers it.

Your app's address will look like `https://courtfield-xxxx.onrender.com`. To use your own domain later (for example `app.yourcompany.com`), add it under the service's **Settings → Custom Domains**, then set a `PUBLIC_URL` environment variable to that address so sign-in links use it.

## After that

- **Updates:** every push to `main` on GitHub redeploys automatically. Database changes are applied on startup.
- **Backups:** paid Render Postgres plans include automatic backups. You can see and restore them under the database's **Recovery** tab.
- **Locked out?** In the `courtfield` service, open **Shell** and run:
  `python -m app.admin signin-link --email you@example.com`
- **Lost or replaced phone:** from Team, use **Sign out all devices** on that person, then **New password link**.
- **Someone leaves:** from Team, use **Turn off**. Their sign-ins end, and their past hours stay on every job.
