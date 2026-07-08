from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from .cache import FileCache
from .catalog import MAPPED_GENRE_IDS, MOVIE_GENRE_MAP, TV_GENRE_MAP
from .models import ClassificationResult, ProgramContext
from .normalization import jaccard_similarity, normalize_title, title_candidates
from .tmdb import TMDbClient

CHANNEL_BUSINESS_TERMS = {"bloomberg", "fox business", "cnbc", "bnn", "business"}
CONTENT_BUSINESS_TERMS = {"business", "markets", "finance", "economics", "stocks", "commodities"}
CHANNEL_NEWS_TERMS = {
    "cnn",
    "bbc news",
    "cbc news",
    "ctv news",
    "global news",
    "fox news",
    "msnbc",
    "weather network",
    "cp24",
    "cpac",
}
CONTENT_NEWS_TERMS = {"news", "weather", "headlines", "current affairs", "breaking"}
CHANNEL_SPORTS_TERMS = {
    "sports",
    "sportsnet",
    "tsn",
    "espn",
    "nfl network",
    "nhl network",
    "mlb network",
    "golf channel",
    "tennis channel",
}
SPORT_RULES = {
    "baseball": "Sports - Baseball",
    "mlb": "Sports - Baseball",
    "blue jays": "Sports - Baseball",
    "basketball": "Sports - Basketball",
    "nba": "Sports - Basketball",
    "football": "Sports - Football",
    "nfl": "Sports - Football",
    "cfl": "Sports - Football",
    "golf": "Sports - Golf",
    "pga": "Sports - Golf",
    "hockey": "Sports - Hockey",
    "nhl": "Sports - Hockey",
    "formula 1": "Sports - Motor Sport",
    "f1": "Sports - Motor Sport",
    "motorsport": "Sports - Motor Sport",
    "racing": "Sports - Motor Sport",
    "tennis": "Sports - Tennis",
}
CHANNEL_CHILDREN_TERMS = {"kids", "children", "cartoon", "nick", "disney", "treehouse", "family jr"}
CONTENT_CHILDREN_TERMS = {"kids", "children", "cartoon", "preschool", "animated"}
CHANNEL_DOCUMENTARY_TERMS = {"discovery", "history", "national geographic", "nat geo", "science", "documentary"}
CONTENT_DOCUMENTARY_TERMS = {"documentary", "history", "science", "nature", "wildlife", "factual"}
CHANNEL_LIFESTYLE_TERMS = {"food", "travel", "hgtv", "home", "garden", "magnolia", "lifestyle", "cooking"}
CONTENT_LIFESTYLE_TERMS = {"food", "travel", "home", "garden", "renovation", "cooking", "diy", "makeover"}
CHANNEL_MUSIC_TERMS = {"music", "mtv", "much", "cmt", "stingray"}
CONTENT_MUSIC_TERMS = {"concert", "music", "playlist", "album", "orchestra", "symphony", "countdown"}
GAME_SHOW_TITLE_TERMS = {
    "jeopardy",
    "wheel of fortune",
    "family feud",
    "the price is right",
    "let's make a deal",
    "lets make a deal",
    "who wants to be a millionaire",
    "password",
    "match game",
    "cash cab",
    "trivial pursuit",
}
GAME_SHOW_CONTENT_TERMS = {"game show", "quiz show", "trivia"}
MOVIE_HINT_CHANNEL_TERMS = {"movie", "movies", "cinema", "film"}
MOVIE_GENRE_ID_LOOKUP = {
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
}
TV_GENRE_ID_LOOKUP = {
    10759: "Action & Adventure",
    16: "Animation",
    35: "Comedy",
    18: "Drama",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
}
NUMERIC_TITLE_RE = re.compile(r"^[0-9][0-9\-: ]*$")


