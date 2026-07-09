# Deploying Kit Tracker to Railway

This gets Kit Tracker onto a public HTTPS URL your staff can open on their
phones (and "Add to Home Screen" so it behaves like a native app). HTTPS is
required for the camera scanner — Railway gives you that automatically.

You'll do this once; afterwards every `git push` redeploys.

## Before you start

- A [Railway](https://railway.app) account (the free/starter tier is plenty).
- This repo pushed to GitHub (it already is).
- The app lives in the **`kit-tracker/` subfolder** of the repo — that matters
  in step 2 below.

## 1. Create the project

1. Railway → **New Project** → **Deploy from GitHub repo** → pick
   `benparker010-boop/premier-league-dashboard`.
2. Railway creates a service and starts a first build. It will likely fail or
   build the wrong thing until you set the root directory in the next step —
   that's expected.

## 2. Point the service at the `kit-tracker` subfolder

Open the service → **Settings** → **Source** → set **Root Directory** to:

```
kit-tracker
```

This tells Railway to build from the folder that has `requirements.txt`,
`Procfile`, and `railway.json`. Nixpacks then auto-detects Python and installs
the dependencies; `railway.json` supplies the gunicorn start command and a
`/healthz` healthcheck.

## 3. Add a Volume (so data survives redeploys)

Railway's filesystem is wiped on every deploy, and the database is a single
SQLite file — without a Volume you'd lose all jobs/scans on each push.

Service → **Variables/Settings** → **Volumes** → **New Volume**, mount path:

```
/data
```

## 4. Set environment variables

Service → **Variables** → add these three:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `sqlite:////data/kit_tracker.sqlite` |
| `SECRET_KEY` | a long random string — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `KIT_TRACKER_PASSWORD` | the shared password your staff will type to sign in |

`PORT` is provided by Railway automatically — don't set it.

> ⚠️ Note the **four** slashes in `sqlite:////data/...` — that's an absolute
> path (`/data/kit_tracker.sqlite`) on the Volume you mounted.

## 5. Deploy & open

Trigger a redeploy (Railway does this automatically when you change settings,
or use **Deploy** → **Redeploy**). When it's live:

1. Service → **Settings** → **Networking** → **Generate Domain** to get a
   public `https://…up.railway.app` URL.
2. Open it — you'll get the **Sign in** page. Enter `KIT_TRACKER_PASSWORD`.
3. On a phone: open the URL in Safari (iOS) or Chrome (Android) → **Share /
   menu → Add to Home Screen**. It installs with the Kit Tracker icon and
   launches full-screen. The camera scanner works because the URL is HTTPS.

## Everyday updates

Push to the branch and Railway rebuilds and redeploys automatically. The
Volume (your database) is untouched by deploys.

## Backups

Your entire business record is the one SQLite file on the Volume. To grab a
copy, install the Railway CLI and run:

```bash
railway run cat /data/kit_tracker.sqlite > kit_tracker-backup-$(date +%F).sqlite
```

Do this on a schedule (even weekly) and keep the copies somewhere safe.

## Changing the password later

Edit `KIT_TRACKER_PASSWORD` in Railway → Variables and redeploy. Everyone is
signed out and uses the new password next time.

## Alternatives

The same app runs on Render, Fly.io, or PythonAnywhere — any host that runs a
Python web process over HTTPS. Set the same three environment variables and use
the start command from the `Procfile`. For a quick demo without deploying at
all, run locally and expose it with `ngrok http 5000`.
