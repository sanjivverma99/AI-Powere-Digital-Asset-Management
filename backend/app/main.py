import logging
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client.http.exceptions import ApiException, ResponseHandlingException

from backend.app.db.database import (
    assets_collection,
    indexing_jobs_collection,
    ping_database,
    utc_now,
)
from backend.app.services.indexing_service import (
    create_indexing_job,
    index_asset,
)
from backend.app.services.embedding_service import get_ollama_status
from backend.app.services.media_service import get_asset_file
from backend.app.services.ollama_service import generate_image_description
from backend.app.services.qdrant_service import (
    ensure_collection,
    get_collection_info,
)
from backend.app.services.scanner_service import scan_library
from backend.app.services.search_service import search_assets


logger = logging.getLogger(__name__)


app = FastAPI(
    title="AI-Powered Digital Asset Management",
    version="0.1.0",
)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "AI-Powered Digital Asset Management Backend is running!",
        "docs_url": "http://localhost:8000/docs",
        "health_url": "http://localhost:8000/health",
        "endpoints": {
            "search": "/search?q={query}",
            "health": "/health",
            "database_health": "/health/database",
            "qdrant_health": "/health/qdrant",
        },
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ai-dam-api",
    }


@app.get("/health/ai")
def ai_health_check():
    return get_ollama_status()


@app.get("/health/database")
def database_health_check():
    ping_database()

    return {
        "status": "ok",
        "database": "mongodb",
    }


@app.get("/health/qdrant")
def qdrant_health_check():
    try:
        ensure_collection()
        info = get_collection_info()
    except (ApiException, ResponseHandlingException) as exc:
        logger.exception("Qdrant health check failed.")
        raise HTTPException(
            status_code=503,
            detail=(
                "Qdrant is unavailable. Start it with `docker compose up -d qdrant` "
                "or run `start-qdrant.ps1`, then retry."
            ),
        ) from exc

    return {
        "status": "ok",
        "collection": "asset_embeddings",
        "vectors_count": info.points_count,
        "vector_size": 768,
    }


# ---------------------------------------------------------
# LIBRARY SCANNING
# ---------------------------------------------------------


@app.post("/index/scan")
def scan_assets():
    return scan_library("data")


# ---------------------------------------------------------
# BACKGROUND INDEXING
# ---------------------------------------------------------


def run_indexing_job(job_id: UUID, *, force: bool = False) -> None:
    """
    Process queued assets in bounded batches.

    Processes in batches of 50 to boundedly handle large directories
    with hundreds or thousands of files, updating persistent job progress.
    """
    while True:
        assets = assets_collection.find(
            {"status": "pending"},
            {"_id": 0, "id": 1},
        ).sort("created_at", 1).limit(50)

        asset_ids = [asset["id"] for asset in assets]
        if not asset_ids:
            break

        for asset_id in asset_ids:
            try:
                index_asset(
                    UUID(str(asset_id)),
                    job_id=job_id,
                    force=force,
                )
            except Exception:
                # index_asset records failure in DB and updates job counts
                continue


@app.post("/index/start")
def start_indexing(
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    """
    Start background indexing for pending assets, or all assets when forced.

    Returns the job ID immediately so the frontend can poll
    /index/jobs/{job_id} for progress.
    """
    if force:
        assets_collection.update_many(
            {},
            {
                "$set": {
                    "status": "pending",
                    "error_message": None,
                    "updated_at": utc_now(),
                }
            },
        )
    else:
        assets_collection.update_many(
            {"status": {"$in": ["ai_processing", "ai_processed"]}},
            {"$set": {"status": "pending", "updated_at": utc_now()}},
        )

    total_files = assets_collection.count_documents({"status": "pending"})

    job_id = create_indexing_job(
        total_files=total_files
    )

    # No assets need processing.
    if total_files == 0:
        indexing_jobs_collection.update_one(
            {"id": str(job_id)},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": utc_now(),
                }
            },
        )

        return {
            "status": "completed",
            "job_id": str(job_id),
            "total_files": 0,
            "message": "All assets are already indexed.",
        }

    background_tasks.add_task(
        run_indexing_job,
        job_id,
        force=force,
    )

    return {
        "status": "started",
        "job_id": str(job_id),
        "total_files": total_files,
    }


@app.get("/index/jobs/{job_id}")
def get_indexing_job_status(job_id: UUID):
    """
    Return the persistent progress of an indexing job.
    """
    job = indexing_jobs_collection.find_one(
        {"id": str(job_id)},
        {"_id": 0},
    )

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Indexing job not found",
        )

    total_files = int(job["total_files"])
    processed_files = int(job["processed_files"])

    if total_files > 0:
        progress_percent = round(
            (processed_files / total_files) * 100,
            2,
        )
    else:
        progress_percent = 100.0

    return {
        "id": str(job["id"]),
        "total_files": total_files,
        "processed_files": processed_files,
        "successful_files": int(job["successful_files"]),
        "failed_files": int(job["failed_files"]),
        "skipped_files": int(job["skipped_files"]),
        "status": job["status"],
        "progress_percent": progress_percent,
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "created_at": job["created_at"],
    }


# ---------------------------------------------------------
# DIRECT IMAGE ANALYSIS
# ---------------------------------------------------------


@app.post("/assets/{asset_id}/analyze")
def analyze_asset(asset_id: UUID):
    asset = assets_collection.find_one(
        {"id": str(asset_id)},
        {
            "_id": 0,
            "id": 1,
            "original_path": 1,
            "file_type": 1,
        },
    )

    if not asset:
        raise HTTPException(
            status_code=404,
            detail="Asset not found",
        )

    if asset["file_type"] != "image":
        raise HTTPException(
            status_code=400,
            detail="This endpoint currently supports images only.",
        )

    try:
        description = generate_image_description(
            asset["original_path"]
        )

        assets_collection.update_one(
            {"id": str(asset_id)},
            {
                "$set": {
                    "description": description,
                    "status": "ai_processed",
                    "error_message": None,
                    "updated_at": utc_now(),
                }
            },
        )

        return {
            "status": "ok",
            "asset_id": str(asset_id),
            "description": description,
        }

    except Exception as exc:
        assets_collection.update_one(
            {"id": str(asset_id)},
            {
                "$set": {
                    "status": "failed",
                    "error_message": str(exc),
                    "updated_at": utc_now(),
                }
            },
        )

        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {exc}",
        )


# ---------------------------------------------------------
# SEMANTIC SEARCH
# ---------------------------------------------------------


@app.get("/search")
def search(
    q: str,
    limit: int = 10,
    file_type: str | None = None,
):
    try:
        return {
            "query": q,
            "results": search_assets(
                q,
                limit=limit,
                file_type=file_type,
            ),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )
    except (ApiException, ResponseHandlingException) as exc:
        logger.exception("Search failed because Qdrant is unavailable.")
        raise HTTPException(
            status_code=503,
            detail=(
                "Search is temporarily unavailable because Qdrant cannot be reached. "
                "Start it with `docker compose up -d qdrant` or run "
                "`start-qdrant.ps1`, then retry."
            ),
        ) from exc


# ---------------------------------------------------------
# ORIGINAL FILE / PREVIEW
# ---------------------------------------------------------


@app.get("/assets/{asset_id}/file")
def get_asset_file_response(asset_id: UUID):
    try:
        asset = get_asset_file(asset_id)

        return FileResponse(
            path=asset["original_path"],
            media_type=asset["mime_type"],
            filename=asset["filename"],
            content_disposition_type="inline",
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )