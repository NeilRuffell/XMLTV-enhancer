from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from .audit import audit_outputs
from .cache import FileCache
from .catalog import classifier_signature
from .classifier import Classifier
from .config import Settings
from .models import ClassificationResult, ProgramContext
from .tmdb import TMDbClient
from .xmltv import (
    build_channel_lookup,
    build_genres_tree,
    enrich_tree,
    inspect_payload,
    parse_xmltv,
    programme_context,
    xml_bytes,
)


class EnrichmentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = FileCache(settings.cache_dir, classifier_signature())
        self.tmdb = TMDbClient(
            token=settings.tmdb_token,
            language=settings.tmdb_language,
            region=settings.tmdb_region,
        )
        self.classifier = Classifier(self.tmdb, self.cache)
        self.last_refresh: str | None = None
        self.last_stats: dict[str, Any] = {
            "mode": "degraded" if settings.degraded_mode else "ready",
            "programmes": 0,
            "channels": 0,
        }

    async def load_input_xml(self) -> str:
        if self.settings.input_mode == "xmltv_url":
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.settings.xmltv_url)
                response.raise_for_status()
                return response.text
        return Path(self.settings.xmltv_file).read_text(encoding="utf-8")

    async def refresh(self, clear_cache: bool = False) -> dict[str, Any]:
        if clear_cache:
            self.cache.clear()

        xml_text = await self.load_input_xml()
        source_tree = parse_xmltv(xml_text)
        root = source_tree.getroot()
        channels = build_channel_lookup(root)
        programmes = root.findall("programme")
        results: list[ClassificationResult] = []
        for programme in programmes:
            context = programme_context(programme, channels)
            result = await self.classifier.classify(context)
            programme.set("data-media-type", result.media_type or "")
            results.append(result)

        enriched_tree = enrich_tree(source_tree, results)
        enriched_root = enriched_tree.getroot()
        for programme, result in zip(enriched_root.findall("programme"), results, strict=True):
            programme.set("data-media-type", result.media_type or "")

        genres_tree = build_genres_tree(self.settings.map_other_unknown)
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.output_epg_path.write_bytes(xml_bytes(enriched_tree))
        self.settings.output_genres_path.write_bytes(xml_bytes(genres_tree))
        self.last_stats = {
            "mode": "degraded" if self.settings.degraded_mode else "ready",
            "programmes": len(programmes),
            "channels": len(channels),
            "cache_dir": str(self.settings.cache_dir),
            "classifier_version": classifier_signature(),
            "tmdb_available": self.tmdb.available,
        }
        return self.last_stats

    async def inspect(self, title: str) -> dict[str, Any]:
        context = ProgramContext(title=title, description="")
        result = await self.classifier.classify(context)
        return inspect_payload(result, title)

    async def audit(self) -> dict[str, Any]:
        try:
            epg_tree = parse_xmltv(self.settings.output_epg_path.read_text(encoding="utf-8"))
            genres_tree = parse_xmltv(self.settings.output_genres_path.read_text(encoding="utf-8"))
        except Exception:
            return {"ok": False, "violations": ["xml_invalid"]}
        violations = audit_outputs(epg_tree, genres_tree, self.tmdb.available)
        return {"ok": not violations, "violations": violations}

    def health(self) -> dict[str, Any]:
        return {"ok": True, "mode": "degraded" if self.settings.degraded_mode else "ready"}
