# Enterprise Asset Management -- Cloud Backend (Phase 1)

Django + Django REST Framework backend implementing the client-server
architecture from the "Major Architecture Update" document:

- Device registration with per-device API keys (§11 security)
- Sync endpoint with automatic hardware change detection (§4)
- Permanent audit history, never overwritten (§5)
- Notifications for hardware changes, new devices, sync failures (§6)
- Two-way commands: admin queues instructions, device picks them up (§10)
- Django Admin as the v1 Admin Web Portal: dashboard, search/filter,
  branch-wise management, role-based access via Django's built-in
  permission system (§2)

**I could not run or test this against a live server** -- I'm working in
a sandboxed environment with no internet access, so Django itself isn't
installed here and there's nowhere to host it. Every file has been
syntax-checked (`py_compile`) and the core change-detection algorithm has
been tested in isolation against realistic hardware-swap scenarios (see
chat), but you should run the standard Django checks below as your first
step on a real machine before trusting it with real data.

## Quick start -- pick one

- **Just want to see it running on your own PC?** Double-click
  `setup_local.bat` -- it creates the virtual environment, installs
  dependencies, generates your secret keys, sets up the database, walks
  you through creating an admin login, and starts the server, all in one
  go. Prints your admin URL and Enrollment Key at the end.
- **Want a real internet address, free, no server of your own?** See
  `RENDER_DEPLOY.md` -- `render.yaml` auto-provisions the server,
  database, and secret keys; you only click a few buttons.
- **Manual setup / understand each step?** Section 1 below.

## 1. First-time setup (any machine with Python + internet)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set SECRET_KEY, DEVICE_ENROLLMENT_KEY, and DB_* (or leave
# DB_ENGINE=sqlite for a quick local test with zero DB setup)

python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser
python manage.py check              # sanity check before running
python manage.py runserver
```

Visit `http://127.0.0.1:8000/admin/` and log in with the superuser you
created -- that's the Admin Web Portal for Phase 1.

## 2. Running for real (Docker, any host)

```bash
cp .env.example .env
# edit .env with real values -- DB_ENGINE=postgresql, real SECRET_KEY, etc.

docker compose up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Put this behind a reverse proxy (Caddy/Nginx) with a real TLS cert for
the HTTPS requirement in §11 -- `SECURE_SSL_REDIRECT` in settings.py
assumes something in front of it is terminating TLS.

## 3. API reference

All device endpoints expect JSON and (except registration) the header:
`Authorization: Api-Key <device's api_key>`

### `POST /api/devices/register/`
One-time call the client makes on first install.

```json
{
  "enrollment_key": "the DEVICE_ENROLLMENT_KEY from .env",
  "hostname": "DESKTOP-8S1E4D9",
  "mac_address": "d5:54:52:48:22:8b",
  "ip_address": "192.168.29.106",
  "os_info": "Windows 11",
  "device_type": "Desktop",
  "branch_name": "Vadodara",
  "employee_name": "Abhinav",
  "designation": "IT Executive",
  "department": "IT"
}
```
Response: `{"device_id": "...", "api_key": "...", "is_new": true}` --
the client must store `api_key` locally (e.g. in the SQLite DB next to
`asset_manager.py`) and send it on every future call.

### `POST /api/sync/`
The main call -- send on every scan (see DEPLOYMENT.md Phase 2 for how
`asset_manager.py` should be extended to call this).

```json
{
  "ip_address": "192.168.29.106",
  "employee_name": "Abhinav",
  "asset": {
    "cpu_name": "Custom-Built PC (Motherboard: Gigabyte B760M DS3H)",
    "cpu_serial": "BFEBFBFF000B0671",
    "processor": "Intel(R) Core(TM) i5-14600K",
    "motherboard_serial": "...",
    "bios_serial": "...",
    "ram_total": "16 GB",
    "ram_devices": [{"slot": 1, "size": "16 GB", "serial": "E950B4F4", "manufacturer": "G Skill Intl"}],
    "storage_devices": [{"name": "KINGSTON SNV2S1000G", "serial": "...", "size": "1 TB", "type": "SSD"}],
    "monitor_name": "Acer K202HQLA", "monitor_serial": "T1KSS0134221"
  }
}
```
Response includes any pending admin commands the device should act on:
```json
{"synced_at": "...", "changes_detected": 1, "commands": [{"id": 4, "command_type": "force_scan", ...}]}
```

