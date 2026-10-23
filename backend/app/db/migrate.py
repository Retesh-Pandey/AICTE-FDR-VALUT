"""
Safe, idempotent schema migration helper for SQLite and PostgreSQL.
Preserves existing data while adding new tables and columns required for
directory synchronization and institution onboarding.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.logging import logger
from app.db.session import Base


def run_safe_migrations(engine: Engine) -> None:
    """Safely apply schema additions without overwriting existing databases."""
    try:
        # 1. Ensure all new tables are created
        Base.metadata.create_all(bind=engine)

        # 2. Check and add missing columns on existing tables
        inspector = inspect(engine)

        if "institutions" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("institutions")]

            with engine.connect() as conn:
                if "source" not in columns:
                    logger.info("Migrating schema: adding 'source' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN source VARCHAR(100) DEFAULT 'PORTAL_REGISTRY'")
                    )
                    conn.commit()

                if "last_synced_at" not in columns:
                    logger.info("Migrating schema: adding 'last_synced_at' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN last_synced_at DATETIME")
                    )
                    conn.commit()

                if "upload_hold_active" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_active' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_active BOOLEAN DEFAULT 0")
                    )
                    conn.commit()

                if "upload_hold_until" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_until' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_until DATETIME")
                    )
                    conn.commit()

                if "upload_hold_reason" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_reason' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_reason TEXT")
                    )
                    conn.commit()

                if "upload_hold_placed_by" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_placed_by' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_placed_by CHAR(32)")
                    )
                    conn.commit()

                if "upload_hold_placed_at" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_placed_at' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_placed_at DATETIME")
                    )
                    conn.commit()

                if "upload_hold_appealed_at" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_appealed_at' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_appealed_at DATETIME")
                    )
                    conn.commit()

                if "upload_hold_appeal_reason" not in columns:
                    logger.info("Migrating schema: adding 'upload_hold_appeal_reason' column to 'institutions' table.")
                    conn.execute(
                        text("ALTER TABLE institutions ADD COLUMN upload_hold_appeal_reason TEXT")
                    )
                    conn.commit()

        logger.info("Safe schema migration check completed.")
    except Exception as e:
        logger.warning(f"Safe migration warning: {e}")
