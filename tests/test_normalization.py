from xmltv_enricher.normalization import normalize_title, title_candidates


def test_normalize_title_removes_noise():
    assert normalize_title("The Office HD S01E02") == "The Office"


def test_title_candidates_preserve_numeric_titles():
    assert title_candidates("2012") == ["2012"]
