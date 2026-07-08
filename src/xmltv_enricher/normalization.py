from __future__ import annotations

import re

NOISE_PATTERNS = [
    re.compile(r"\b(?:HD|FHD|UHD|4K|NEW|LIVE|Premiere)\b", re.IGNORECASE),
    re.compile(r"\bS\d{1,2}\s*E\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\bS\d{1,2}E\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}x\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\bEpisode\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bSeason\s+\d+\b", re.IGNORECASE),
]


def normalize_title(title: str) -> str:
    value = title.strip()
    for pattern in NOISE_PATTERNS:
        value = pattern.sub(" ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+[-:|]\s*$", "", value)
    return value.strip(" -:")


def title_candidates(title: str) -> list[str]:
    raw = title.strip()
    normalized = normalize_title(raw)
    seen: list[str] = []
    for candidate in (raw, normalized):
        if candidate and candidate not in seen:
            seen.append(candidate)
    return seen


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return overlap / union if union else 0.0
