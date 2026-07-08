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
                    "title": "Seinfeld",
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
                    "title": "The Office",
                    "overview": "A workplace comedy.",
                    "genre_ids": [35],
                    "popularity": 25,
                    "vote_count": 700,
                    "first_air_date": "2005-03-24",
                }
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


@pytest.mark.anyio
async def test_classifier_resolves_tv_comedy(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(ProgramContext(title="Seinfeld", description="A sitcom about nothing"))
    assert result.media_type == "tv"
    assert result.final_category == "Entertainment - Comedy"
    assert result.genre_id == "0x30"


@pytest.mark.anyio
async def test_classifier_resolves_the_office(tmp_path):
    classifier = Classifier(StubTMDb(), FileCache(tmp_path, "v1"))
    result = await classifier.classify(ProgramContext(title="The Office", description="A workplace comedy"))
    assert result.media_type == "tv"
    assert result.final_category == "Entertainment - Comedy"
