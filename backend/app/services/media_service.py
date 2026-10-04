from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from backend.app.db.database import assets_collection


def get_asset_file(asset_id: UUID) -> dict[str, Any]:
    """
    Retrieve the local file information for an indexed asset.
    """
    asset = assets_collection.find_one(
        {"id": str(asset_id)},
        {
            "_id": 0,
            "id": 1,
            "filename": 1,
            "original_path": 1,
            "file_type": 1,
            "mime_type": 1,
        },
    )

    if not asset:
        raise ValueError(f"Asset not found: {asset_id}")

    path = Path(asset["original_path"])

    if not path.exists():
        clean_rel = str(asset["original_path"]).lstrip("/\\")
        candidates = [
            Path(clean_rel),
            Path("data") / f"{asset['file_type']}s" / asset["filename"],
            Path("data") / asset["filename"],
            Path.cwd() / clean_rel,
            Path.cwd() / "data" / f"{asset['file_type']}s" / asset["filename"],
        ]
        for candidate in candidates:
            if candidate.exists():
                path = candidate
                break

    if not path.exists():
        raise FileNotFoundError(
            f"Asset file does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Asset path is not a file: {path}"
        )

    return {
        "id": UUID(str(asset["id"])),
        "filename": asset["filename"],
        "original_path": path,
        "file_type": asset["file_type"],
        "mime_type": asset["mime_type"],
    }