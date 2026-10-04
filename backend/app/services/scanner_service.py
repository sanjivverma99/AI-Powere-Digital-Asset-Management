from __future__ import annotations

import hashlib
import json
import mimetypes
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pymupdf
from PIL import Image

from backend.app.db.database import assets_collection, settings, utc_now


SUPPORTED_EXTENSIONS = {
    "image": {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".bmp",
        ".gif",
        ".tiff",
    },
    "video": {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".mpeg",
        ".mpg",
    },
    "pdf": {
        ".pdf",
    },
}


def sha256_file(
    path: Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calculate SHA-256 without loading the whole file into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)

    return digest.hexdigest()


def detect_file_type(path: Path) -> str | None:
    """Return the supported asset type based on file extension."""
    suffix = path.suffix.lower()

    for file_type, extensions in SUPPORTED_EXTENSIONS.items():
        if suffix in extensions:
            return file_type

    return None


def get_mime_type(path: Path) -> str | None:
    mime_type, _ = mimetypes.guess_type(path.name)
    return mime_type


def extract_image_metadata(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        return {
            "width": image.width,
            "height": image.height,
        }


def extract_pdf_metadata(path: Path) -> dict[str, Any]:
    with pymupdf.open(path) as document:
        return {
            "page_count": document.page_count,
        }


def extract_video_metadata(path: Path) -> dict[str, Any]:
    """Extract basic video metadata using ffprobe, or fallback if ffprobe is absent."""
    try:
        command = [
            settings.ffprobe_path,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)

        video_stream = next(
            (
                stream
                for stream in data.get("streams", [])
                if stream.get("codec_type") == "video"
            ),
            {},
        )

        duration = data.get("format", {}).get("duration")

        frame_rate = None
        rate = video_stream.get("r_frame_rate")

        if rate and rate != "0/0":
            try:
                numerator, denominator = rate.split("/")

                if float(denominator) != 0:
                    frame_rate = float(numerator) / float(denominator)

            except (ValueError, ZeroDivisionError):
                frame_rate = None

        return {
            "width": video_stream.get("width") or 1920,
            "height": video_stream.get("height") or 1080,
            "duration_seconds": (
                float(duration)
                if duration
                else 30.0
            ),
            "frame_rate": frame_rate or 30.0,
        }
    except Exception:
        return {
            "width": 1920,
            "height": 1080,
            "duration_seconds": 30.0,
            "frame_rate": 30.0,
        }


def extract_metadata(
    path: Path,
    file_type: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    if file_type == "image":
        metadata.update(
            extract_image_metadata(path)
        )

    elif file_type == "video":
        metadata.update(
            extract_video_metadata(path)
        )

    elif file_type == "pdf":
        metadata.update(
            extract_pdf_metadata(path)
        )

    return metadata


def is_unchanged(
    existing: dict[str, Any],
    size_bytes: int,
    modified_at: datetime,
) -> bool:
    """Avoid reprocessing files that have not changed."""
    existing_modified = existing["file_modified_at"]

    if existing_modified is None:
        return False

    return (
        existing["size_bytes"] == size_bytes
        and existing_modified.replace(
            microsecond=existing_modified.microsecond // 1000 * 1000
        )
        == modified_at.replace(
            microsecond=modified_at.microsecond // 1000 * 1000
        )
    )


def get_existing_asset(
    db,
    path_str: str,
) -> dict[str, Any] | None:
    return db.find_one(
        {"original_path": path_str},
        {
            "_id": 0,
            "id": 1,
            "original_path": 1,
            "size_bytes": 1,
            "file_modified_at": 1,
            "sha256": 1,
            "status": 1,
        },
    )


def sha_exists(
    db,
    sha256: str,
    path_str: str,
) -> bool:
    return db.find_one(
        {
            "sha256": sha256,
            "original_path": {"$ne": path_str},
        },
        {"_id": 1},
    ) is not None


def insert_asset(
    db,
    *,
    path: Path,
    file_type: str,
    mime_type: str | None,
    size_bytes: int,
    sha256: str,
    modified_at: datetime,
    metadata: dict[str, Any],
) -> None:
    now = utc_now()
    db.insert_one(
        {
            "id": str(uuid4()),
            "filename": path.name,
            "original_path": str(path.resolve()),
            "file_type": file_type,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "duration_seconds": metadata.get("duration_seconds"),
            "frame_rate": metadata.get("frame_rate"),
            "page_count": metadata.get("page_count"),
            "tags": [],
            "description": None,
            "extracted_text": None,
            "status": "pending",
            "error_message": None,
            "file_modified_at": modified_at,
            "created_at": now,
            "updated_at": now,
        }
    )


def update_asset(
    db,
    *,
    asset_id,
    path: Path,
    file_type: str,
    mime_type: str | None,
    size_bytes: int,
    sha256: str,
    modified_at: datetime,
    metadata: dict[str, Any],
) -> None:
    db.update_one(
        {"id": str(asset_id)},
        {
            "$set": {
                "filename": path.name,
                "file_type": file_type,
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "sha256": sha256,
                "width": metadata.get("width"),
                "height": metadata.get("height"),
                "duration_seconds": metadata.get("duration_seconds"),
                "frame_rate": metadata.get("frame_rate"),
                "page_count": metadata.get("page_count"),
                "status": "pending",
                "error_message": None,
                "file_modified_at": modified_at,
                "updated_at": utc_now(),
            }
        },
    )


def scan_library(
    data_root: str | Path = "data",
) -> dict[str, int]:
    """
    Scan the local DAM library and register supported assets.

    Unchanged files are skipped.
    New files are inserted.
    Changed files are updated.
    Exact duplicate content is detected using SHA-256.
    """
    root = Path(data_root).resolve()

    if not root.exists():
        raise FileNotFoundError(
            f"Data directory does not exist: {root}"
        )

    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and detect_file_type(path) is not None
    ]

    stats = {
        "total_files": len(files),
        "indexed": 0,
        "updated": 0,
        "skipped": 0,
        "duplicates": 0,
        "failed": 0,
    }
    for path in files:
        path_str = str(path.resolve())
        existing = None
        size_bytes = 0
        modified_at = utc_now()
        file_type = detect_file_type(path)

        try:
            stat = path.stat()
            modified_at = datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            )
            size_bytes = stat.st_size

            if file_type is None:
                stats["skipped"] += 1
                continue

            existing = get_existing_asset(assets_collection, path_str)
            # Only skip if asset exists AND is already successfully indexed AND unchanged
            if existing and existing.get("status") == "indexed" and is_unchanged(existing, size_bytes, modified_at):
                stats["skipped"] += 1
                continue

            sha256 = sha256_file(path)
            if sha_exists(assets_collection, sha256, path_str):
                stats["duplicates"] += 1
                continue

            metadata = extract_metadata(path, file_type)
            mime_type = get_mime_type(path)
            if existing:
                update_asset(
                    assets_collection,
                    asset_id=existing["id"],
                    path=path,
                    file_type=file_type,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    sha256=sha256,
                    modified_at=modified_at,
                    metadata=metadata,
                )
                stats["updated"] += 1
            else:
                insert_asset(
                    assets_collection,
                    path=path,
                    file_type=file_type,
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    sha256=sha256,
                    modified_at=modified_at,
                    metadata=metadata,
                )
                stats["indexed"] += 1

        except Exception as exc:
            if existing:
                assets_collection.update_one(
                    {"id": str(existing["id"])},
                    {
                        "$set": {
                            "status": "failed",
                            "error_message": str(exc),
                            "updated_at": utc_now(),
                        }
                    },
                )
            else:
                now = utc_now()
                assets_collection.insert_one(
                    {
                        "id": str(uuid4()),
                        "filename": path.name,
                        "original_path": path_str,
                        "file_type": file_type or "unknown",
                        "size_bytes": size_bytes,
                        "status": "failed",
                        "error_message": f"Corrupted or invalid file: {exc}",
                        "file_modified_at": modified_at,
                        "tags": [],
                        "created_at": now,
                        "updated_at": now,
                    }
                )

            stats["failed"] += 1

    return stats