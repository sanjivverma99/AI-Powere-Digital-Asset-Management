from __future__ import annotations

import json
import logging
import math
import socket
import time
from urllib import error, parse, request

from backend.app.db.database import settings

logger = logging.getLogger(__name__)

OLLAMA_EMBED_URL = f"{settings.ollama_base_url}/api/embed"
EMBEDDING_MODEL = "embeddinggemma:latest"
EXPECTED_DIMENSION = 768

_ollama_available: bool | None = None
_last_ollama_check: float = 0.0
_CHECK_INTERVAL = 30.0  # re-check every 30 seconds


def _is_ollama_online() -> bool:
    """Fast check whether Ollama host & port are reachable."""
    global _ollama_available, _last_ollama_check
    now = time.time()
    if _ollama_available is not None and (now - _last_ollama_check) < _CHECK_INTERVAL:
        return _ollama_available

    try:
        parsed = parse.urlparse(settings.ollama_base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 11434
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.3)
        res = sock.connect_ex((host, port))
        sock.close()
        _ollama_available = (res == 0)
    except Exception:
        _ollama_available = False

    _last_ollama_check = now
    return _ollama_available


def get_ollama_status() -> dict[str, object]:
    """Report Ollama availability and whether all required models are installed."""
    required_models = [EMBEDDING_MODEL, settings.ollama_vision_model]
    tags_url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    http_request = request.Request(tags_url, method="GET")

    try:
        with request.urlopen(http_request, timeout=2) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "offline",
            "ollama_available": False,
            "installed_models": [],
            "required_models": required_models,
            "missing_models": required_models,
            "detail": f"Cannot reach Ollama at {settings.ollama_base_url}: {exc}",
        }

    models = result.get("models") if isinstance(result, dict) else None
    if not isinstance(models, list):
        return {
            "status": "degraded",
            "ollama_available": True,
            "installed_models": [],
            "required_models": required_models,
            "missing_models": required_models,
            "detail": "Ollama returned an invalid model list from /api/tags.",
        }

    installed_models = [
        model["name"]
        for model in models
        if isinstance(model, dict) and isinstance(model.get("name"), str)
    ]
    missing_models = [
        required
        for required in required_models
        if required not in installed_models
    ]
    return {
        "status": "ready" if not missing_models else "degraded",
        "ollama_available": True,
        "installed_models": installed_models,
        "required_models": required_models,
        "missing_models": missing_models,
        "detail": (
            "Required AI models are ready."
            if not missing_models
            else f"Install required models with: ollama pull {' && ollama pull '.join(missing_models)}"
        ),
    }


def generate_embedding(text: str) -> list[float]:
    """
    Generate a semantic embedding for the supplied text using Ollama.

    A non-semantic hash vector would make unrelated content appear similar, so
    model availability and inference failures are surfaced instead.
    """
    text = text.strip()

    if not text:
        raise ValueError("Cannot generate an embedding for empty text.")

    if not _is_ollama_online():
        raise RuntimeError(
            f"Ollama is unavailable at {settings.ollama_base_url}; "
            f"start Ollama and ensure {EMBEDDING_MODEL} is installed."
        )

    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
    }

    body = json.dumps(payload).encode("utf-8")

    http_request = request.Request(
        OLLAMA_EMBED_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(
            http_request,
            timeout=settings.ai_request_timeout_seconds,
        ) as response:
            result = json.loads(response.read().decode("utf-8"))

        if not isinstance(result, dict):
            raise RuntimeError("Ollama returned an invalid embedding response.")

        embeddings = result.get("embeddings")
        if (
            not isinstance(embeddings, list)
            or not embeddings
            or not isinstance(embeddings[0], list)
        ):
            raise RuntimeError("Ollama returned no valid embeddings.")

        vector = embeddings[0]
        if len(vector) != EXPECTED_DIMENSION:
            raise RuntimeError(
                f"Unexpected embedding dimension: {len(vector)}. "
                f"Expected {EXPECTED_DIMENSION}."
            )
        try:
            vector = [float(value) for value in vector]
        except (TypeError, ValueError) as err:
            raise RuntimeError("Ollama returned a non-numeric embedding.") from err
        if not all(math.isfinite(value) for value in vector):
            raise RuntimeError("Ollama returned a non-finite embedding.")
        return vector

    except (
        error.URLError,
        ConnectionRefusedError,
        TimeoutError,
        OSError,
        RuntimeError,
        json.JSONDecodeError,
    ) as err:
        logger.exception("Ollama embedding request failed.")
        raise RuntimeError(
            f"Unable to generate an embedding with {EMBEDDING_MODEL}: {err}"
        ) from err