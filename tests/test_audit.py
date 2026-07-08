from xmltv_enricher.audit import audit_outputs
from xmltv_enricher.xmltv import build_genres_tree, parse_xmltv


def test_audit_flags_tmdb_unavailable():
    epg = parse_xmltv(
        """<tv>
        <programme data-media-type="tv" data-source="tmdb" data-confidence="7.1">
          <title>Seinfeld</title>
          <category>Entertainment - Comedy</category>
        </programme>
        </tv>"""
    )
    violations = audit_outputs(epg, build_genres_tree(), tmdb_available=False)
    assert "tmdb_unavailable" in violations


def test_audit_flags_movie_category_on_tv():
    epg = parse_xmltv(
        """<tv>
        <programme data-media-type="tv" data-source="tmdb" data-confidence="7.1">
          <title>Seinfeld</title>
          <category>Movie - Comedy</category>
        </programme>
        </tv>"""
    )
    violations = audit_outputs(epg, build_genres_tree(), tmdb_available=True)
    assert "tv_contains_movie_or_film" in violations


def test_audit_flags_non_library_category_without_special_rule():
    epg = parse_xmltv(
        """<tv>
        <programme data-media-type="" data-source="tmdb" data-confidence="7.1">
          <title>SportsCenter</title>
          <category>Sports - Football</category>
        </programme>
        </tv>"""
    )
    violations = audit_outputs(epg, build_genres_tree(), tmdb_available=True)
    assert "non_library_category_without_special_rule" in violations
