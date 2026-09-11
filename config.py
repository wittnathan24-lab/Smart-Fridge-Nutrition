from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    usda_api_key: str
    themealdb_base_url: str = "https://www.themealdb.com/api/json/v1/1"
    usda_base_url: str = "https://api.nal.usda.gov/fdc/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
