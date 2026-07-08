from xmltv_enricher.catalog import classifier_signature


def test_classifier_signature_is_stable_string_hash():
    signature = classifier_signature()
    assert isinstance(signature, str)
    assert len(signature) == 64
