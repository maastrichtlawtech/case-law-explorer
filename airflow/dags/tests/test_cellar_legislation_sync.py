"""Unit tests for data_extraction.legislation.cellar_legislation_sync."""

import io
import json

from data_extraction.legislation import cellar_legislation_sync as mod


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_parse_sparql_bindings_en_and_fr_fallback():
    bindings = [
        {
            "celex": {"value": "32006L0112"},
            "title_en": {"value": "Council Directive 2006/112/EC on VAT"},
            "enacted_date": {"value": "2006-11-28"},
            "eli": {"value": "http://data.europa.eu/eli/dir/2006/112/oj"},
            "resource_type": {"value": "http://publications.europa.eu/resource/authority/resource-type/DIR"},
        },
        {
            "celex": {"value": "31968R0259(01)"},
            "title_fr": {"value": "Règlement (CEE) n° 259/68"},
            "enacted_date": {"value": "1968-02-29"},
            "resource_type": {"value": "http://publications.europa.eu/resource/authority/resource-type/REG"},
        },
    ]
    acts = mod.parse_sparql_bindings(bindings)
    assert acts["32006L0112"].document_type == "directive"
    assert acts["32006L0112"].enacted_year == 2006
    assert acts["32006L0112"].eli == "http://data.europa.eu/eli/dir/2006/112/oj"
    assert acts["31968R0259(01)"].title == "Règlement (CEE) n° 259/68"
    assert acts["31968R0259(01)"].document_type == "regulation"


def test_fetch_cellar_metadata_uses_xsd_string_values():
    seen_queries = []

    def fake_urlopen(req, timeout=60):
        seen_queries.append(req.data.decode("utf-8"))
        payload = {
            "results": {
                "bindings": [
                    {
                        "celex": {"value": "32009R0207"},
                        "title_en": {"value": "Community trade mark regulation"},
                        "enacted_date": {"value": "2009-02-26"},
                        "resource_type": {
                            "value": "http://publications.europa.eu/resource/authority/resource-type/REG"
                        },
                    }
                ]
            }
        }
        return _FakeResp(json.dumps(payload).encode("utf-8"))

    acts = mod.fetch_cellar_metadata(["32009R0207"], pause=0, urlopen=fake_urlopen)
    assert "32009R0207" in acts
    assert acts["32009R0207"].title == "Community trade mark regulation"
    assert "xsd%3Astring" in seen_queries[0]


def test_candidate_celexes_normalizes_treaty_article_and_consolidated():
    assert "12008E/TXT" in mod.candidate_celexes_for_raw("12008E267")
    assert "32016R0679" in mod.candidate_celexes_for_raw("02016R0679-20160504")
