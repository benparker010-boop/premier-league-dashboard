"""Kit Tracker — scan equipment out to jobs and back in again."""
import calendar as pycalendar
import hmac
import io
import os
import re
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta

import qrcode
import qrcode.constants
from icalendar import Calendar as ICalendar
from markupsafe import Markup, escape
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from models import (
    CATEGORIES,
    EQUIPMENT_STATUSES,
    STAFF,
    AppSetting,
    Equipment,
    Job,
    ScanEvent,
    db,
    utcnow,
)
from seed import seed_if_empty


def _ensure_schema():
    """Tiny idempotent migration: add columns introduced after v1 to an
    existing SQLite database (db.create_all only creates missing *tables*)."""
    with db.engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(jobs)"))]
        if "source_uid" not in cols:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN source_uid VARCHAR(255)"))
            conn.commit()


def _database_uri():
    """Where the SQLite file lives.

    In production (e.g. Railway) set DATABASE_URL to a path on a mounted
    volume so data survives redeploys, e.g.
    ``sqlite:////data/kit_tracker.sqlite``. Locally it defaults to a file in
    the Flask instance folder.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # Make sure the target directory exists for an absolute sqlite path.
        if url.startswith("sqlite:////"):
            path = url[len("sqlite:///"):]  # keep the leading slash
            os.makedirs(os.path.dirname(path), exist_ok=True)
        return url
    return "sqlite:///kit_tracker.sqlite"


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "kit-tracker-dev")
app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

# Optional shared-password gate. When KIT_TRACKER_PASSWORD is set (required on
# any public URL), every page needs a one-time shared-password login. Left
# unset locally, the app is open — matching the "no accounts" brief for
# warehouse-LAN use.
APP_PASSWORD = os.environ.get("KIT_TRACKER_PASSWORD", "").strip()
AUTH_ENABLED = bool(APP_PASSWORD)

db.init_app(app)

with app.app_context():
    db.create_all()
    _ensure_schema()
    seed_if_empty()

if AUTH_ENABLED and app.config["SECRET_KEY"] == "kit-tracker-dev":
    app.logger.warning(
        "KIT_TRACKER_PASSWORD is set but SECRET_KEY is the insecure default — "
        "set a strong random SECRET_KEY env var so login sessions can't be forged."
    )
elif not AUTH_ENABLED:
    app.logger.warning(
        "KIT_TRACKER_PASSWORD is not set — the app is UNPROTECTED. Set it before "
        "exposing Kit Tracker on a public URL."
    )

# Endpoints reachable without logging in.
PUBLIC_ENDPOINTS = {"login", "static", "service_worker", "manifest", "healthz"}


@app.before_request
def require_login():
    if not AUTH_ENABLED:
        return None
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None
    if session.get("authed"):
        return None
    if request.path.startswith("/api/"):
        return jsonify(result="error", message="Session expired — please log in again."), 401
    return redirect(url_for("login", next=request.path))

# QR labels encode e.g. "KIT-0042"; tolerate missing dash / leading zeros.
# Digit count is capped so absurd numbers fall through to "not recognized"
# instead of overflowing SQLite's 64-bit integer.
KIT_CODE_RE = re.compile(r"^\s*KIT-?0*(\d{1,9})\s*$", re.IGNORECASE)

BADGE_CLASSES = {
    "In Warehouse": "ok",
    "Out on Job": "info",
    "Missing": "danger",
    "Setup in Progress": "warn",
    "Live": "info",
    "Collection in Progress": "purple",
    "Completed": "ok",
    "Items Missing": "danger",
}


# ---------------------------------------------------------------- helpers

def get_job_or_404(job_id):
    job = db.session.get(Job, job_id)
    if job is None:
        abort(404)
    return job


def kit_state(job):
    """The job's kit list: [{equipment, setup, collection}] plus counts.

    The kit list is defined as every equipment item with a SETUP scan for
    this job, in the order it was scanned on.
    """
    setup_scans = (
        ScanEvent.query.filter_by(job_id=job.id, scan_type="SETUP")
        .order_by(ScanEvent.timestamp, ScanEvent.id)
        .all()
    )
    collection_scans = {
        scan.equipment_id: scan
        for scan in ScanEvent.query.filter_by(job_id=job.id, scan_type="COLLECTION")
    }
    rows = [
        {
            "equipment": scan.equipment,
            "setup": scan,
            "collection": collection_scans.get(scan.equipment_id),
        }
        for scan in setup_scans
    ]
    counts = {
        "expected": len(rows),
        "collected": sum(1 for row in rows if row["collection"]),
    }
    return rows, counts


def job_counts(job):
    _, counts = kit_state(job)
    return counts


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.template_filter("dt")
def fmt_dt(value, fmt="%d %b %Y %H:%M"):
    # Timestamps are stored naive-UTC; emit them tagged so a small script in
    # base.html can re-render them in the viewer's local timezone.
    if not value:
        return "—"
    return Markup(
        f'<span class="localdt" data-utc="{value.isoformat()}Z">'
        f"{escape(value.strftime(fmt))} UTC</span>"
    )


@app.template_filter("d")
def fmt_d(value):
    return value.strftime("%d %b %Y") if value else "—"


@app.context_processor
def inject_helpers():
    return {
        "badge_class": lambda status: BADGE_CLASSES.get(status, "muted"),
        "auth_enabled": AUTH_ENABLED,
    }


# ---------------------------------------------------------------- auth / PWA

@app.route("/login", methods=["GET", "POST"])
def login():
    if not AUTH_ENABLED or session.get("authed"):
        return redirect(url_for("dashboard"))
    error = None
    if request.method == "POST":
        supplied = (request.form.get("password") or "").encode("utf-8")
        expected = APP_PASSWORD.encode("utf-8")
        if hmac.compare_digest(supplied, expected):
            session["authed"] = True
            session.permanent = True
            target = request.args.get("next") or url_for("dashboard")
            # Only allow same-site relative redirects.
            if not target.startswith("/"):
                target = url_for("dashboard")
            return redirect(target)
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/healthz")
def healthz():
    # Cheap liveness probe for Railway's healthcheck.
    return "ok", 200


@app.route("/sw.js")
def service_worker():
    # Served from the site root so its scope covers the whole app.
    response = send_file(
        os.path.join(app.static_folder, "sw.js"), mimetype="application/javascript"
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/manifest.webmanifest")
def manifest():
    response = send_file(
        os.path.join(app.static_folder, "manifest.webmanifest"),
        mimetype="application/manifest+json",
    )
    response.headers["Cache-Control"] = "no-cache"
    return response


# ---------------------------------------------------------------- dashboard

@app.route("/")
def dashboard():
    active_jobs = (
        Job.query.filter(Job.status != "Completed")
        .order_by(Job.setup_date.desc(), Job.id.desc())
        .all()
    )
    jobs_with_counts = [(job, job_counts(job)) for job in active_jobs]
    stats = {
        "active_jobs": len(active_jobs),
        "jobs_missing": Job.query.filter_by(status="Items Missing").count(),
        "equipment_out": Equipment.query.filter_by(status="Out on Job").count(),
        "equipment_missing": Equipment.query.filter_by(status="Missing").count(),
    }
    return render_template("dashboard.html", jobs=jobs_with_counts, stats=stats)


# ---------------------------------------------------------------- calendar

def _month_base(param):
    """Parse a ?month=YYYY-MM param into the first of that month; default today."""
    if param:
        try:
            year, month = (int(part) for part in param.split("-", 1))
            return date(year, month, 1)
        except (ValueError, TypeError):
            pass
    return date.today().replace(day=1)


@app.route("/calendar")
def calendar_view():
    today = date.today()
    base = _month_base(request.args.get("month"))
    year, month = base.year, base.month

    # Weeks of date objects (Mon-first), including spillover days so the grid
    # is always a full rectangle like Google Calendar's month view.
    weeks = pycalendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    start, end = weeks[0][0], weeks[-1][-1]

    # A job shows on its setup date and (if different) its collection date.
    jobs = Job.query.filter(
        db.or_(
            Job.setup_date.between(start, end),
            Job.collection_date.between(start, end),
        )
    ).all()
    by_day = defaultdict(list)
    for job in jobs:
        if job.setup_date and start <= job.setup_date <= end:
            by_day[job.setup_date].append({"job": job, "kind": "setup"})
        if job.collection_date and start <= job.collection_date <= end:
            by_day[job.collection_date].append({"job": job, "kind": "collection"})

    grid = []
    for week in weeks:
        row = []
        for day in week:
            row.append(
                {
                    "date": day,
                    "in_month": day.month == month,
                    "is_today": day == today,
                    "events": sorted(
                        by_day.get(day, []),
                        key=lambda e: (e["kind"] != "setup", e["job"].job_name.lower()),
                    ),
                }
            )
        grid.append(row)

    # Agenda: every dated job in this month, chronological — the mobile-friendly
    # companion to the grid.
    agenda = sorted(
        [j for j in jobs if (j.setup_date and start <= j.setup_date <= end)
         or (j.collection_date and start <= j.collection_date <= end)],
        key=lambda j: (j.setup_date or j.collection_date or end),
    )

    prev_month = (base - timedelta(days=1)).replace(day=1)
    next_month = (base + timedelta(days=32)).replace(day=1)
    return render_template(
        "calendar.html",
        grid=grid,
        agenda=agenda,
        month_label=base.strftime("%B %Y"),
        prev_month=prev_month.strftime("%Y-%m"),
        next_month=next_month.strftime("%Y-%m"),
        this_month=today.strftime("%Y-%m"),
        weekday_names=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        today=today,
        ical_configured=bool(get_setting("gcal_ical_url")),
    )


# ------------------------------------------------ Google Calendar (iCal) sync

def get_setting(key, default=""):
    row = db.session.get(AppSetting, key)
    return row.value if row else default


def set_setting(key, value):
    row = db.session.get(AppSetting, key)
    if row is None:
        db.session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.session.commit()


def _event_dates(component):
    """Map an iCal VEVENT's start/end to (setup_date, collection_date)."""
    start = component.get("dtstart").dt
    dtend = component.get("dtend")
    end = dtend.dt if dtend is not None else start

    setup_date = start.date() if isinstance(start, datetime) else start
    if isinstance(end, datetime):
        collection_date = end.date()
    elif isinstance(end, date):
        # All-day events use an EXCLUSIVE end date (the morning after) — step
        # back a day so a one-day event collects on the same day it sets up.
        collection_date = end - timedelta(days=1)
    else:
        collection_date = setup_date
    if collection_date < setup_date:
        collection_date = setup_date
    return setup_date, collection_date


