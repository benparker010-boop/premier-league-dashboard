"""Kit Tracker — scan equipment out to jobs and back in again."""
import io
import re
from datetime import date, datetime

import qrcode
import qrcode.constants
from markupsafe import Markup, escape
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
    url_for,
)

from models import (
    CATEGORIES,
    EQUIPMENT_STATUSES,
    STAFF,
    Equipment,
    Job,
    ScanEvent,
    db,
)
from seed import seed_if_empty

app = Flask(__name__)
app.config["SECRET_KEY"] = "kit-tracker-dev"  # only used for flash messages
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///kit_tracker.sqlite"

db.init_app(app)

with app.app_context():
    db.create_all()
    seed_if_empty()

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
    return {"badge_class": lambda status: BADGE_CLASSES.get(status, "muted")}


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
    # Camera access requires a secure context: localhost is fine in dev, but
    # phones on the LAN need HTTPS — see README for options.
    app.run(debug=True, host="0.0.0.0", port=5000)
