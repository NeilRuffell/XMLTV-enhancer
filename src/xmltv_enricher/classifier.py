from __future__ import annotations

import json
from dataclasses import asdict

from .cache import FileCache
from .catalog import MAPPED_GENRE_IDS, MOVIE_GENRE_MAP, TV_GENRE_MAP
from .models import ClassificationResult, ProgramContext
from .normalization import jaccard_similarity, normalize_title, title_candidates
from .tmdb import TMDbClient

SPORT_RULES = {
    "baseball": "Sports - Baseball",
    "mlb": "Sports - Baseball",
    "basketball": "Sports - Basketball",
    "nba": "Sports - Basketball",
    "football": "Sports - Football",
    "nfl": "Sports - Football",
    "cfl": "Sports - Football",
    "golf": "Sports - Golf",
    "hockey": "Sports - Hockey",
    "nhl": "Sports - Hockey",
    "formula 1": "Sports - Motor Sport",
    "f1": "Sports - Motor Sport",
    "motorsport": "Sports - Motor Sport",
    "racing": "Sports - Motor Sport",
    "tennis": "Sports - Tennis",
}

BUSINESS_TERMS = {"business", "markets", "finance", "economics", "stocks"}
NEWS_TERMS = {"news", "weather", "current affairs", "headlines"}
CHILDREN_TERMS = {"kids", "children", "cartoon", "family channel"}
DOCUMENTARY_TERMS = {"documentary", "history", "science", "nature", "factual"}
LIFESTYLE_TERMS = {"food", "home", "garden", "travel", "lifestyle", "renovation"}
MUSIC_TERMS = {"music", "concert", "countdown", "hits"}


