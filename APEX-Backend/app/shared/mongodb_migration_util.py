import logging
import asyncio
from typing import Any, List

from sqlalchemy import select
from sqlalchemy.orm import Session
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.infrastructure.persistence.database import engine
from app.infrastructure.persistence import models as pg_models
from app.infrastructure.persistence.mongodb import mongodb_manager

logger = logging.getLogger(__name__)

async def migrate_users(pg_db: Session, mongo_db: AsyncIOMotorDatabase, dry_run: bool = True):
    """Migrate users from PostgreSQL to MongoDB."""
    print("Migrating users...")
    logger.info("Migrating users...")
    stmt = select(pg_models.User)
    users = pg_db.execute(stmt).scalars().all()

    count = 0
    for user in users:
        user_doc = {
            "_id": str(user.id), # Use PG ID as string _id for easy mapping
            "full_name": user.full_name,
            "email": user.email,
            "password_hash": user.password_hash,
            "auth_provider": user.auth_provider,
            "auth_providers": [user.auth_provider],
            "provider_user_id": user.provider_user_id,
            "profile_image": user.profile_image,
            "role": user.role,
            "is_active": user.is_active,
            "is_email_verified": user.is_email_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login_at": user.last_login_at,
        }

        if not dry_run:
            await mongo_db.users.update_one(
                {"email": user.email},
                {"$set": user_doc},
                upsert=True
            )
        count += 1

    logger.info("User migration %s: %d records processed.", "dry-run" if dry_run else "complete", count)

async def migrate_job_owners(pg_db: Session, mongo_db: AsyncIOMotorDatabase, dry_run: bool = True):
    """Migrate migration_job_owners from PostgreSQL to MongoDB."""
    logger.info("Migrating job owners...")
    stmt = select(pg_models.MigrationJobOwner)
    owners = pg_db.execute(stmt).scalars().all()

    count = 0
    for owner in owners:
        owner_doc = {
            "job_id": owner.job_id,
            "user_id": str(owner.user_id),
            "created_at": owner.created_at
        }

        if not dry_run:
            await mongo_db.migration_job_owners.update_one(
                {"job_id": owner.job_id},
                {"$set": owner_doc},
                upsert=True
            )
        count += 1
    logger.info("Job owner migration %s: %d records processed.", "dry-run" if dry_run else "complete", count)

async def migrate_reports(pg_db: Session, mongo_db: AsyncIOMotorDatabase, dry_run: bool = True):
    """Migrate persisted_migration_reports from PostgreSQL to MongoDB."""
    logger.info("Migrating migration reports...")
    import json
    stmt = select(pg_models.PersistedMigrationReport)
    reports = pg_db.execute(stmt).scalars().all()

    count = 0
    for report in reports:
        try:
            report_data = json.loads(report.report_json)
        except Exception:
            report_data = {}

        report_doc = {
            "job_id": report.job_id,
            "status": report.status,
            "progress_percent": report.progress_percent,
            "current_step": report.current_step,
            "report_json": report_data,
            "updated_at": report.updated_at
        }

        if not dry_run:
            await mongo_db.migration_reports.update_one(
                {"job_id": report.job_id},
                {"$set": report_doc},
                upsert=True
            )
        count += 1
    logger.info("Migration report migration %s: %d records processed.", "dry-run" if dry_run else "complete", count)

async def run_migration(dry_run: bool = True):
    """Main entry point for data migration."""
    await mongodb_manager.connect()
    mongo_db = mongodb_manager.db

    with Session(engine) as pg_db:
        await migrate_users(pg_db, mongo_db, dry_run)
        await migrate_job_owners(pg_db, mongo_db, dry_run)
        await migrate_reports(pg_db, mongo_db, dry_run)
        # (Add other migrations here: tokens, test states, etc.)

    mongodb_manager.close()

if __name__ == "__main__":
    import sys
    is_dry = "--execute" not in sys.argv
    asyncio.run(run_migration(dry_run=is_dry))
