# Hybrid Attendance Tracker (Django)

A login-protected version of the attendance tracker: every visitor sees the
sign-in page first, and each user's calendar entries are stored server-side
in the database, scoped to their own account only.

## What's included

- Django auth (login / logout / signup) using Django's built-in, hashed
  password storage — nothing is stored in plain text.
- `tracker.AttendanceRecord` — one row per user per day (`WFH`, `WFO`,
  `Leave`, `Holiday`), with a database constraint so a user can only have
  one status per date.
- Every view that touches attendance data is `@login_required` and always
  filters by `request.user` — one user can never see or edit another's
  entries.
- The same calendar UI as before (click a date → choose a status), now
  saved via an AJAX call to the server instead of client-side storage.
- Server-side `.xlsx` export (month or full year) built with `openpyxl`,
  streamed straight from the database for the signed-in user.

## Run it locally

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` — you'll land on the sign-in page. Use
"Create an account" to register, or the superuser you created.

## Deploying to Render

1. Push this project to a Git repo and create a new **Web Service** on
   Render pointing at it.
2. Build command: `pip install -r requirements.txt`
3. Start command is already set in the `Procfile` (`gunicorn
   attendance_project.wsgi:application`); the `release` line runs
   migrations automatically on each deploy.
4. In the service's **Environment** tab, set:
   - `DJANGO_SECRET_KEY` — a long random string (never reuse the dev key)
   - `DJANGO_DEBUG` — `False`
   - `DJANGO_ALLOWED_HOSTS` — your Render URL, e.g. `your-app.onrender.com`
5. SQLite works for a single small team, but Render's disk isn't
   persistent across deploys on the free tier. For real data safety in
   production, add a Render **PostgreSQL** instance and point
   `DATABASES` in `attendance_project/settings.py` at it (e.g. via
   `dj-database-url` + `psycopg`) instead of SQLite.

## Notes on data safety

- Passwords are hashed by Django (PBKDF2 by default) — never stored or
  logged in plain text.
- CSRF protection is on by default for all POST requests (login, saving
  a status).
- Every query in `tracker/views.py` filters by `user=request.user`, so
  there's no endpoint that can return or modify another account's data.
- For production, keep `DJANGO_DEBUG=False` and use HTTPS (Render gives
  you this automatically) — the settings already redirect to HTTPS and
  mark cookies secure when `DEBUG` is off.