def import_ical(raw_bytes):
    """Parse an iCal feed and upsert its events as jobs. Returns a summary."""
    cal = ICalendar.from_ical(raw_bytes)
    created = updated = skipped = 0
    # Ignore long-past events so a first sync doesn't import years of history.
    cutoff = date.today() - timedelta(days=60)

    for component in cal.walk("VEVENT"):
        if component.get("dtstart") is None:
            skipped += 1
            continue
        setup_date, collection_date = _event_dates(component)
        if collection_date < cutoff:
            skipped += 1
            continue

        uid = str(component.get("uid") or "").strip()
        name = (str(component.get("summary") or "Untitled event").strip() or "Untitled event")[:120]
        location = str(component.get("location") or "").strip()[:200]

        job = Job.query.filter_by(source_uid=uid).first() if uid else None
        if job is not None:
            # Refresh scheduling fields only — never touch status or scans, so
            # a job already being worked isn't disturbed by a re-sync.
            job.job_name = name
            job.location = location
            job.setup_date = setup_date
            job.collection_date = collection_date
            updated += 1
        else:
            db.session.add(
                Job(
                    job_name=name,
                    client_name="",
                    location=location,
                    setup_date=setup_date,
                    collection_date=collection_date,
                    status="Setup in Progress",
                    source_uid=uid or None,
                )
            )
            created += 1

    db.session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def fetch_ical(url):
    # Google's "secret iCal address" is a plain HTTPS GET, no auth needed.
    request_obj = urllib.request.Request(url, headers={"User-Agent": "KitTracker/1.0"})
    with urllib.request.urlopen(request_obj, timeout=20) as response:
        return response.read()


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            url = (request.form.get("ical_url") or "").strip()
            if url and not url.lower().startswith(("http://", "https://")):
                flash("That doesn't look like a valid link (it should start with https://).", "error")
            else:
                set_setting("gcal_ical_url", url)
                flash("Calendar link saved." if url else "Calendar link cleared.", "success")
        elif action == "sync":
            url = get_setting("gcal_ical_url").strip()
            if not url:
                flash("Add your calendar link first, then sync.", "error")
            else:
                try:
                    summary = import_ical(fetch_ical(url))
                    set_setting("gcal_last_sync", utcnow().isoformat())
                    result_text = "{} new, {} updated".format(
                        summary["created"], summary["updated"]
                    )
                    if summary["skipped"]:
                        result_text += ", {} skipped".format(summary["skipped"])
                    set_setting("gcal_last_result", result_text)
                    flash(
                        f"Synced from Google Calendar: {summary['created']} new job(s), "
                        f"{summary['updated']} updated.",
                        "success",
                    )
                except Exception as exc:  # noqa: BLE001 — surface any fetch/parse error
                    flash(f"Sync failed: {exc}", "error")
        return redirect(url_for("settings"))

    last_iso = get_setting("gcal_last_sync")
    last_dt = None
    if last_iso:
        try:
            last_dt = datetime.fromisoformat(last_iso)
        except ValueError:
            last_dt = None
    return render_template(
        "settings.html",
        ical_url=get_setting("gcal_ical_url"),
        last_sync=last_dt,
        last_result=get_setting("gcal_last_result"),
    )


