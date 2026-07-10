"""Database models for Kit Tracker."""
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

CATEGORIES = ["Speaker", "Cable", "Light", "Mixer", "Stand", "Case", "Other"]

EQUIPMENT_STATUSES = ["In Warehouse", "Out on Job", "Missing"]

JOB_STATUSES = [
    "Setup in Progress",
    "Live",
    "Collection in Progress",
    "Completed",
    "Items Missing",
]

SCAN_TYPES = ["SETUP", "COLLECTION"]

# No accounts by design — scans are attributed to a name picked from this list.
STAFF = ["Alex", "Ben", "Chloe", "Dan", "Priya", "Sam"]


def utcnow():
    # Stored naive-UTC: SQLite has no timezone type, and mixing aware/naive
    # datetimes breaks comparisons on values read back from the DB.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Equipment(db.Model):
    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(20), nullable=False, default="Other")
    status = db.Column(db.String(20), nullable=False, default="In Warehouse")
    date_added = db.Column(db.DateTime, nullable=False, default=utcnow)

    scans = db.relationship("ScanEvent", back_populates="equipment", lazy="dynamic")

    @property
    def kit_id(self):
        """The human-readable ID encoded in this item's QR label, e.g. KIT-0042."""
        return f"KIT-{self.id:04d}"

    def last_scan(self):
        return self.scans.order_by(
            ScanEvent.timestamp.desc(), ScanEvent.id.desc()
        ).first()


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(120), nullable=False)
    client_name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(200), nullable=False, default="")
    setup_date = db.Column(db.Date, nullable=True)
    collection_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Setup in Progress")
    # UID of the Google Calendar event this job was imported from, if any —
    # lets a re-sync update the same job instead of duplicating it.
    source_uid = db.Column(db.String(255), nullable=True, index=True)

    scans = db.relationship("ScanEvent", back_populates="job", lazy="dynamic")


class ScanEvent(db.Model):
    __tablename__ = "scan_events"
    __table_args__ = (
        # One SETUP and one COLLECTION scan per item per job — enforced at the
        # DB layer so concurrent double-submits can't slip past the app check.
        db.UniqueConstraint("job_id", "equipment_id", "scan_type", name="uq_scan_once"),
    )

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.id"), nullable=False, index=True
    )
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    scan_type = db.Column(db.String(10), nullable=False)  # SETUP | COLLECTION
    staff_name = db.Column(db.String(60), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    equipment = db.relationship("Equipment", back_populates="scans")
    job = db.relationship("Job", back_populates="scans")


class AppSetting(db.Model):
    """Simple key/value store for runtime config (e.g. the calendar link)."""

    __tablename__ = "app_settings"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")
