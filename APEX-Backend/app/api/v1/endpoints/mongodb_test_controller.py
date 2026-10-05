import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.infrastructure.persistence.mongodb import get_mongodb

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mongodb-test"])

@router.get("/mongodb/health")
async def mongodb_health(db = Depends(get_mongodb)):
    """Simple endpoint to verify MongoDB connectivity."""
    if db is None:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": "MongoDB is not initialized."}
        )

    try:
        # Perform a ping to verify connection
        await db.command("ping")

        # List collections
        collections = await db.list_collection_names()

        return {
            "status": "ok",
            "database": db.name,
            "collections_found": len(collections)
        }
    except Exception as e:
        logger.error("MongoDB health check failed: %s", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