# ---------------------------------------------------------------- jobs

@app.route("/jobs")
def jobs_list():
    all_jobs = Job.query.order_by(Job.id.desc()).all()
    jobs_with_counts = [(job, job_counts(job)) for job in all_jobs]
    return render_template("jobs.html", jobs=jobs_with_counts)


@app.route("/jobs/new", methods=["GET", "POST"])
def job_new():
    if request.method == "POST":
        job_name = (request.form.get("job_name") or "").strip()
        client_name = (request.form.get("client_name") or "").strip()
        if not job_name or not client_name:
            flash("Job name and client are required.", "error")
        else:
            job = Job(
                job_name=job_name,
                client_name=client_name,
                location=(request.form.get("location") or "").strip(),
                setup_date=parse_date(request.form.get("setup_date")),
                collection_date=parse_date(request.form.get("collection_date")),
                status="Setup in Progress",
            )
            db.session.add(job)
            db.session.commit()
            flash(f"Job “{job.job_name}” created — ready for setup scanning.", "success")
            return redirect(url_for("job_detail", job_id=job.id))
    return render_template("job_new.html", today=date.today().isoformat())


@app.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def job_edit(job_id):
    job = get_job_or_404(job_id)
    if request.method == "POST":
        job_name = (request.form.get("job_name") or "").strip()
        client_name = (request.form.get("client_name") or "").strip()
        if not job_name:
            flash("Job name is required.", "error")
        else:
            job.job_name = job_name
            job.client_name = client_name
            job.location = (request.form.get("location") or "").strip()
            job.setup_date = parse_date(request.form.get("setup_date"))
            job.collection_date = parse_date(request.form.get("collection_date"))
            db.session.commit()
            flash("Job details updated.", "success")
            return redirect(url_for("job_detail", job_id=job.id))
    return render_template("job_edit.html", job=job)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    job = get_job_or_404(job_id)
    rows, counts = kit_state(job)
    # Until collection is finalized an unscanned item is merely "awaiting";
    # once the job closes it is genuinely missing.
    finalized = job.status in ("Completed", "Items Missing")
    return render_template(
        "job_detail.html", job=job, rows=rows, counts=counts, finalized=finalized
    )


