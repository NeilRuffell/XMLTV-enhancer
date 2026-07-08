from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    input_mode: str = "xmltv_file"
    xmltv_url: str = ""
    xmltv_file: str = "/data/input.xml"
    tmdb_token: str = ""
    tmdb_language: str = "en-US"
    tmdb_region: str = "CA"
    port: int = 8765
    refresh_seconds: int = 21600
    data_dir: Path = Path("/data")
    map_other_unknown: bool = False

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def output_epg_path(self) -> Path:
        return self.data_dir / "epg.xml"

    @property
    def output_genres_path(self) -> Path:
        return self.data_dir / "genres.xml"

    @property
    def degraded_mode(self) -> bool:
        return not bool(self.tmdb_token.strip())


def load_settings() -> Settings:
    return Settings(
        input_mode=os.getenv("INPUT_MODE", "xmltv_file"),
        xmltv_url=os.getenv("XMLTV_URL", ""),
        xmltv_file=os.getenv("XMLTV_FILE", "/data/input.xml"),
        tmdb_token=os.getenv("TMDB_TOKEN", ""),
        tmdb_language=os.getenv("TMDB_LANGUAGE", "en-US"),
        tmdb_region=os.getenv("TMDB_REGION", "CA"),
        port=int(os.getenv("PORT", "8765")),
        refresh_seconds=int(os.getenv("REFRESH_SECONDS", "21600")),
        data_dir=Path(os.getenv("DATA_DIR", "/data")),
        map_other_unknown=os.getenv("MAP_OTHER_UNKNOWN", "").lower() in {"1", "true", "yes"},
    )
