from __future__ import annotations

import hashlib

CLASSIFIER_VERSION = "2026-07-08"

ALLOWED_CATEGORIES = [
    "Movie",
    "Movie - Action",
    "Movie - Adventure",
    "Movie - Animation",
    "Movie - Comedy",
    "Movie - Drama",
    "Movie - Factual",
    "Movie - Horror",
    "Movie - Mystery",
    "Movie - Romance",
    "Movie - Sci-Fi",
    "Movie - Thriller",
    "Movie - War",
    "Movie - Western",
    "Entertainment",
    "Entertainment - Action",
    "Entertainment - Animation",
    "Entertainment - Comedy",
    "Entertainment - Drama",
    "Entertainment - Game Show",
    "Entertainment - Reality",
    "Entertainment - Sci-Fi",
    "Entertainment - Soap",
    "Entertainment - Talk",
    "Children",
    "Documentary",
    "News & Documentaries - News",
    "News & Documentaries - Business",
    "Sports - Baseball",
    "Sports - Basketball",
    "Sports - Football",
    "Sports - Golf",
    "Sports - Hockey",
    "Sports - Motor Sport",
    "Sports - Tennis",
    "Lifestyle",
    "Music",
    "Other Unknown",
]

MAPPED_GENRE_IDS = {
    "Movie": "0x10",
    "Movie - Action": "0x10",
    "Movie - Adventure": "0x10",
    "Movie - Animation": "0x10",
    "Movie - Comedy": "0x10",
    "Movie - Drama": "0x10",
    "Movie - Factual": "0x10",
    "Movie - Horror": "0x10",
    "Movie - Mystery": "0x10",
    "Movie - Romance": "0x10",
    "Movie - Sci-Fi": "0x10",
    "Movie - Thriller": "0x10",
    "Movie - War": "0x10",
    "Movie - Western": "0x10",
    "Entertainment": "0x30",
    "Entertainment - Action": "0x30",
    "Entertainment - Animation": "0x30",
    "Entertainment - Comedy": "0x30",
    "Entertainment - Drama": "0x30",
    "Entertainment - Game Show": "0x30",
    "Entertainment - Reality": "0x30",
    "Entertainment - Sci-Fi": "0x30",
    "Entertainment - Soap": "0x30",
    "Entertainment - Talk": "0x30",
    "Children": "0x50",
    "Documentary": "0x90",
    "News & Documentaries - News": "0x20",
    "News & Documentaries - Business": "0x20",
    "Sports - Baseball": "0x40",
    "Sports - Basketball": "0x40",
    "Sports - Football": "0x40",
    "Sports - Golf": "0x40",
    "Sports - Hockey": "0x40",
    "Sports - Motor Sport": "0x40",
    "Sports - Tennis": "0x40",
    "Lifestyle": "0xA0",
    "Music": "0x60",
}

BARE_AMBIGUOUS_CATEGORIES = {
    "Drama",
    "Comedy",
    "Action",
    "Thriller",
    "Romance",
    "Science Fiction",
}

MOVIE_GENRE_MAP = {
    "Action": "Movie - Action",
    "Adventure": "Movie - Adventure",
    "Animation": "Movie - Animation",
    "Comedy": "Movie - Comedy",
    "Drama": "Movie - Drama",
    "Documentary": "Movie - Factual",
    "Horror": "Movie - Horror",
    "Mystery": "Movie - Mystery",
    "Romance": "Movie - Romance",
    "Science Fiction": "Movie - Sci-Fi",
    "Thriller": "Movie - Thriller",
    "War": "Movie - War",
    "Western": "Movie - Western",
}

TV_GENRE_MAP = {
    "Action & Adventure": "Entertainment - Action",
    "Animation": "Entertainment - Animation",
    "Comedy": "Entertainment - Comedy",
    "Drama": "Entertainment - Drama",
    "Reality": "Entertainment - Reality",
    "Sci-Fi & Fantasy": "Entertainment - Sci-Fi",
    "Soap": "Entertainment - Soap",
    "Talk": "Entertainment - Talk",
}


def classifier_signature() -> str:
    mapping_entries = [f"{category}={genre_id}" for category, genre_id in sorted(MAPPED_GENRE_IDS.items())]
    payload = "|".join([CLASSIFIER_VERSION, *ALLOWED_CATEGORIES, *mapping_entries])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
