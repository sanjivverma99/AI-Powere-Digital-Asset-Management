from __future__ import annotations

import re
from typing import Any

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
)
from backend.app.db.database import assets_collection
from backend.app.services.embedding_service import generate_embedding
from backend.app.services.qdrant_service import (
    COLLECTION_NAME,
    client,
    ensure_collection,
)


MIN_RELEVANCE_SCORE = 0.50

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in",
    "into", "of", "on", "or", "the", "to", "with", "show", "showing",
    "find", "looking", "related",
}


def _tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    return {
        token[:-1] if len(token) > 4 and token.endswith("s") else token
        for token in tokens
    }


def _detect_media_intent(query_words: list[str]) -> str | None:
    """Detect whether query explicitly asks for images, videos, or brochures/documents."""
    q_set = set(query_words)
    image_keywords = {"image", "images", "photo", "photos", "picture", "pictures", "photograph", "photographs"}
    video_keywords = {"video", "videos", "clip", "clips", "footage", "movie", "movies"}
    pdf_keywords = {"pdf", "pdfs", "brochure", "brochures", "document", "documents", "report", "reports", "guideline", "guidelines"}

    if q_set & image_keywords:
        return "image"
    if q_set & video_keywords:
        return "video"
    if q_set & pdf_keywords:
        return "pdf"
    return None


def _build_text_score(description: str, filename: str, tags: list[str], query_words: list[str], raw_query: str) -> float:
    """
    Compute a high-accuracy text relevance score for hybrid re-ranking.
    Returns a value in [0, 1].
    """
    if not query_words and not raw_query:
        return 0.0

    terms = {
        token
        for token in _tokens(" ".join(query_words))
        if token not in _STOP_WORDS
    }
    if not terms:
        return 0.0

    description_tokens = _tokens(description or "")
    filename_tokens = _tokens(filename or "")
    tag_tokens = _tokens(" ".join(str(tag) for tag in tags or []))
    matched = sum(
        1.0 if term in description_tokens else
        0.8 if term in tag_tokens else
        0.35 if term in filename_tokens else
        0.0
        for term in terms
    )
    score = matched / len(terms)

    normalized_query = " ".join(
        token for token in re.findall(r"[a-z0-9]+", raw_query.lower())
        if token not in _STOP_WORDS
    )
    normalized_description = " ".join(
        re.findall(r"[a-z0-9]+", (description or "").lower())
    )
    if normalized_query and normalized_query in normalized_description:
        score += 0.2

    return min(1.0, score)


def search_assets(
    query: str,
    *,
    limit: int = 10,
    file_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    Perform semantic vector search and enrich with MongoDB metadata.

    Scoring strategy:
    - Primary score: Qdrant cosine similarity (vector relevance)
    - Secondary: lightweight text match bonus on description/filename/tags
    - Combined score uses semantic similarity and exact-token text relevance
    - Results are filtered by a minimum relevance score and re-ranked
    - Falls back to MongoDB keyword/tag search if vector store has no matches above threshold
    """
    query = query.strip()

    if not query:
        raise ValueError("Search query cannot be empty.")

    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100.")

    ensure_collection()

    query_filter = None
    if file_type:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="file_type",
                    match=MatchValue(value=file_type),
                )
            ]
        )

    # Extract individual query words for hybrid text matching
    query_words = [
        word for word in re.findall(r"[a-z0-9]+", query.lower())
        if word not in _STOP_WORDS
    ]
    query_vector = generate_embedding(query)
    raw_limit = min(limit * 10, 200)
    points = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=query_filter,
        with_payload=True,
        limit=raw_limit,
    ).points

    if points:
        asset_ids = [
            str(point.payload["asset_id"])
            for point in points
            if point.payload and point.payload.get("asset_id")
        ]
        assets_by_id = {
            asset["id"]: asset
            for asset in assets_collection.find(
                {
                    "id": {"$in": asset_ids},
                    "status": "indexed",
                },
                {"_id": 0},
            )
        }

        results: list[dict[str, Any]] = []
        media_intent = _detect_media_intent(query_words)
        for point in points:
            payload = point.payload or {}
            asset = assets_by_id.get(str(payload.get("asset_id")))
            if not asset:
                continue

            text_score = _build_text_score(
                asset.get("description", "") or "",
                asset.get("filename", "") or "",
                asset.get("tags") or [],
                query_words,
                query,
            )
            base_score = 0.7 * float(point.score) + 0.3 * text_score
            if base_score < MIN_RELEVANCE_SCORE:
                continue
            intent_bonus = 0.0
            if media_intent and not file_type:
                intent_bonus = (
                    0.04 if asset.get("file_type") == media_intent else -0.04
                )
            combined_score = round(max(0.0, base_score + intent_bonus), 4)
            results.append(
                {
                    "asset_id": str(asset["id"]),
                    "filename": asset["filename"],
                    "file_type": asset["file_type"],
                    "mime_type": asset.get("mime_type"),
                    "size_bytes": asset.get("size_bytes"),
                    "width": asset.get("width"),
                    "height": asset.get("height"),
                    "duration_seconds": asset.get("duration_seconds"),
                    "frame_rate": asset.get("frame_rate"),
                    "page_count": asset.get("page_count"),
                    "description": asset.get("description"),
                    "status": asset["status"],
                    "original_path": asset.get("original_path"),
                    "score": combined_score,
                }
            )

        results.sort(key=lambda result: result["score"], reverse=True)
        if results[:limit]:
            return results[:limit]

    patterns = [rf"\b{re.escape(word)}\b" for word in query_words]
    if not patterns:
        return []
    fallback_filter: dict[str, Any] = {
        "status": "indexed",
        "$or": [
            {field: {"$regex": pattern, "$options": "i"}}
            for pattern in patterns
            for field in ("description", "filename", "tags")
        ],
    }
    if file_type:
        fallback_filter["file_type"] = file_type

    fallback_results: list[dict[str, Any]] = []
    min_text_score = max(
        MIN_RELEVANCE_SCORE,
        0.25 if len(query_words) > 1 else 0.35,
    )
    for asset in assets_collection.find(fallback_filter, {"_id": 0}).limit(500):
        text_score = _build_text_score(
            asset.get("description", "") or "",
            asset.get("filename", "") or "",
            asset.get("tags") or [],
            query_words,
            query,
        )
        if text_score < min_text_score:
            continue
        fallback_results.append(
            {
                "asset_id": str(asset["id"]),
                "filename": asset["filename"],
                "file_type": asset["file_type"],
                "mime_type": asset.get("mime_type"),
                "size_bytes": asset.get("size_bytes"),
                "width": asset.get("width"),
                "height": asset.get("height"),
                "duration_seconds": asset.get("duration_seconds"),
                "frame_rate": asset.get("frame_rate"),
                "page_count": asset.get("page_count"),
                "description": asset.get("description"),
                "status": asset["status"],
                "original_path": asset.get("original_path"),
                "score": round(text_score, 4),
            }
        )

    fallback_results.sort(key=lambda result: result["score"], reverse=True)
    return fallback_results[:limit]