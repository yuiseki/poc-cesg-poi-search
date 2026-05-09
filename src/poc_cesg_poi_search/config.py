import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    poi_search_db: str = os.environ.get("POI_SEARCH_DB", "")
    poi_search_asset_url: str = os.environ.get(
        "POI_SEARCH_ASSET_URL",
        "https://z.yuiseki.net/static/cesg/tokyo/poi-search.duckdb",
    )
    poi_search_manifest_url: str = os.environ.get(
        "POI_SEARCH_MANIFEST_URL",
        "https://z.yuiseki.net/static/cesg/tokyo/poi-search-manifest.json",
    )
    poi_search_local_cache: str = os.environ.get(
        "POI_SEARCH_LOCAL_CACHE", "/tmp/poi-search.duckdb"
    )

    class Config:
        env_file = ".env"


settings = Settings()
