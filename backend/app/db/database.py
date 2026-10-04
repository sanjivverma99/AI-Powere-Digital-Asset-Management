from datetime import datetime, timezone

from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import MongoClient


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "dam"
    qdrant_url: str
    ollama_base_url: str

    ollama_vision_model: str = "moondream:latest"
    ai_request_timeout_seconds: int = 180
    vision_max_image_size: int = 384
    vision_jpeg_quality: int = 50

    ffprobe_path: str
    ffmpeg_path: str

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        extra="ignore",
    )


settings = Settings()
mongo_client = MongoClient(
    settings.mongodb_url,
    serverSelectionTimeoutMS=5000,
    tz_aware=True,
)
database = mongo_client[settings.mongodb_database]
assets_collection = database["assets"]
indexing_jobs_collection = database["indexing_jobs"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ping_database() -> None:
    mongo_client.admin.command("ping")