@app.post("/jobs/<int:job_id>/setup/reopen")
def setup_reopen(job_id):
    # Escape hatch: one accidental collection scan flips a job to
    # "Collection in Progress" and locks setup scanning; this undoes that.
    job = get_job_or_404(job_id)
    if job.status == "Collection in Progress":
        job.status = "Live"
        db.session.commit()
        flash("Setup scanning reopened — the job is back to Live.", "info")
    return redirect(url_for("job_detail", job_id=job.id))


@app.post("/jobs/<int:job_id>/setup/complete")
def setup_complete(job_id):
    job = get_job_or_404(job_id)
    if job.status == "Setup in Progress":
        job.status = "Live"
        db.session.commit()
        flash("Setup complete — job is now live.", "success")
    return redirect(url_for("job_detail", job_id=job.id))


@app.post("/jobs/<int:job_id>/collection/complete")
def collection_complete(job_id):
    job = get_job_or_404(job_id)
    if job.status == "Completed":
        flash("This job is already completed.", "info")
        return redirect(url_for("job_detail", job_id=job.id))

    rows, counts = kit_state(job)
    if counts["expected"] == 0:
        job.status = "Completed"
        db.session.commit()
        flash("No items were ever scanned onto this job — closed as completed.", "info")
        return redirect(url_for("job_detail", job_id=job.id))

    missing_rows = [row for row in rows if row["collection"] is None]
    flagged = []
    for row in missing_rows:
        equipment = row["equipment"]
        last = equipment.last_scan()
        # If the item's most recent scan belongs to a different job it has
        # since been redeployed (e.g. found and setup-scanned elsewhere) —
        # don't clobber its live status from here.
        if last is not None and last.job_id != job.id:
            continue
        equipment.status = "Missing"
        flagged.append(equipment)
    job.status = "Items Missing" if missing_rows else "Completed"
    db.session.commit()

    if flagged:
        names = ", ".join(equipment.kit_id for equipment in flagged)
        flash(
            f"Collection closed with {len(flagged)} item(s) flagged MISSING: {names}",
            "error",
        )
    elif missing_rows:
        flash(
            "Collection closed. Uncollected items are already accounted for on other jobs.",
            "info",
        )
    else:
        flash("Collection complete — all items back in the warehouse. ✅", "success")
    return redirect(url_for("job_detail", job_id=job.id))


