from __future__ import annotations

import asyncio
import json
import logging
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

logger = logging.getLogger(__name__)


class EnrichmentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._refresh_lock = asyncio.Lock()
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
            "refresh_state": "idle",
            "refresh_phase": None,
            "programmes": 0,
            "channels": 0,
            "processed_programmes": 0,
            "total_programmes": 0,
            "last_error": None,
        }

    async def load_input_xml(self) -> str:
        if self.settings.input_mode == "xmltv_url":
            logger.info("Fetching XMLTV from URL")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.settings.xmltv_url)
                response.raise_for_status()
                logger.info("Fetched XMLTV from URL with status %s", response.status_code)
                return response.text
        logger.info("Reading XMLTV from file %s", self.settings.xmltv_file)
        return Path(self.settings.xmltv_file).read_text(encoding="utf-8")

    async def refresh(self, clear_cache: bool = False) -> dict[str, Any]:
        async for _ in self.refresh_stream(clear_cache=clear_cache):
            pass
        return self.last_stats

    async def refresh_stream(self, clear_cache: bool = False):
        if self._refresh_lock.locked():
            logger.info("Refresh requested while another refresh is already running")
            yield self._format_progress_line("refresh already running")
            yield self._format_json_line(self.last_stats)
            return

        async with self._refresh_lock:
            yield self._format_progress_line(
                f"refresh started clear_cache={clear_cache} input_mode={self.settings.input_mode}"
            )
            self._set_progress(state="running", phase="starting", clear_cache=clear_cache, last_error=None)
            logger.info("Refresh started clear_cache=%s input_mode=%s", clear_cache, self.settings.input_mode)
            try:
                if clear_cache:
                    self._set_progress(phase="clearing_cache")
                    self.cache.clear()
                    logger.info("Cache cleared")
                    yield self._format_progress_line("cache cleared")

                self._set_progress(phase="loading_input")
                yield self._format_progress_line("loading input xmltv")
                xml_text = await self.load_input_xml()
                logger.info("Input XML loaded (%s bytes)", len(xml_text.encode("utf-8")))
                yield self._format_progress_line(f"input loaded bytes={len(xml_text.encode('utf-8'))}")

                self._set_progress(phase="parsing_xml")
                yield self._format_progress_line("parsing xmltv")
                source_tree = parse_xmltv(xml_text)
                root = source_tree.getroot()
                channels = build_channel_lookup(root)
                programmes = root.findall("programme")
                total_programmes = len(programmes)
                self._set_progress(
                    phase="classifying",
                    channels=len(channels),
                    total_programmes=total_programmes,
                    processed_programmes=0,
                )
                logger.info("Parsed XMLTV channels=%s programmes=%s", len(channels), total_programmes)
                yield self._format_progress_line(
                    f"parsed xmltv channels={len(channels)} programmes={total_programmes}"
                )

                results: list[ClassificationResult] = []
                for index, programme in enumerate(programmes, start=1):
                    context = programme_context(programme, channels)
                    result = await self.classifier.classify(context)
                    programme.set("data-media-type", result.media_type or "")
                    results.append(result)
                    self._set_progress(processed_programmes=index, total_programmes=total_programmes)
                    if index == 1 or index % 100 == 0 or index == total_programmes:
                        logger.info(
                            "Classification progress %s/%s title=%r category=%r",
                            index,
                            total_programmes,
                            context.title,
                            result.final_category,
                        )
                        yield self._format_progress_line(
                            f"classification {index}/{total_programmes} title={context.title!r} "
                            f"category={result.final_category!r}"
                        )

                self._set_progress(phase="writing_output")
                yield self._format_progress_line("writing output files")
                enriched_tree = enrich_tree(source_tree, results)
                enriched_root = enriched_tree.getroot()
                for programme, result in zip(enriched_root.findall("programme"), results, strict=True):
                    programme.set("data-media-type", result.media_type or "")

                genres_tree = build_genres_tree(self.settings.map_other_unknown)
                self.settings.data_dir.mkdir(parents=True, exist_ok=True)
                self.settings.output_epg_path.write_bytes(xml_bytes(enriched_tree))
                self.settings.output_genres_path.write_bytes(xml_bytes(genres_tree))
                logger.info(
                    "Wrote outputs epg=%s genres=%s",
                    self.settings.output_epg_path,
                    self.settings.output_genres_path,
                )
                yield self._format_progress_line("output files written")

                self._set_progress(
                    state="idle",
                    phase="complete",
                    programmes=total_programmes,
                    channels=len(channels),
                    processed_programmes=total_programmes,
                    total_programmes=total_programmes,
                    cache_dir=str(self.settings.cache_dir),
                    classifier_version=classifier_signature(),
                    tmdb_available=self.tmdb.available,
                    last_error=None,
                )
                logger.info("Refresh completed successfully")
                yield self._format_progress_line("refresh completed")
                yield self._format_json_line(self.last_stats)
                return
            except Exception as exc:
                logger.exception("Refresh failed")
                self._set_progress(state="error", phase="failed", last_error=str(exc))
                yield self._format_progress_line(f"refresh failed error={exc}")
                yield self._format_json_line(self.last_stats)
                raise

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

    def _set_progress(self, **updates: Any) -> None:
        base = {
            "mode": "degraded" if self.settings.degraded_mode else "ready",
            "refresh_state": self.last_stats.get("refresh_state", "idle"),
            "refresh_phase": self.last_stats.get("refresh_phase"),
            "programmes": self.last_stats.get("programmes", 0),
            "channels": self.last_stats.get("channels", 0),
            "processed_programmes": self.last_stats.get("processed_programmes", 0),
            "total_programmes": self.last_stats.get("total_programmes", 0),
            "cache_dir": self.last_stats.get("cache_dir", str(self.settings.cache_dir)),
            "classifier_version": self.last_stats.get("classifier_version", classifier_signature()),
            "tmdb_available": self.last_stats.get("tmdb_available", self.tmdb.available),
            "last_error": self.last_stats.get("last_error"),
        }
        base.update(updates)
        self.last_stats = base

    def _format_progress_line(self, message: str) -> str:
        return f"{message}\n"

    def _format_json_line(self, payload: dict[str, Any]) -> str:
        return f"{json.dumps(payload, ensure_ascii=False)}\n"
