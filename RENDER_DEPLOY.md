# Deploying to Render (free, internet-accessible)

This is the "no server of your own" path. A few steps genuinely can't be
automated -- creating accounts and clicking "authorize" are things only
a human can do in a browser -- but `render.yaml` in this folder
auto-provisions everything else (the web service, the database, and all
the secret keys) so it's as close to one-click as free hosting gets.

**Read the honest tradeoff first**: Render's free tier is great for
proving this all works over the real internet. It is **not** where your
permanent company records should live -- the free web service sleeps
after 15 minutes of inactivity (30-60 sec to wake up), and Render's free
Postgres database is **automatically deleted 30 days after creation**
with no warning. Use this to test, then move to a paid Render plan or a
small VPS (see the Docker/VPS instructions in `README.md`) once you're
ready to trust it with real data.

## Steps

1. **Create a free GitHub account** if you don't have one: https://github.com/signup

2. **Create a new repository** (Add a repository -> the "+" in the top right -> "New repository"). Name it something like `itam-backend`. Leave it empty (don't add a README).

3. **Upload this folder's contents** -- on the new repo's page, click "uploading an existing file", then drag in every file and folder from this `server` folder (yes, including `render.yaml`, `Dockerfile`, `entrypoint.sh`, and the `core`/`itam_backend` subfolders). No git command line needed. Commit the upload.

4. **Create a free Render account**: https://dashboard.render.com/register (no credit card required)

5. In the Render dashboard: **New +** -> **Blueprint**, then connect your GitHub account and pick the `itam-backend` repo you just created. Render reads `render.yaml` automatically and shows you a plan: one web service + one free Postgres database.

6. Render will ask you to fill in three values it couldn't generate for you (these become your admin login):
   - `DJANGO_SUPERUSER_USERNAME` -- e.g. `admin`
   - `DJANGO_SUPERUSER_EMAIL` -- any email, doesn't need to be real
   - `DJANGO_SUPERUSER_PASSWORD` -- a real password, this logs into the dashboard

7. Click **Apply**. Render builds the Docker image and deploys it -- takes a few minutes the first time. When it's done, your service has a URL like `https://itam-backend-xxxx.onrender.com`.

## Where everything is afterward

- **Admin dashboard**: `https://itam-backend-xxxx.onrender.com/admin/` -- log in with the username/password from step 6.
- **Enrollment Key** (needed on every client PC's Cloud Sync tab): in the Render dashboard, open your web service -> **Environment** tab -> find `DEVICE_ENROLLMENT_KEY` -> click the eye icon to reveal it -> copy it.
- **Server URL** (also needed on every client): the `https://itam-backend-xxxx.onrender.com` address from step 7 -- no `/admin` on the end for this one, that part's just for your browser.

## In AssetManager's Cloud Sync tab

| Field | Value |
|---|---|
| Server URL | `https://itam-backend-xxxx.onrender.com` (your actual Render URL) |
| Enrollment Key | the value you copied from Render's Environment tab |

Tick **Enable Cloud Sync**, **Save Settings**, then **Sync Now**. If the
service was asleep (free tier, 15+ min idle), the first request can take
30-60 seconds to respond -- that's normal, not an error.

## When you outgrow the free tier

Two options, same `render.yaml`/`Dockerfile`/`docker-compose.yml` work
for both:
- Upgrade the web service and database to Render's paid plans (stays in
  the same dashboard, just costs money and stops sleeping/expiring).
- Move to a small VPS using `docker-compose.yml` instead (see
  `README.md` section 2) -- cheaper long-term, and you control the data
  directly instead of trusting a third party's free tier.
