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
    # Non-CELEX raw strings must be ignored so SPARQL never sees malformed tokens
    assert mod.candidate_celexes_for_raw("Treaty establishing the EEC (1957)") == []
    assert mod.candidate_celexes_for_raw("http://publications.europa.eu/resource/cellar/abc") == []


def test_write_acts_artifact_validates_with_legislation_acts(tmp_path):
    from data_extraction.legislation.acts import read_acts

    act = mod.CellarAct(
        identifier="32016R0679",
        document_type="regulation",
        title="GDPR",
        enacted_date="2016-04-27",
        enacted_year=2016,
        eli="http://data.europa.eu/eli/reg/2016/679/oj",
    )
    out = tmp_path / "legislation_cellar_sparql.jsonl"
    written = mod.write_acts_artifact({"32016R0679": act}, str(out))
    assert written == 1
    loaded = list(read_acts(str(out)))
    assert len(loaded) == 1
    assert loaded[0].identifier == "32016R0679"
    assert loaded[0].source_dataset == mod.SOURCE_DATASET


def test_cellar_appeal_sync_parses_fd100_and_builds_records():
    from data_extraction.case_context import cellar_appeal_sync as appeal_mod

    bindings = [
        {
            "celex": {"value": "62019CJ0001"},
            "tp": {"value": "http://publications.europa.eu/resource/authority/fd_100/ANNU"},
        },
        {
            "celex": {"value": "62019CJ0001"},
            "tp": {"value": "http://publications.europa.eu/resource/authority/fd_100/PVOI%3DOB"},
        },
    ]
    fd100 = appeal_mod.parse_fd100_bindings(bindings)
    assert fd100 == {"62019CJ0001": ["ANNU", "PVOI%3DOB"]}
    pairs = [
        {
            "a_id": 10,
            "a_ecli": "ECLI:EU:C:2021:1",
            "a_celex": "62019CJ0001",
            "a_date": "2021-03-10",
            "u_id": 5,
            "u_ecli": "ECLI:EU:T:2019:1",
            "u_celex": "62018TJ0001",
        }
    ]
    outcomes, statuses = appeal_mod.build_records(pairs, fd100)
    assert len(outcomes) == 1
    assert outcomes[0].outcome == "successful"
    assert outcomes[0].source_dataset == "cjeu_proc_type"
    assert len(statuses) == 1
    assert statuses[0].status == "overturned"
    assert statuses[0].case.ecli == "ECLI:EU:T:2019:1"
    assert statuses[0].related.ecli == "ECLI:EU:C:2021:1"


def test_rs_dictum_handles_xml_concatenated_section_headings():
    from data_extraction.case_context import rs_dictum

    text = "Overwegingen...\n4De beslissing\nDe rechtbank verklaart het beroep ongegrond.\nDit vonnis is gewezen door..."
    found, reason = rs_dictum.parse_dictum(text)
    assert reason == "ok"
    assert found[0][0] == "dismissed"

    rvs_text = "8Beslissing\nDe Afdeling:\nverklaart het hoger beroep gegrond;\nvernietigt de uitspraak.\nAldus vastgesteld"
    found2, reason2 = rs_dictum.parse_dictum(rvs_text)
    assert reason2 == "ok"
    assert {f[0] for f in found2} == {"upheld", "quashed"}