# ---------------------------------------------------------------- scan modes

@app.route("/setup")
def setup_pick():
    eligible = (
        Job.query.filter(Job.status.in_(["Setup in Progress", "Live"]))
        .order_by(Job.id.desc())
        .all()
    )
    return render_template(
        "pick_job.html",
        jobs=eligible,
        mode="setup",
        title="Setup mode — pick a job",
        empty_hint="No jobs are open for setup. Create a new job first.",
    )


@app.route("/collection")
def collection_pick():
    eligible = (
        Job.query.filter(
            Job.status.in_(
                ["Setup in Progress", "Live", "Collection in Progress", "Items Missing"]
            )
        )
        .order_by(Job.id.desc())
        .all()
    )
    return render_template(
        "pick_job.html",
        jobs=eligible,
        mode="collection",
        title="Collection mode — pick a job",
        empty_hint="No jobs are awaiting collection.",
    )


@app.route("/jobs/<int:job_id>/setup")
def setup_mode(job_id):
    job = get_job_or_404(job_id)
    rows, counts = kit_state(job)
    closed = job.status in ("Collection in Progress", "Completed", "Items Missing")
    # Newest first so the item just scanned appears at the top of the list.
    return render_template(
        "scan_setup.html",
        job=job,
        rows=list(reversed(rows)),
        counts=counts,
        closed=closed,
        staff=STAFF,
    )


