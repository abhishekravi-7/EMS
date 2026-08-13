import sys
import os

# Add the parent directory to sys.path so 'app' can be imported
sys.path.append(os.getcwd())

from app.infrastructure.persistence.database import engine
from sqlalchemy import text

indexes = [
    'ix_llm_token_usage_created_at',
    'ix_llm_token_usage_provider',
    'ix_llm_token_usage_model',
    'ix_llm_token_usage_status',
    'ix_llm_token_usage_user_id'
]

print("Connecting to database and dropping redundant indexes...")
with engine.connect() as conn:
    for index in indexes:
        print(f"Dropping index: {index}")
        conn.execute(text(f"DROP INDEX IF EXISTS {index};"))
    conn.commit()
print("Cleanup complete.")
