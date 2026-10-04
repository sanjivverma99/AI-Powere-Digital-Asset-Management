import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ResponseHandlingException

from backend.app import main
from backend.app.services import embedding_service, indexing_service
from backend.app.services import search_service
from backend.app.services.search_service import _build_text_score


def test_text_score_does_not_match_partial_words():
    score = _build_text_score(
        "A photograph of a quiet living room",
        "marketing-image.jpg",
        ["image", "photography", "room"],
        ["art"],
        "art",
    )

    assert score == 0


def test_text_score_prefers_assets_covering_more_query_terms():
    query_words = ["woman", "cat", "standing"]
    complete_match = _build_text_score(
        "A woman standing beside a cat",
        "asset.jpg",
        [],
        query_words,
        "A woman standing with a cat",
    )
    partial_match = _build_text_score(
        "A woman in a garden",
        "asset.jpg",
        [],
        query_words,
        "A woman standing with a cat",
    )

    assert complete_match > partial_match


def test_search_filters_low_relevance_vector_results(monkeypatch):
    relevant_id = str(uuid4())
    irrelevant_id = str(uuid4())
    assets = [
        {
            "id": relevant_id,
            "filename": "bicycle.jpg",
            "file_type": "image",
            "description": "A red bicycle",
            "status": "indexed",
        },
        {
            "id": irrelevant_id,
            "filename": "car.jpg",
            "file_type": "image",
            "description": "A blue car",
            "status": "indexed",
        },
    ]
    points = [
        SimpleNamespace(
            payload={"asset_id": relevant_id},
            score=0.4,
        ),
        SimpleNamespace(
            payload={"asset_id": irrelevant_id},
            score=0.6,
        ),
    ]
    monkeypatch.setattr(search_service, "ensure_collection", lambda: None)
    monkeypatch.setattr(
        search_service,
        "generate_embedding",
        lambda query: [0.1] * 768,
    )
    monkeypatch.setattr(
        search_service.client,
        "query_points",
        lambda **kwargs: SimpleNamespace(points=points),
    )
    monkeypatch.setattr(
        search_service.assets_collection,
        "find",
        lambda *args, **kwargs: assets,
    )

    results = search_service.search_assets("red bicycle")

    assert [result["asset_id"] for result in results] == [relevant_id]


def test_keyword_fallback_filters_partial_query_matches(monkeypatch):
    asset = {
        "id": str(uuid4()),
        "filename": "image.jpg",
        "file_type": "image",
        "description": "A woman sitting beside a cat",
        "tags": [],
        "status": "indexed",
    }

    class Cursor(list):
        def limit(self, count):
            return self

    monkeypatch.setattr(search_service, "ensure_collection", lambda: None)
    monkeypatch.setattr(
        search_service,
        "generate_embedding",
        lambda query: [0.1] * 768,
    )
    monkeypatch.setattr(
        search_service.client,
        "query_points",
        lambda **kwargs: SimpleNamespace(points=[]),
    )
    monkeypatch.setattr(
        search_service.assets_collection,
        "find",
        lambda *args, **kwargs: Cursor([asset]),
    )

    results = search_service.search_assets("woman standing in a forest")

    assert results == []


def test_embedding_does_not_silently_return_a_nonsemantic_vector(monkeypatch):
    monkeypatch.setattr(embedding_service, "_is_ollama_online", lambda: False)

    with pytest.raises(RuntimeError, match="Ollama is unavailable"):
        embedding_service.generate_embedding("a cat sitting by a window")


def test_embedding_uses_configured_ai_timeout(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"embeddings": [[0.25] * 768]}).encode()

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(embedding_service, "_is_ollama_online", lambda: True)
    monkeypatch.setattr(embedding_service.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(embedding_service.settings, "ai_request_timeout_seconds", 37)

    vector = embedding_service.generate_embedding("a cat")

    assert len(vector) == 768
    assert captured["timeout"] == 37


def test_image_index_uses_the_vision_description_not_guessed_tags(monkeypatch, tmp_path):
    asset_id = uuid4()
    asset_path = tmp_path / "generic-image.jpg"
    asset_path.touch()
    asset = {
        "id": str(asset_id),
        "filename": asset_path.name,
        "original_path": str(asset_path),
        "file_type": "image",
        "description": "Unrelated old description",
        "extracted_text": None,
        "status": "pending",
    }
    updates = []
    embedding_inputs = []
    monkeypatch.setattr(
        indexing_service.assets_collection,
        "find_one",
        lambda *args, **kwargs: asset,
    )
    monkeypatch.setattr(
        indexing_service.assets_collection,
        "update_one",
        lambda *args, **kwargs: updates.append(args[1]["$set"]),
    )
    monkeypatch.setattr(
        indexing_service,
        "generate_image_description",
        lambda path: "A black cat sitting on a sofa",
    )
    monkeypatch.setattr(
        indexing_service,
        "generate_embedding",
        lambda text: embedding_inputs.append(text) or [0.0] * 768,
    )
    monkeypatch.setattr(indexing_service, "upsert_asset_embedding", lambda *a, **k: None)

    indexing_service.index_asset(asset_id)

    searchable_metadata = next(
        update for update in updates if update.get("status") == "ai_processed"
    )
    assert searchable_metadata["description"] == "A black cat sitting on a sofa"
    assert "sky" not in searchable_metadata["tags"]
    assert embedding_inputs == ["A black cat sitting on a sofa"]
    assert updates[-1]["status"] == "indexed"


def test_search_reports_embedding_service_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("Ollama is unavailable")

    monkeypatch.setattr(main, "search_assets", unavailable)
    response = TestClient(main.app).get("/search", params={"q": "a cat"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Ollama is unavailable"


def test_search_reports_qdrant_unavailable(monkeypatch):
    def unavailable():
        raise ResponseHandlingException(ConnectionError("connection refused"))

    monkeypatch.setattr(search_service, "ensure_collection", unavailable)
    response = TestClient(main.app).get("/search", params={"q": "cat"})

    assert response.status_code == 503
    assert "Qdrant cannot be reached" in response.json()["detail"]


def test_ai_health_reports_missing_ollama_models(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_ollama_status",
        lambda: {
            "status": "degraded",
            "ollama_available": True,
            "installed_models": ["embeddinggemma:latest"],
            "required_models": ["embeddinggemma:latest", "moondream:latest"],
            "missing_models": ["moondream:latest"],
        },
    )

    response = TestClient(main.app).get("/health/ai")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["missing_models"] == ["moondream:latest"]


def test_ollama_status_reports_connection_error(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(embedding_service.request, "urlopen", unavailable)

    status = embedding_service.get_ollama_status()

    assert status["status"] == "offline"
    assert status["ollama_available"] is False
    assert "connection refused" in status["detail"]
