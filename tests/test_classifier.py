import pytest

from xmltv_enricher.cache import FileCache
from xmltv_enricher.classifier import Classifier
from xmltv_enricher.models import ProgramContext


class StubTMDb:
    available = True

    async def search_multi(self, query: str):
        data = {
            "2012": [
                {
                    "id": 1,
                    "media_type": "movie",
                    "title": "2012",
                    "original_title": "2012",
                    "overview": "A disaster film.",
                    "genre_ids": [28, 878],
                    "popularity": 30,
                    "vote_count": 1000,
                    "release_date": "2009-11-10",
                }
            ],
            "Seinfeld": [
                {
                    "id": 2,
                    "media_type": "tv",
                    "name": "Seinfeld",
                    "original_name": "Seinfeld",
                    "overview": "A sitcom about nothing.",
                    "genre_ids": [35],
                    "popularity": 20,
                    "vote_count": 500,
                    "first_air_date": "1989-07-05",
                }
            ],
            "The Office": [
                {
                    "id": 3,
                    "media_type": "tv",
                    "name": "The Office",
                    "original_name": "The Office",
                    "overview": "A workplace comedy.",
                    "genre_ids": [35],
                    "popularity": 25,
                    "vote_count": 700,
                    "first_air_date": "2005-03-24",
                }
            ],
            "Mystery Title": [
                {
                    "id": 4,
                    "media_type": "movie",
                    "title": "Another Movie",
                    "original_title": "Another Movie",
                    "overview": "Unrelated.",
                    "genre_ids": [18],
                    "popularity": 10,
                    "vote_count": 25,
                    "release_date": "2001-01-01",
                },
                {
                    "id": 5,
                    "media_type": "tv",
                    "name": "Another Show",
                    "original_name": "Another Show",
                    "overview": "Also unrelated.",
                    "genre_ids": [18],
                    "popularity": 9,
                    "vote_count": 20,
                    "first_air_date": "2001-01-01",
                },
            ],
        }
        return data.get(query, [])


@pytest.mark.anyio
async def test_classifier_resolves_movie(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(ProgramContext(title="2012", description="A disaster movie"))
    assert result.media_type == "movie"
    assert result.final_category.startswith("Movie")
    assert result.genre_id == "0x10"
    assert result.source == "tmdb"
    assert result.confidence >= 4.5


@pytest.mark.anyio
async def test_classifier_resolves_tv_comedy(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(ProgramContext(title="Seinfeld", description="A sitcom about nothing"))
    assert result.media_type == "tv"
    assert result.final_category == "Entertainment - Comedy"
    assert result.genre_id == "0x30"
    assert result.source == "tmdb"


@pytest.mark.anyio
async def test_classifier_resolves_the_office(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(ProgramContext(title="The Office", description="A workplace comedy"))
    assert result.media_type == "tv"
    assert result.final_category == "Entertainment - Comedy"
    assert result.decision_reason


@pytest.mark.anyio
async def test_classifier_falls_back_for_ambiguous_match(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(ProgramContext(title="Mystery Title", description="No metadata"))
    assert result.source == "fallback"
    assert result.final_category == "Other Unknown"


@pytest.mark.anyio
async def test_classifier_uses_high_confidence_special_rule(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(
        ProgramContext(title="NFL Live", description="Latest football headlines", channel_name="ESPN")
    )
    assert result.source == "special_rule"
    assert result.final_category == "Sports - Football"


@pytest.mark.anyio
async def test_tmdb_title_match_beats_news_wording_in_description(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(
        ProgramContext(
            title="Seinfeld",
            description="He shares news with his wife after a strange day.",
            channel_name="Local TV",
        )
    )
    assert result.source == "tmdb"
    assert result.final_category == "Entertainment - Comedy"


@pytest.mark.anyio
async def test_unknown_title_with_news_wording_does_not_become_news_without_channel_signal(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(
        ProgramContext(
            title="Unknown Sitcom",
            description="He shares news with his wife after dinner.",
            channel_name="General Entertainment",
        )
    )
    assert result.source == "fallback"
    assert result.final_category == "Other Unknown"
