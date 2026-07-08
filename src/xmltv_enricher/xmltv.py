from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET

from .catalog import ALLOWED_CATEGORIES, MAPPED_GENRE_IDS
from .models import ChannelContext, ClassificationResult, ProgramContext


def parse_xmltv(xml_text: str) -> ET.ElementTree:
    return ET.ElementTree(ET.fromstring(xml_text))


def xml_bytes(tree: ET.ElementTree) -> bytes:
    return ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True)


def build_channel_lookup(root: ET.Element) -> dict[str, ChannelContext]:
    channels: dict[str, ChannelContext] = {}
    for channel in root.findall("channel"):
        channel_id = channel.get("id", "")
        names = [(node.text or "").strip() for node in channel.findall("display-name") if (node.text or "").strip()]
        channels[channel_id] = ChannelContext(channel_id=channel_id, display_names=names)
    return channels


def _runtime_minutes(programme: ET.Element) -> int | None:
    start = programme.get("start")
    stop = programme.get("stop")
    if not start or not stop:
        return None
    try:
        start_dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S")
        stop_dt = datetime.strptime(stop[:14], "%Y%m%d%H%M%S")
        return max(0, int((stop_dt - start_dt).total_seconds() / 60))
    except ValueError:
        return None


def programme_context(programme: ET.Element, channels: dict[str, ChannelContext]) -> ProgramContext:
    channel_id = programme.get("channel", "")
    channel_name = channels.get(channel_id).preferred_name if channel_id in channels else channel_id
    title = programme.findtext("title", default="").strip()
    description = programme.findtext("desc", default="").strip()
    year = None
    date_text = programme.findtext("date", default="").strip()
    if len(date_text) >= 4 and date_text[:4].isdigit():
        year = int(date_text[:4])
    return ProgramContext(
        title=title,
        description=description,
        channel_id=channel_id,
        channel_name=channel_name,
        runtime_minutes=_runtime_minutes(programme),
        year=year,
    )


def enrich_tree(tree: ET.ElementTree, results: list[ClassificationResult]) -> ET.ElementTree:
    root = deepcopy(tree.getroot())
    programmes = root.findall("programme")
    for programme, result in zip(programmes, results, strict=True):
        for category in list(programme.findall("category")):
            programme.remove(category)
        category = ET.Element("category")
        category.text = result.final_category
        programme.append(category)
    return ET.ElementTree(root)


def build_genres_tree(map_other_unknown: bool = False) -> ET.ElementTree:
    root = ET.Element("genres")
    for category in ALLOWED_CATEGORIES:
        genre = ET.SubElement(root, "genre")
        genre.text = category
        genre_id = MAPPED_GENRE_IDS.get(category)
        if genre_id:
            genre.set("type", genre_id)
        elif category == "Other Unknown" and map_other_unknown:
            genre.set("type", "0xF0")
    return ET.ElementTree(root)


def extract_categories(tree: ET.ElementTree) -> list[str]:
    return [programme.findtext("category", default="") for programme in tree.getroot().findall("programme")]


def inspect_payload(result: ClassificationResult, query: str) -> dict[str, Any]:
    return {
        "query": query,
        "normalized_candidates": result.normalized_candidates,
        "special_detection": result.special_detection,
        "tmdb_candidates": result.tmdb_candidates,
        "chosen": {
            "source": result.source,
            "media_type": result.media_type,
            "title": result.title,
            "genres": result.genres,
            "final_category": result.final_category,
            "genre_id": result.genre_id,
        },
    }
