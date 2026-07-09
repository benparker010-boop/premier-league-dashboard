"""Seed data so the app is testable immediately after setup."""
from datetime import date, timedelta

from models import Equipment, Job, ScanEvent, db

DEMO_EQUIPMENT = [
    ("QSC K12.2 Powered Speaker", "Speaker"),
    ("QSC K12.2 Powered Speaker", "Speaker"),
    ("XLR Cable 10m", "Cable"),
    ("XLR Cable 10m", "Cable"),
    ("Chauvet SlimPAR Uplight", "Light"),
    ("Chauvet SlimPAR Uplight", "Light"),
    ("Yamaha MG12XU Mixer", "Mixer"),
    ("K&M Speaker Stand", "Stand"),
    ("K&M Speaker Stand", "Stand"),
    ("6U Rack Case", "Case"),
    ("Shure SM58 Microphone", "Other"),
    ("13A Power Distro", "Other"),
]


def seed_if_empty():
    """Populate a fresh database with demo equipment and one in-flight job."""
    if Equipment.query.first() is not None or Job.query.first() is not None:
        return

    items = [Equipment(name=name, category=category) for name, category in DEMO_EQUIPMENT]
    db.session.add_all(items)
    db.session.flush()

    job = Job(
        job_name="Spring Gala (demo job)",
        client_name="Riverside Hotel",
        location="Riverside Hotel Ballroom, Bristol",
        setup_date=date.today(),
        collection_date=date.today() + timedelta(days=1),
        status="Live",
    )
    db.session.add(job)
    db.session.flush()

    # Seven items were setup-scanned onto the demo job, so collection mode
    # has a real kit list to tick off straight away.
    for equipment in items[:7]:
        db.session.add(
            ScanEvent(
                equipment_id=equipment.id,
                job_id=job.id,
                scan_type="SETUP",
                staff_name="Alex",
            )
        )
        equipment.status = "Out on Job"

    db.session.commit()
