from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChannelContext:
    channel_id: str
    display_names: list[str] = field(default_factory=list)

    @property
    def preferred_name(self) -> str:
        return self.display_names[0] if self.display_names else self.channel_id


@dataclass(slots=True)
class ProgramContext:
    title: str
    description: str
    channel_id: str = ""
    channel_name: str = ""
    runtime_minutes: int | None = None
    year: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CandidateScore:
    score: float
    reason: str
    payload: dict[str, Any]


@dataclass(slots=True)
class ClassificationResult:
    source: str
    media_type: str | None
    title: str
    genres: list[str]
    final_category: str
    genre_id: str | None
    confidence: float
    decision_reason: str
    special_detection: dict[str, Any] | None = None
    tmdb_candidates: list[dict[str, Any]] = field(default_factory=list)
    normalized_candidates: list[str] = field(default_factory=list)
