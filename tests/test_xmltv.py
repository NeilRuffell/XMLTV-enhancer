from xmltv_enricher.models import ClassificationResult
from xmltv_enricher.xmltv import build_genres_tree, enrich_tree, parse_xmltv


def test_enrich_tree_rewrites_categories():
    tree = parse_xmltv(
        """<tv>
        <programme start="20260101000000 +0000" stop="20260101010000 +0000" channel="ch1">
          <title>The Office</title>
          <category>Drama</category>
        </programme>
        </tv>"""
    )
    enriched = enrich_tree(
        tree,
        [
            ClassificationResult(
                source="tmdb",
                media_type="tv",
                title="The Office",
                genres=["Comedy"],
                final_category="Entertainment - Comedy",
                genre_id="0x30",
                confidence=7.0,
                decision_reason="exact_normalized_title_match",
            )
        ],
    )
    programme = enriched.getroot().find("programme")
    categories = programme.findall("category")
    assert len(categories) == 1
    assert categories[0].text == "Entertainment - Comedy"


def test_genres_tree_includes_other_unknown_without_mapping():
    tree = build_genres_tree()
    genres = {genre.text: genre.get("type") for genre in tree.getroot().findall("genre")}
    assert genres["Movie"] == "0x10"
    assert genres["Other Unknown"] is None