@app.route("/jobs/<int:job_id>/collection")
def collection_mode(job_id):
    job = get_job_or_404(job_id)
    rows, counts = kit_state(job)
    closed = job.status == "Completed"
    return render_template(
        "scan_collection.html",
        job=job,
        rows=rows,
        counts=counts,
        closed=closed,
        staff=STAFF,
    )


# ---------------------------------------------------------------- scan API

@app.post("/api/scan")
def api_scan():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    try:
        job_id = int(data.get("job_id"))
    except (TypeError, ValueError):
        return jsonify(result="error", message="Bad job id."), 400
    if not 0 < job_id < 2**31:
        return jsonify(result="error", message="Job not found."), 404
    job = db.session.get(Job, job_id)
    if job is None:
        return jsonify(result="error", message="Job not found."), 404

    scan_type = data.get("scan_type")
    if scan_type not in ("SETUP", "COLLECTION"):
        return jsonify(result="error", message="Bad scan type."), 400

    staff_name = (data.get("staff_name") or "").strip()[:60]
    if not staff_name:
        return jsonify(result="error", message="Choose your name before scanning."), 400

    raw_code = (data.get("code") or "").strip()
    match = KIT_CODE_RE.match(raw_code)
    equipment = db.session.get(Equipment, int(match.group(1))) if match else None
    if equipment is None:
        shown = raw_code[:40] or "(empty)"
        return jsonify(
            result="not_recognized",
            message=f"“{shown}” not recognized — no matching item in the inventory.",
        )

    item = {
        "id": equipment.id,
        "kit_id": equipment.kit_id,
        "name": equipment.name,
        "category": equipment.category,
    }

    if scan_type == "SETUP":
        return _setup_scan(job, equipment, staff_name, item)
    return _collection_scan(job, equipment, staff_name, item)


def _setup_scan(job, equipment, staff_name, item):
    if job.status in ("Collection in Progress", "Completed", "Items Missing"):
        return (
            jsonify(
                result="error",
                message=f"Setup scanning is closed for this job ({job.status}).",
                item=item,
            ),
            409,
        )

    already = ScanEvent.query.filter_by(
        job_id=job.id, equipment_id=equipment.id, scan_type="SETUP"
    ).first()
    if already is not None:
        _, counts = kit_state(job)
        return jsonify(
            result="duplicate",
            message=f"{equipment.name} ({equipment.kit_id}) is already on the kit list.",
            item=item,
            counts=counts,
        )

    if equipment.status == "Out on Job":
        elsewhere = (
            ScanEvent.query.filter_by(equipment_id=equipment.id, scan_type="SETUP")
            .order_by(ScanEvent.timestamp.desc(), ScanEvent.id.desc())
            .first()
        )
        if elsewhere is not None and elsewhere.job_id != job.id:
            return jsonify(
                result="on_other_job",
                message=(
                    f"{equipment.name} ({equipment.kit_id}) is still out on "
                    f"“{elsewhere.job.job_name}” — collect it there first."
                ),
                item=item,
            )

    db.session.add(
        ScanEvent(
            job_id=job.id,
            equipment_id=equipment.id,
            scan_type="SETUP",
            staff_name=staff_name,
        )
    )
    equipment.status = "Out on Job"
    try:
        db.session.commit()
    except IntegrityError:
        # A concurrent scan of the same label won the race — treat as duplicate.
        db.session.rollback()
        _, counts = kit_state(job)
        return jsonify(
            result="duplicate",
            message=f"{equipment.name} ({equipment.kit_id}) is already on the kit list.",
            item=item,
            counts=counts,
        )
    _, counts = kit_state(job)
    return jsonify(
        result="added",
        message=f"{equipment.name} ({equipment.kit_id}) added to kit list.",
        item=item,
        counts=counts,
    )


