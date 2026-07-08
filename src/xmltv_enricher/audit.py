from __future__ import annotations

from xml.etree import ElementTree as ET

from .catalog import ALLOWED_CATEGORIES, BARE_AMBIGUOUS_CATEGORIES, MAPPED_GENRE_IDS

SPECIAL_RULE_ALLOWED_CATEGORIES = {
    "News & Documentaries - News",
    "News & Documentaries - Business",
    "Sports - Baseball",
    "Sports - Basketball",
    "Sports - Football",
    "Sports - Golf",
    "Sports - Hockey",
    "Sports - Motor Sport",
    "Sports - Tennis",
    "Children",
    "Documentary",
    "Lifestyle",
    "Music",
    "Entertainment - Game Show",
}


def audit_outputs(epg_tree: ET.ElementTree, genres_tree: ET.ElementTree, tmdb_available: bool) -> list[str]:
    violations: list[str] = []
    if not tmdb_available:
        violations.append("tmdb_unavailable")

    root = epg_tree.getroot()
    genres_root = genres_tree.getroot()
    genres_names = {genre.text or "" for genre in genres_root.findall("genre")}

    for programme in root.findall("programme"):
        categories = programme.findall("category")
        if not categories:
            violations.append("programme_missing_category")
            continue
        if len(categories) > 1:
            violations.append("programme_multiple_categories")
        category_text = (categories[0].text or "").strip()
        if category_text not in ALLOWED_CATEGORIES:
            violations.append("category_not_in_whitelist")
        if category_text not in genres_names:
            violations.append("category_missing_from_genres_xml")
        if category_text in BARE_AMBIGUOUS_CATEGORIES:
            violations.append("bare_ambiguous_category")
        if category_text == "Feature Film":
            violations.append("feature_film_present")
        source = programme.get("data-source", "")
        media_type = programme.get("data-media-type", "")
        confidence = float(programme.get("data-confidence", "0") or "0")
        if "Movie" in category_text or "Film" in category_text:
            if media_type == "tv":
                violations.append("tv_contains_movie_or_film")
            elif media_type != "movie":
                violations.append("non_movie_contains_movie_or_film")
            if source != "tmdb" or confidence < 4.5:
                violations.append("movie_category_without_confident_tmdb")
        if category_text.startswith("Movie") and programme.get("data-media-type") != "movie":
            violations.append("movie_category_without_movie_media_type")
        if category_text.startswith("Entertainment") and category_text != "Entertainment - Game Show":
            if source != "tmdb" or media_type != "tv" or confidence < 4.5:
                violations.append("entertainment_category_without_tv_resolution")
        if category_text in SPECIAL_RULE_ALLOWED_CATEGORIES and not category_text.startswith("Entertainment"):
            if source != "special_rule":
                violations.append("non_library_category_without_special_rule")
        if category_text == "Entertainment - Game Show" and source not in {"special_rule", "tmdb"}:
            violations.append("entertainment_category_without_tv_resolution")

    for genre in genres_root.findall("genre"):
        if genre.get("type") == "0x00":
            violations.append("genre_id_0x00_used")
        if (genre.text or "").strip() in MAPPED_GENRE_IDS and genre.get("type") != MAPPED_GENRE_IDS[(genre.text or "").strip()]:
            violations.append("category_missing_from_genres_xml")

    seen: list[str] = []
    for violation in violations:
        if violation not in seen:
            seen.append(violation)
    return seen