class Classifier:
    def __init__(self, tmdb: TMDbClient, cache: FileCache) -> None:
        self.tmdb = tmdb
        self.cache = cache

    async def classify(self, program: ProgramContext) -> ClassificationResult:
        candidates = title_candidates(program.title)
        special = self._detect_special(program)
        if special:
            return ClassificationResult(
                source="rule",
                media_type=None,
                title=program.title,
                genres=[],
                final_category=special,
                genre_id=MAPPED_GENRE_IDS.get(special),
                special_detection=special,
                normalized_candidates=candidates,
            )

        cache_key = self._cache_key(program, candidates)
        cached = self.cache.get(cache_key)
        if cached:
            return ClassificationResult(**cached)

        tmdb_candidates = await self._search_tmdb(program, candidates)
        chosen = self._pick_tmdb_candidate(program, tmdb_candidates)
        if chosen is None:
            result = ClassificationResult(
                source="fallback",
                media_type=None,
                title=program.title,
                genres=[],
                final_category="Other Unknown",
                genre_id=MAPPED_GENRE_IDS.get("Other Unknown"),
                normalized_candidates=candidates,
                tmdb_candidates=tmdb_candidates,
            )
        else:
            final_category = self._map_genres(chosen["media_type"], chosen["genres"])
            result = ClassificationResult(
                source="tmdb",
                media_type=chosen["media_type"],
                title=chosen["title"],
                genres=chosen["genres"],
                final_category=final_category,
                genre_id=MAPPED_GENRE_IDS.get(final_category),
                normalized_candidates=candidates,
                tmdb_candidates=tmdb_candidates,
            )

        self.cache.set(cache_key, asdict(result))
        return result

    def _detect_special(self, program: ProgramContext) -> str | None:
        haystack = " ".join(filter(None, [program.channel_name, program.title, program.description])).lower()
        if any(term in haystack for term in BUSINESS_TERMS):
            return "News & Documentaries - Business"
        if any(term in haystack for term in NEWS_TERMS):
            return "News & Documentaries - News"
        for term, category in SPORT_RULES.items():
            if term in haystack:
                return category
        if any(term in haystack for term in CHILDREN_TERMS):
            return "Children"
        if any(term in haystack for term in DOCUMENTARY_TERMS):
            return "Documentary"
        if any(term in haystack for term in LIFESTYLE_TERMS):
            return "Lifestyle"
        if any(term in haystack for term in MUSIC_TERMS):
            return "Music"
        return None

    async def _search_tmdb(self, program: ProgramContext, candidates: list[str]) -> list[dict]:
        aggregated: list[dict] = []
        seen: set[str] = set()
        for candidate in candidates:
            for result in await self.tmdb.search_multi(candidate):
                identity = f"{result.get('media_type')}:{result.get('id')}"
                if identity in seen:
                    continue
                seen.add(identity)
                aggregated.append(
                    {
                        "id": result.get("id"),
                        "media_type": result.get("media_type"),
                        "title": result.get("title") or result.get("name") or "",
                        "overview": result.get("overview") or "",
                        "genres": [genre["name"] for genre in result.get("genre_ids_resolved", [])],
                        "genre_ids": result.get("genre_ids", []),
                        "popularity": result.get("popularity", 0),
                        "vote_count": result.get("vote_count", 0),
                        "release_date": result.get("release_date") or result.get("first_air_date") or "",
                    }
                )
        return aggregated

    def _pick_tmdb_candidate(self, program: ProgramContext, tmdb_candidates: list[dict]) -> dict | None:
        ranked: list[tuple[float, dict]] = []
        normalized = normalize_title(program.title).lower()
        for candidate in tmdb_candidates:
            title = normalize_title(candidate["title"]).lower()
            score = 0.0
            if title == normalized:
                score += 5.0
            score += jaccard_similarity(program.title, candidate["title"]) * 2.5
            score += jaccard_similarity(program.description, candidate["overview"]) * 1.5
            if program.year and candidate["release_date"].startswith(str(program.year)):
                score += 2.0
            if candidate["media_type"] == "movie" and program.runtime_minutes and program.runtime_minutes >= 60:
                score += 0.5
            if candidate["media_type"] == "tv" and program.runtime_minutes and program.runtime_minutes < 60:
                score += 0.5
            score += min(candidate["popularity"] / 1000.0, 0.25)
            score += min(candidate["vote_count"] / 10000.0, 0.25)
            ranked.append((score, candidate))

        if not ranked:
            return None
        ranked.sort(key=lambda item: item[0], reverse=True)
        best_score, best = ranked[0]
        if best_score < 3.0:
            return None
        best["genres"] = self._resolve_genre_names(best)
        return best

    def _resolve_genre_names(self, candidate: dict) -> list[str]:
        if candidate.get("genres"):
            return candidate["genres"]
        movie_lookup = {
            28: "Action",
            12: "Adventure",
            16: "Animation",
            35: "Comedy",
            18: "Drama",
            99: "Documentary",
            27: "Horror",
            9648: "Mystery",
            10749: "Romance",
            878: "Science Fiction",
            53: "Thriller",
            10752: "War",
            37: "Western",
            10751: "Family",
        }
        tv_lookup = {
            10759: "Action & Adventure",
            16: "Animation",
            35: "Comedy",
            18: "Drama",
            10764: "Reality",
            10765: "Sci-Fi & Fantasy",
            10766: "Soap",
            10767: "Talk",
            10762: "Kids",
        }
        lookup = movie_lookup if candidate["media_type"] == "movie" else tv_lookup
        return [lookup[genre_id] for genre_id in candidate.get("genre_ids", []) if genre_id in lookup]

    def _map_genres(self, media_type: str, genres: list[str]) -> str:
        if media_type == "movie":
            for genre in genres:
                if genre in MOVIE_GENRE_MAP:
                    return MOVIE_GENRE_MAP[genre]
            return "Movie"
        if media_type == "tv":
            if "Kids" in genres:
                return "Children"
            if "Documentary" in genres:
                return "Documentary"
            for genre in genres:
                if genre in TV_GENRE_MAP:
                    return TV_GENRE_MAP[genre]
            return "Entertainment"
        return "Other Unknown"

    def _cache_key(self, program: ProgramContext, candidates: list[str]) -> str:
        payload = {
            "title": program.title,
            "description": program.description,
            "channel_id": program.channel_id,
            "channel_name": program.channel_name,
            "runtime_minutes": program.runtime_minutes,
            "year": program.year,
            "normalized_candidates": candidates,
        }
        return json.dumps(payload, sort_keys=True)
