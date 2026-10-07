# Implementation Plan - Migration to MongoDB Atlas

Migration of authentication, authorization, and all application data from PostgreSQL and Firebase to MongoDB Atlas.

## User Review Required

> [!IMPORTANT]
> This migration will replace Firebase with a custom FastAPI authentication system. Existing users will need to reset their passwords as hashes cannot be migrated from Firebase.
> PostgreSQL will be kept as a secondary/read-only database during the transition.

## Batch 1: MongoDB Infrastructure

Establishing the core connection and lifecycle management for MongoDB.

### [MODIFY] [config.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/core/config.py)
- Add `AUTH_PROVIDER` and `PERSISTENCE_BACKEND` settings.
- Add MongoDB connection settings if missing (already partially present).
- Add JWT settings for custom authentication.

### [MODIFY] [mongodb.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/infrastructure/persistence/mongodb.py)
- Improve `MongoDBManager` with async connection, ping, and index setup.
- Add `get_db` dependency for MongoDB.

### [NEW] [indexes.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/infrastructure/persistence/mongodb_indexes.py)
- Idempotent index creation for all collections.

### [MODIFY] [main.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/main.py)
- Ensure MongoDB lifecycle is correctly integrated into `lifespan`.

## Batch 2: MongoDB Authentication

### [NEW] [user_repository.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/infrastructure/persistence/mongodb_user_repository.py)
- MongoDB-backed user storage.

### [NEW] [auth_service.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/application/services/mongodb_auth_service.py)
- Password hashing (Argon2id).
- JWT issuance and validation.

### [NEW] [auth_controller.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/api/v1/endpoints/mongodb_auth_controller.py)
- Signup, Login, Logout, Refresh endpoints.

## Batch 3: Authorization & Ownership

### [MODIFY] [deps.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/api/deps.py)
- Update `get_current_user` to support `mongodb` provider.
- Update `verify_job_ownership` to query MongoDB.

## Batch 4: Application Persistence

Migrating remaining repositories to MongoDB:
- `migration_jobs`
- `discovery_reports`
- `llm_token_usage`
- `migration_events`

## Batch 5: Data Migration Utility

### [NEW] [migration_util.py](file:///C:/Users/ST-SUBRAMANI/OneDrive%20-%20SORIM%20TECHNOLOGIES/Documents/JAVA_APEX/JavaAPEX/APEX-Backend/app/shared/mongodb_migration_util.py)
- Script to copy data from PostgreSQL to MongoDB.

## Verification Plan

### Automated Tests
- `pytest tests/unit/test_mongodb_auth.py`
- `pytest tests/integration/test_mongodb_persistence.py`

### Manual Verification
- Perform signup and login with the new system.
- Verify job ownership is enforced.
- Verify discovery results are correctly persisted in MongoDB.

## Rollback Strategy
- Keep `AUTH_PROVIDER=firebase` and `PERSISTENCE_BACKEND=postgres` as available configuration options.
- The logic will branched based on these settings.
