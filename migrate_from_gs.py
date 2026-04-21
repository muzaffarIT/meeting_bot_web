import logging
from sheets import get_all_leads, get_all_users, get_settings_raw
from db_models import SessionLocal, Lead, User, Setting
from sqlalchemy.exc import IntegrityError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    # Step 1: fetch data BEFORE touching the DB — fail fast if GS is unavailable
    logger.info("Fetching leads from Google Sheets...")
    leads = get_all_leads()
    logger.info("Fetching users from Google Sheets...")
    users = get_all_users()
    logger.info("Fetching settings from Google Sheets...")
    settings = get_settings_raw()

    logger.info(f"Loaded {len(leads)} leads, {len(users)} users, {len(settings)} settings.")

    if not users:
        logger.warning("No users found in Google Sheets — aborting migration to avoid losing existing data.")
        return

    db = SessionLocal()
    try:
        # Step 2: wipe + insert in a single transaction
        db.query(Lead).delete()
        db.query(User).delete()
        db.query(Setting).delete()

        logger.info("Inserting Users into SQL DB...")
        for u in users:
            filtered = {k: str(v) for k, v in u.items() if hasattr(User, k)}
            db.add(User(**filtered))

        logger.info("Inserting Leads into SQL DB...")
        for l in leads:
            filtered = {k: str(v) for k, v in l.items() if hasattr(Lead, k)}
            db.add(Lead(**filtered))

        logger.info("Inserting Settings into SQL DB...")
        for k, v in settings.items():
            db.add(Setting(key=str(k), value=str(v)))

        db.commit()
        logger.info("Migration completed successfully!")
    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed, rolled back: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