class Classifier:
    def __init__(self, tmdb: TMDbClient, cache: FileCache) -> None:
        self.tmdb = tmdb
        self.cache = cache

    async def classify(self, program: ProgramContext) -> ClassificationResult:
        candidates = title_candidates(program.title)
        cache_key = self._cache_key(program, candidates)
        cached = self.cache.get(cache_key)
        if cached:
            return ClassificationResult(**cached)

        tmdb_candidates = await self._search_tmdb(program)
        chosen = self._pick_tmdb_candidate(program, tmdb_candidates)
        special = self._detect_special(program)
        if chosen is None and special is not None:
            result = ClassificationResult(
                source="special_rule",
                media_type=None,
                title=program.title,
                genres=[],
                final_category=special["category"],
                genre_id=MAPPED_GENRE_IDS.get(special["category"]),
                confidence=special["confidence"],
                decision_reason=special["reason"],
                special_detection=special,
                normalized_candidates=candidates,
                tmdb_candidates=tmdb_candidates,
            )
        elif chosen is None:
            result = ClassificationResult(
                source="fallback",
                media_type=None,
                title=program.title,
                genres=[],
                final_category="Other Unknown",
                genre_id=MAPPED_GENRE_IDS.get("Other Unknown"),
                confidence=0.0,
                decision_reason="no_confident_resolution",
                normalized_candidates=candidates,
                tmdb_candidates=tmdb_candidates,
            )
        else:
            result = ClassificationResult(
                source="tmdb",
                media_type=chosen["media_type"],
                title=chosen["display_title"],
                genres=chosen["genres"],
                final_category=self._map_genres(chosen["media_type"], chosen["genres"]),
                genre_id=MAPPED_GENRE_IDS.get(self._map_genres(chosen["media_type"], chosen["genres"])),
                confidence=chosen["score"],
                decision_reason=chosen["decision_reason"],
                normalized_candidates=candidates,
                tmdb_candidates=tmdb_candidates,
            )

        self.cache.set(cache_key, asdict(result))
        return result

    def _detect_special(self, program: ProgramContext) -> dict[str, Any] | None:
        channel = self._normalize_text(program.channel_name)
        title = self._normalize_text(program.title)
        description = self._normalize_text(program.description)
        content = f"{title} {description}".strip()

        if self._matches_any(title, GAME_SHOW_TITLE_TERMS) or (
            self._matches_any(title, GAME_SHOW_CONTENT_TERMS) and self._matches_any(channel, CHANNEL_SPORTS_TERMS) is False
        ):
            return self._special_result("game_show", "Entertainment - Game Show", 0.92)

        business_channel = self._matches_any(channel, CHANNEL_BUSINESS_TERMS)
        business_title_hits = self._count_matches(title, CONTENT_BUSINESS_TERMS)
        business_description_hits = self._count_matches(description, CONTENT_BUSINESS_TERMS)
        if business_channel and (business_title_hits >= 1 or business_description_hits >= 1):
            return self._special_result(
                "business",
                "News & Documentaries - Business",
                0.96,
            )

        sports_channel = self._matches_any(channel, CHANNEL_SPORTS_TERMS)
        sport_category = self._detect_sport_category(title, description)
        if sport_category and (sports_channel or sport_category["strong_title_signal"]):
            return self._special_result(
                sport_category["family"],
                sport_category["category"],
                0.97 if sports_channel else 0.9,
            )

        news_channel = self._matches_any(channel, CHANNEL_NEWS_TERMS)
        news_title_hits = self._count_matches(title, CONTENT_NEWS_TERMS)
        news_description_hits = self._count_matches(description, CONTENT_NEWS_TERMS)
        if news_channel and (news_title_hits >= 1 or news_description_hits >= 1):
            return self._special_result("news", "News & Documentaries - News", 0.94)

        children_channel = self._matches_any(channel, CHANNEL_CHILDREN_TERMS)
        children_title_hits = self._count_matches(title, CONTENT_CHILDREN_TERMS)
        children_description_hits = self._count_matches(description, CONTENT_CHILDREN_TERMS)
        if children_channel and (children_title_hits >= 1 or children_description_hits >= 1):
            return self._special_result("children", "Children", 0.95 if children_channel else 0.84)
        if children_title_hits >= 2:
            return self._special_result("children", "Children", 0.84)

        documentary_channel = self._matches_any(channel, CHANNEL_DOCUMENTARY_TERMS)
        documentary_title_hits = self._count_matches(title, CONTENT_DOCUMENTARY_TERMS)
        documentary_description_hits = self._count_matches(description, CONTENT_DOCUMENTARY_TERMS)
        if documentary_channel and (documentary_title_hits >= 1 or documentary_description_hits >= 1):
            return self._special_result("documentary", "Documentary", 0.92)
        if documentary_title_hits >= 2:
            return self._special_result("documentary", "Documentary", 0.81)

        lifestyle_channel = self._matches_any(channel, CHANNEL_LIFESTYLE_TERMS)
        lifestyle_title_hits = self._count_matches(title, CONTENT_LIFESTYLE_TERMS)
        lifestyle_description_hits = self._count_matches(description, CONTENT_LIFESTYLE_TERMS)
        if lifestyle_channel and (lifestyle_title_hits >= 1 or lifestyle_description_hits >= 1):
            return self._special_result("lifestyle", "Lifestyle", 0.9)
        if lifestyle_title_hits >= 2:
            return self._special_result("lifestyle", "Lifestyle", 0.8)

        music_channel = self._matches_any(channel, CHANNEL_MUSIC_TERMS)
        music_title_hits = self._count_matches(title, CONTENT_MUSIC_TERMS)
        music_description_hits = self._count_matches(description, CONTENT_MUSIC_TERMS)
        if music_channel and (music_title_hits >= 1 or music_description_hits >= 1):
            return self._special_result("music", "Music", 0.9)
        if music_title_hits >= 2:
            return self._special_result("music", "Music", 0.79)
        return None

    async def _search_tmdb(self, program: ProgramContext) -> list[dict[str, Any]]:
        aggregated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for candidate in title_candidates(program.title):
            for result in await self.tmdb.search_multi(candidate):
                identity = f"{result.get('media_type')}:{result.get('id')}"
                if identity in seen:
                    continue
                seen.add(identity)
                aggregated.append(
                    {
                        "id": result.get("id"),
                        "media_type": result.get("media_type"),
                        "display_title": result.get("title") or result.get("name") or "",
                        "overview": result.get("overview") or "",
                        "genre_ids": result.get("genre_ids", []),
                        "popularity": result.get("popularity", 0),
                        "vote_count": result.get("vote_count", 0),
                        "release_date": result.get("release_date") or result.get("first_air_date") or "",
                        "matched_query": candidate,
                        "title_variants": self._title_variants(result),
                    }
                )
        return aggregated

    def _pick_tmdb_candidate(self, program: ProgramContext, tmdb_candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        normalized_candidates = [normalize_title(value).lower() for value in title_candidates(program.title)]
        title_is_numeric = bool(normalized_candidates and NUMERIC_TITLE_RE.match(normalized_candidates[0]))
        ranked: list[dict[str, Any]] = []
        for candidate in tmdb_candidates:
            evaluation = self._evaluate_candidate(program, candidate, normalized_candidates, title_is_numeric)
            candidate.update(evaluation)
            ranked.append(candidate)

        if not ranked:
            return None
        ranked.sort(key=lambda item: item["score"], reverse=True)
        best = ranked[0]
        if not best["accepted"]:
            return None

        runner_up = ranked[1] if len(ranked) > 1 else None
        if runner_up and (best["score"] - runner_up["score"] < 0.75) and not best["exact_title_match"]:
            best["accepted"] = False
            best["decision_reason"] = f"{best['decision_reason']},close_runner_up"
            return None

        best["genres"] = self._resolve_genre_names(best)
        return best

    def _evaluate_candidate(
        self,
        program: ProgramContext,
        candidate: dict[str, Any],
        normalized_candidates: list[str],
        title_is_numeric: bool,
    ) -> dict[str, Any]:
        normalized_variants = [normalize_title(value).lower() for value in candidate["title_variants"] if value]
        exact_title_match = any(variant in normalized_candidates for variant in normalized_variants)
        title_similarity = max(
            (
                jaccard_similarity(query, variant)
                for query in title_candidates(program.title)
                for variant in candidate["title_variants"]
            ),
            default=0.0,
        )
        score = 0.0
        reasons: list[str] = []
        if exact_title_match:
            score += 6.0
            reasons.append("exact_normalized_title_match")
        elif title_similarity >= 0.75:
            score += 4.0
            reasons.append("strong_title_similarity")
        elif title_similarity >= 0.6:
            score += 2.0
            reasons.append("moderate_title_similarity")
        else:
            reasons.append("weak_title_similarity")

        candidate_year = candidate["release_date"][:4] if candidate["release_date"] else ""
        if program.year and candidate_year:
            if candidate_year == str(program.year):
                score += 1.5
                reasons.append("year_match")
            else:
                score -= 1.0
                reasons.append("year_conflict")

        if candidate["media_type"] == "movie" and program.runtime_minutes and program.runtime_minutes >= 75:
            score += 0.4
            reasons.append("movie_runtime_support")
        if candidate["media_type"] == "tv" and program.runtime_minutes and program.runtime_minutes <= 65:
            score += 0.4
            reasons.append("tv_runtime_support")

        if candidate["media_type"] == "movie" and self._matches_any(self._normalize_text(program.channel_name), MOVIE_HINT_CHANNEL_TERMS):
            score += 0.2
            reasons.append("channel_movie_hint")

        score += min(candidate["popularity"] / 1500.0, 0.2)
        score += min(candidate["vote_count"] / 20000.0, 0.2)

        accepted = exact_title_match or title_similarity >= 0.75
        if title_is_numeric and not exact_title_match:
            accepted = False
            reasons.append("numeric_title_requires_exact_match")
        if score < 4.5:
            accepted = False
            reasons.append("score_below_threshold")
        if "year_conflict" in reasons and not exact_title_match:
            accepted = False
            reasons.append("rejected_year_conflict")

        return {
            "score": round(score, 3),
            "accepted": accepted,
            "decision_reason": ",".join(reasons),
            "exact_title_match": exact_title_match,
            "title_similarity": round(title_similarity, 3),
            "description_similarity": round(jaccard_similarity(program.description, candidate["overview"]), 3),
        }

    def _resolve_genre_names(self, candidate: dict[str, Any]) -> list[str]:
        lookup = MOVIE_GENRE_ID_LOOKUP if candidate["media_type"] == "movie" else TV_GENRE_ID_LOOKUP
        return [lookup[genre_id] for genre_id in candidate.get("genre_ids", []) if genre_id in lookup]

    def _map_genres(self, media_type: str, genres: list[str]) -> str:
        if media_type == "movie":
            for genre in genres:
                if genre in MOVIE_GENRE_MAP:
                    return MOVIE_GENRE_MAP[genre]
            return "Movie"
        if media_type == "tv":
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

    def _special_result(self, family: str, category: str, confidence: float) -> dict[str, Any]:
        return {
            "family": family,
            "category": category,
            "reason": f"high_confidence_{family}_rule",
            "confidence": confidence,
        }

    def _detect_sport_category(self, title: str, description: str) -> dict[str, Any] | None:
        text = f"{title} {description}"
        for term, category in SPORT_RULES.items():
            if self._contains_term(text, term):
                return {
                    "family": category.lower().replace("sports - ", "").replace(" ", "_"),
                    "category": category,
                    "strong_title_signal": self._contains_term(title, term),
                }
        return None

    def _title_variants(self, result: dict[str, Any]) -> list[str]:
        seen: list[str] = []
        for value in (
            result.get("title"),
            result.get("name"),
            result.get("original_title"),
            result.get("original_name"),
        ):
            text = (value or "").strip()
            if text and text not in seen:
                seen.append(text)
        return seen

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.lower()).strip()

    def _matches_any(self, text: str, terms: set[str]) -> bool:
        return any(self._contains_term(text, term) for term in terms)

    def _count_matches(self, text: str, terms: set[str]) -> int:
        return sum(1 for term in terms if self._contains_term(text, term))

    def _contains_term(self, text: str, term: str) -> bool:
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        return bool(re.search(pattern, text))