### `POST /api/heartbeat/`
Cheap "I'm still online" ping between full syncs. Body: `{}`.

### `GET /api/commands/pending/`
Poll for instructions without doing a full sync.

### `POST /api/commands/<id>/result/`
Device reports back: `{"status": "completed", "result_detail": "..."}`

## 4. Trying it locally with curl (no client needed yet)

```bash
# 1. Register a test device
curl -X POST http://127.0.0.1:8000/api/devices/register/ \
  -H "Content-Type: application/json" \
  -d '{"enrollment_key":"change-this-to-a-long-random-string","hostname":"TEST-PC","device_type":"Desktop","branch_name":"Vadodara","employee_name":"Test User"}'
# -> copy the "api_key" from the response

# 2. Send a sync with that key
curl -X POST http://127.0.0.1:8000/api/sync/ \
  -H "Authorization: Api-Key PASTE_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"asset":{"cpu_name":"Test PC","ram_total":"16 GB","ram_devices":[],"storage_devices":[]}}'

# 3. Send it again with a different ram_total to see change detection fire
curl -X POST http://127.0.0.1:8000/api/sync/ \
  -H "Authorization: Api-Key PASTE_KEY_HERE" \
  -H "Content-Type: application/json" \
  -d '{"asset":{"cpu_name":"Test PC","ram_total":"32 GB","ram_devices":[],"storage_devices":[]}}'
# -> check /admin/core/assetchangelog/ for the new audit row,
#    and /admin/core/notification/ for the alert
```

## 5. Security notes (§11)

- Rotate `DEVICE_ENROLLMENT_KEY` per branch if you want to be able to
  cut off one branch's ability to register new devices without
  affecting others -- current setup uses one shared key; splitting it
  per-branch is a small follow-up (add an `enrollment_key` field to
  `Branch` and check against that instead of the global settings value).
  I kept it global for Phase 1 to keep first deployment simple.
- Deactivating a device (`Device.is_active = False`, or the "Deactivate
  selected devices" admin action) immediately blocks that device's API
  key on its next call -- use this for stolen/decommissioned machines.
- `AssetChangeLog` records are **not editable or deletable** through the
  admin (see `has_add_permission`/`has_change_permission` in admin.py) --
  keeps the audit trail honest.
- Passwords for admin/manager accounts use Django's built-in hashing
  (PBKDF2 by default) -- nothing to configure.
- Set real `ALLOWED_HOSTS` and put this behind HTTPS before going live;
  `DEBUG=False` in production hides stack traces from unauthenticated
  callers.

## 6. What's NOT built yet (see chat for the phase plan)

- **Phase 2**: `asset_manager.py` doesn't call this API yet -- it still
  only writes to its local SQLite file. Next step is adding a sync
  module to the client: on save, POST to `/api/sync/` if online,
  otherwise queue locally and retry (a `pending_sync` flag column on the
  local `assets` table is enough to implement the queue).
- **Phase 3 polish**: Django Admin covers the *functional* requirements
  of §2 (dashboard, search, filter, role-based access) but is not a
  custom-branded UI. If you want a nicer/branded dashboard instead of
  Django Admin's stock look, that's a separate frontend project (e.g. a
  small React or server-rendered dashboard hitting some additional
  read-only summary API endpoints).
- Email sending for critical notifications is wired to settings
  (`EMAIL_HOST` etc.) but nothing currently calls `send_mail()` --
  hook that into `Notification` creation for `severity='critical'` once
  you have real SMTP credentials.
- Barcode/QR, mobile app, AD/Entra ID integration, helpdesk integration,
  predictive maintenance (§12) -- all explicitly "future expansion" in
  your own document; not attempted here.
