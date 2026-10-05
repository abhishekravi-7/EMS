"""Aggregates all v1 endpoint routers.

Connect, Discovery, and Migration Config endpoints are wired. Later stages
(strategy, start-migration, result) register their routers here.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin_settings_controller,
    auth_controller,
    connect_controller,
    discovery_controller,
    docs_controller,
    existing_test_controller,
    existing_test_report_controller,
    migration_config_controller,
    migration_execution_controller,
    proposed_test_controller,
    support_controller,
    unit_test_controller,
    user_settings_controller,
)

api_router = APIRouter()
api_router.include_router(auth_controller.router)
api_router.include_router(connect_controller.router)
api_router.include_router(discovery_controller.router)
api_router.include_router(migration_config_controller.router)
api_router.include_router(migration_execution_controller.router)
api_router.include_router(docs_controller.router)
api_router.include_router(support_controller.router)
api_router.include_router(unit_test_controller.router)
api_router.include_router(existing_test_controller.router)
api_router.include_router(existing_test_report_controller.router)
api_router.include_router(proposed_test_controller.router)
api_router.include_router(admin_settings_controller.router)
api_router.include_router(user_settings_controller.router)
