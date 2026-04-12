"""API settings via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Vision API"
    vision_db_path: str = "vision.db"
    google_cloud_project: str | None = None
    default_script_path: str = "src/live/example_script.yaml"
    default_product_path: str = "src/live/data/product.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