def _collection_scan(job, equipment, staff_name, item):
    on_kit_list = ScanEvent.query.filter_by(
        job_id=job.id, equipment_id=equipment.id, scan_type="SETUP"
    ).first()
    if on_kit_list is None:
        return jsonify(
            result="not_expected",
            message=f"{equipment.name} ({equipment.kit_id}) is NOT on this job's kit list.",
            item=item,
        )

    already = ScanEvent.query.filter_by(
        job_id=job.id, equipment_id=equipment.id, scan_type="COLLECTION"
    ).first()
    if already is not None:
        _, counts = kit_state(job)
        return jsonify(
            result="duplicate",
            message=f"{equipment.name} ({equipment.kit_id}) was already collected.",
            item=item,
            counts=counts,
        )

    db.session.add(
        ScanEvent(
            job_id=job.id,
            equipment_id=equipment.id,
            scan_type="COLLECTION",
            staff_name=staff_name,
        )
    )
    equipment.status = "In Warehouse"
    if job.status in ("Setup in Progress", "Live"):
        job.status = "Collection in Progress"
    try:
        db.session.flush()
    except IntegrityError:
        # A concurrent scan of the same label won the race — treat as duplicate.
        db.session.rollback()
        _, counts = kit_state(job)
        return jsonify(
            result="duplicate",
            message=f"{equipment.name} ({equipment.kit_id}) was already collected.",
            item=item,
            counts=counts,
        )

    # A late scan on an "Items Missing" job can clear the last missing item,
    # at which point the job is genuinely complete.
    rows, counts = kit_state(job)
    if job.status == "Items Missing" and all(row["collection"] for row in rows):
        job.status = "Completed"
    db.session.commit()

    return jsonify(
        result="collected",
        message=f"{equipment.name} ({equipment.kit_id}) collected. ✅",
        item=item,
        counts=counts,
        job_status=job.status,
    )


# ---------------------------------------------------------------- equipment

@app.route("/equipment")
def equipment_list():
    category = request.args.get("category", "")
    status = request.args.get("status", "")
    query = Equipment.query
    if category in CATEGORIES:
        query = query.filter_by(category=category)
    if status in EQUIPMENT_STATUSES:
        query = query.filter_by(status=status)
    items = query.order_by(Equipment.id).all()
    return render_template(
        "equipment_list.html",
        items=items,
        categories=CATEGORIES,
        statuses=EQUIPMENT_STATUSES,
        selected_category=category,
        selected_status=status,
    )


@app.route("/equipment/new", methods=["GET", "POST"])
def equipment_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        category = request.form.get("category")
        if category not in CATEGORIES:
            category = "Other"
        if not name:
            flash("Equipment name is required.", "error")
        else:
            equipment = Equipment(name=name, category=category)
            db.session.add(equipment)
            db.session.commit()
            flash(f"{equipment.name} added as {equipment.kit_id}.", "success")
            return redirect(url_for("equipment_label", equipment_id=equipment.id))
    return render_template("equipment_new.html", categories=CATEGORIES)


@app.route("/equipment/<int:equipment_id>/label")
def equipment_label(equipment_id):
    equipment = db.session.get(Equipment, equipment_id)
    if equipment is None:
        abort(404)
    return render_template("equipment_label.html", equipment=equipment)


@app.route("/equipment/<int:equipment_id>/qr.png")
def equipment_qr(equipment_id):
    equipment = db.session.get(Equipment, equipment_id)
    if equipment is None:
        abort(404)
    qr = qrcode.QRCode(
        box_size=12,
        border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    qr.add_data(equipment.kit_id)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


# ---------------------------------------------------------------- missing report

@app.route("/missing")
def missing_report():
    missing_items = (
        Equipment.query.filter_by(status="Missing").order_by(Equipment.id).all()
    )
    rows = []
    for equipment in missing_items:
        scan = equipment.last_scan()
        rows.append(
            {
                "equipment": equipment,
                "scan": scan,
                "job": scan.job if scan else None,
            }
        )
    return render_template("missing_report.html", rows=rows)


if __name__ == "__main__":
    # Local dev server. In production Kit Tracker is served by gunicorn
    # (see Procfile) which imports `app` directly and never runs this block.
    # Camera access requires a secure context: localhost is fine in dev, but
    # phones on the LAN need HTTPS — see README for options.
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
