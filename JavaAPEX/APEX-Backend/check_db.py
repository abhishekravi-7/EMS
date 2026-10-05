import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add current dir to path to import app
sys.path.append(os.getcwd())

from app.core.config import settings
from app.infrastructure.persistence.models import LLMTokenUsage


def check():
    print(f"Connecting to: {settings.database_url}")
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        count = db.query(LLMTokenUsage).count()
        print(f"Total LLMTokenUsage records: {count}")

        if count > 0:
            first = db.query(LLMTokenUsage).first()
            print(f"First record: ID={first.id}, Created={first.created_at}, Provider={first.provider}")
    except Exception as e:  # noqa: BLE001
        print(f"Error querying LLMTokenUsage: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check()
