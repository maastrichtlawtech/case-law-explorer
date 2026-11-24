"""
Link artifact and link loader.

The artifact tests are pure. The loader tests need a real Postgres (the
loader's correctness is in its SQL: partial-index arbiters, ON CONFLICT,
cascades), so they run only when CLE_TEST_PG_DSN points at a server where
the test may create and drop a scratch database, e.g.

    CLE_TEST_PG_DSN=postgresql://postgres:test@localhost:5432/postgres

The schema is built from db/schema.sql, which mirrors the deployed migrations.
"""

import json

import pytest

from data_extraction.linking.artifact import (
    ArtifactError,
    ArtifactWriter,
    CaseKey,
    DatasetWriters,
    LinkRecord,
    Mention,
    match_method,
    read_jsonl,
    write_jsonl,
)
from tests.linking_db import DSN, needs_db, scratch_db  # noqa: F401


def _record(**overrides):
    value = {
        "source": {"ecli": "ECLI:NL:RVS:2020:423"},
        "target": {"ecli": "ECLI:EU:C:2019:189"},
        "target_ref_raw": "C-221/17",
        "target_ref_scheme": "cjeu_case_number",
        "relation_type": "cites",
        "source_dataset": "rs_text_cjeu_casenum",
        "extractor_version": "rs_text/test",
        "match_method": "case_number/cjeu_judgment",
        "confidence": 0.9,
        "mentions": [
            {
                "text_field": "fulltext",
                "language": "nl",
                "text_source": "RECHTSPRAAK",
                "char_start": 10,
                "char_end": 18,
                "raw_text": "C‑221/17",
            }
        ],
    }
    value.update(overrides)
    return value


# ---------------------------------------------------------------------------
# artifact
# ---------------------------------------------------------------------------


def test_record_round_trip(tmp_path):
    record = LinkRecord.from_dict(_record())
    path = tmp_path / "links.jsonl"
    assert write_jsonl([record], path) == 1
    assert list(read_jsonl(path)) == [record]


def test_write_is_sorted_and_stable(tmp_path):
    a = LinkRecord.from_dict(_record(source={"ecli": "ECLI:NL:B:2020:1"}))
    b = LinkRecord.from_dict(_record(source={"ecli": "ECLI:NL:A:2020:1"}))
    first, second = tmp_path / "1.jsonl", tmp_path / "2.jsonl"
    write_jsonl([a, b], first)
    write_jsonl([b, a], second)
    assert first.read_bytes() == second.read_bytes()


def _streamed(path, batches):
    with ArtifactWriter(path) as writer:
        for batch in batches:
            writer.write(batch)
    return writer.count


def test_streamed_artifact_is_the_same_bytes_whatever_the_order_within_a_batch(tmp_path):
    """Finding 6: extractors write batch by batch (cases in id order). The same
    records arriving in another order within their batch give the same file."""
    records = [
        LinkRecord.from_dict(
            _record(source={"ecli": f"ECLI:NL:RVS:2020:{i}"}, extractor_version=f"v{i % 3}")
        )
        for i in range(12)
    ]
    batches = [records[:5], records[5:9], records[9:]]
    first, second = tmp_path / "1.jsonl", tmp_path / "2.jsonl"
    assert _streamed(first, batches) == 12
    reordered = [list(reversed(batches[0])), batches[1][2:] + batches[1][:2], batches[2][::-1]]
    assert _streamed(second, reordered) == 12
    assert first.read_bytes() == second.read_bytes()
    lines = first.read_text().splitlines()
    # sorted within each batch, batches in the order given
    assert lines[:5] == sorted(lines[:5]) and lines[5:9] == sorted(lines[5:9])
    assert {json.loads(line)["source"]["ecli"] for line in lines[:5]} == {
        r.source.ecli for r in batches[0]
    }
    assert {json.loads(line)["source"]["ecli"] for line in lines[5:9]} == {
        r.source.ecli for r in batches[1]
    }


def test_streamed_artifact_is_complete_or_absent(tmp_path):
    path = tmp_path / "links.jsonl"
    with pytest.raises(RuntimeError):
        with ArtifactWriter(path) as writer:
            writer.write([LinkRecord.from_dict(_record())])
            raise RuntimeError("extractor failed")
    assert list(tmp_path.iterdir()) == []
    assert ArtifactWriter(None).write([LinkRecord.from_dict(_record())]) == 1  # counts only


def test_dataset_writers_split_and_refuse_unknown_datasets(tmp_path):
    a = LinkRecord.from_dict(_record(source_dataset="rs_text_cjeu_casenum"))
    b = LinkRecord.from_dict(_record(source_dataset="rs_text_ecli", match_method="ecli"))
    paths = {d: str(tmp_path / f"{d}.jsonl") for d in ("rs_text_ecli", "rs_text_cjeu_casenum")}
    paths["rs_text_echr_appno"] = str(tmp_path / "rs_text_echr_appno.jsonl")
    with DatasetWriters(paths) as writers:
        assert writers.write([a, b]) == 2
    assert writers.counts == {"rs_text_ecli": 1, "rs_text_cjeu_casenum": 1, "rs_text_echr_appno": 0}
    assert (tmp_path / "rs_text_echr_appno.jsonl").read_text() == ""
    with pytest.raises(ArtifactError, match="not expected"):
        with DatasetWriters({"rs_text_ecli": str(tmp_path / "x.jsonl")}) as writers:
            writers.write([a])
    assert not (tmp_path / "x.jsonl").exists()


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"source": {}}, "needs source"),
        ({"source": {"case_id": 1}}, "unknown case key"),
        ({"target": None, "target_ref_raw": None, "target_ref_scheme": None}, "needs a target"),
        ({"target_ref_scheme": "bogus"}, "known scheme"),
        ({"target_ref_raw": None}, "without target_ref_raw"),
        ({"confidence": 1.5}, "between 0 and 1"),
        ({"target": {"ecli": "ECLI:NL:RVS:2020:423"}}, "itself"),
        ({"mentions": [{"text_field": "body", "raw_text": "x"}]}, "text_field"),
        ({"mentions": [{"text_field": "summary", "raw_text": "x", "char_start": 3}]}, "together"),
        (
            {
                "mentions": [
                    {"text_field": "summary", "raw_text": "x", "char_start": 5, "char_end": 2}
                ]
            },
            "bad offsets",
        ),
    ],
)
def test_invalid_records_are_refused(overrides, message):
    with pytest.raises(ArtifactError, match=message):
        LinkRecord.from_dict(_record(**overrides))


def test_read_names_the_bad_line(tmp_path):
    path = tmp_path / "links.jsonl"
    good = json.dumps(_record())
    path.write_text(good + "\n" + json.dumps(_record(confidence=7)) + "\n")
    with pytest.raises(ArtifactError, match=r"links.jsonl:2"):
        list(read_jsonl(path))


def test_match_method_convention():
    assert match_method("case_number", "cjeu_judgment") == "case_number/cjeu_judgment"
    assert match_method("ecli") == match_method("ecli", "ecli") == "ecli"
    with pytest.raises(ArtifactError, match="unknown match method"):
        match_method("guess", "x")


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"match_method": "cjeu_judgment"}, "bad match_method"),
        ({"match_method": "case_number/"}, "bad match_method"),
        ({"target": None, "match_method": "case_number/cjeu_judgment"}, "method alone"),
        ({"target": None, "match_method": "case_number", "confidence": 0.9}, "no confidence"),
    ],
)
def test_match_method_is_validated(overrides, message):
    with pytest.raises(ArtifactError, match=message):
        LinkRecord.from_dict(_record(**overrides))


def test_case_key_drops_empty_fields():
    assert CaseKey.from_dict({"ecli": "E", "celex": ""}).to_dict() == {"ecli": "E"}
    assert Mention.from_dict({"text_field": "metadata", "raw_text": "x"}).char_start is None


# ---------------------------------------------------------------------------
# loader, against a real database
# ---------------------------------------------------------------------------


@pytest.fixture
def conn(scratch_db):  # noqa: F811
    with scratch_db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO cle_v2.cases (ecli, celex_id, sources) VALUES
              ('ECLI:NL:RVS:2020:423', NULL, '{RS}'),
              ('ECLI:EU:C:2019:189', '62017CJ0221', '{CJEU}'),
              ('ECLI:NL:HR:2020:593', NULL, '{RS}');
            INSERT INTO cle_v2.case_text (case_id, language, source, fulltext)
            SELECT id, 'nl', 'RECHTSPRAAK', 'tekst' FROM cle_v2.cases
             WHERE ecli = 'ECLI:NL:RVS:2020:423';
            """)
    scratch_db.commit()
    yield scratch_db


def _rows(conn, sql):
    with conn.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


@needs_db
def test_loader_inserts_resolved_row_with_provenance_and_mention(conn):
    from data_loading.link_loader import load_records

    counts = load_records(conn, [LinkRecord.from_dict(_record())])
    assert counts == {"rs_text_cjeu_casenum": {"inserted": 1, "mentions_inserted": 1}}
    rows = _rows(
        conn,
        """
        SELECT s.ecli, t.ecli, cc.match_method, cc.confidence, cc.target_ref_raw,
               cc.is_cross_jurisdiction, cc.weight, m.raw_text, m.case_text_id IS NOT NULL
          FROM cle_v2.case_citation cc
          JOIN cle_v2.cases s ON s.id = cc.source_case_id
          JOIN cle_v2.cases t ON t.id = cc.target_case_id
          JOIN cle_v2.case_citation_mention m ON m.citation_id = cc.id
        """,
    )
    assert rows == [
        (
            "ECLI:NL:RVS:2020:423",
            "ECLI:EU:C:2019:189",
            "case_number/cjeu_judgment",
            pytest.approx(0.9),
            "C-221/17",
            True,
            1,
            "C‑221/17",
            True,
        )
    ]


@needs_db
def test_loader_is_idempotent_and_adds_new_mentions(conn):
    from data_loading.link_loader import load_records

    load_records(conn, [LinkRecord.from_dict(_record())])
    again = _record()
    again["mentions"].append({"text_field": "summary", "language": "nl", "raw_text": "C-221/17"})
    counts = load_records(conn, [LinkRecord.from_dict(again)])
    assert counts == {"rs_text_cjeu_casenum": {"existing": 1, "mentions_inserted": 1}}
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation") == [(1,)]
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation_mention") == [(2,)]


@needs_db
def test_loader_writes_missing_target_unresolved_and_reference_only(conn):
    from data_loading.link_loader import load_records

    records = [
        # target not in this database: kept by its ECLI for late binding
        _record(
            target={"ecli": "ECLI:EU:C:2013:720"},
            target_ref_raw="C-199/12",
            source_dataset="rs_text_ecli",
        ),
        # nothing matched: kept by reference
        _record(
            target=None,
            target_ref_raw="C-999/99",
            source_dataset="rs_text_cjeu_casenum",
            match_method="case_number",
            confidence=None,
        ),
        # source case absent: skipped
        _record(source={"ecli": "ECLI:NL:XX:2020:1"}),
    ]
    first = load_records(conn, [LinkRecord.from_dict(r) for r in records])
    second = load_records(conn, [LinkRecord.from_dict(r) for r in records])
    assert first == {
        "rs_text_ecli": {"inserted_unresolved": 1, "mentions_inserted": 1},
        "rs_text_cjeu_casenum": {
            "inserted_unresolved": 1,
            "mentions_inserted": 1,
            "source_missing": 1,
        },
    }
    assert second == {
        "rs_text_ecli": {"existing": 1},
        "rs_text_cjeu_casenum": {"existing": 1, "source_missing": 1},
    }
    rows = _rows(
        conn,
        """
        SELECT source_dataset, target_ecli_raw, target_ref_raw, target_ref_scheme,
               is_cross_jurisdiction
          FROM cle_v2.case_citation ORDER BY source_dataset
        """,
    )
    assert rows == [
        ("rs_text_cjeu_casenum", None, "C-999/99", "cjeu_case_number", False),
        ("rs_text_ecli", "ECLI:EU:C:2013:720", "C-199/12", "cjeu_case_number", True),
    ]


@needs_db
def test_dataset_is_removed_with_one_delete(conn):
    from data_loading.link_loader import load_records

    load_records(conn, [LinkRecord.from_dict(_record())])
    with conn.cursor() as cursor:
        cursor.execute(
            "DELETE FROM cle_v2.case_citation WHERE source_dataset = 'rs_text_cjeu_casenum'"
        )
    conn.commit()
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation_mention") == [(0,)]


# ---------------------------------------------------------------------------
# late binding (R2.9), against a real database
# ---------------------------------------------------------------------------


def _add_case(conn, ecli=None, celex=None, sources=("CJEU",), decided=None, item_id=None):
    with conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO cle_v2.cases (ecli, celex_id, item_id, date_decision, sources)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (ecli, celex, item_id, decided, list(sources)),
        )
        (case_id,) = cursor.fetchone()
    conn.commit()
    return case_id


def _identifier(conn, case_id, scheme, value, normalized=None):
    with conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO cle_v2.case_identifier (case_id, scheme, value, value_normalized, source)
               VALUES (%s, %s, %s, %s, 'test')""",
            (case_id, scheme, value, normalized or value),
        )
    conn.commit()


def _ref(dataset, scheme, value, method, **overrides):
    """An unresolved reference record from ECLI:NL:RVS:2020:423."""
    return _record(
        target=None,
        target_ref_raw=value,
        target_ref_scheme=scheme,
        source_dataset=dataset,
        match_method=method,
        confidence=None,
        **overrides,
    )


def _citations(conn):
    return _rows(
        conn,
        """
        SELECT cc.source_dataset, t.ecli, cc.target_ecli_raw, cc.target_celex_raw,
               cc.target_ref_raw, cc.match_method, cc.confidence, cc.is_cross_jurisdiction,
               cc.extractor_version, cc.weight,
               (SELECT count(*) FROM cle_v2.case_citation_mention m WHERE m.citation_id = cc.id)
          FROM cle_v2.case_citation cc
          LEFT JOIN cle_v2.cases t ON t.id = cc.target_case_id
         ORDER BY cc.source_dataset, cc.target_case_id NULLS FIRST, cc.id
        """,
    )


@needs_db
def test_late_binding_resolves_ecli_and_celex_rows_and_copies_mentions(conn):
    from data_loading.link_loader import load_records, resolve_late

    two_mentions = _record()["mentions"] + [
        {"text_field": "summary", "language": "nl", "raw_text": "EU:C:2013:720"}
    ]
    load_records(
        conn,
        [
            LinkRecord.from_dict(r)
            for r in (
                _record(
                    target={"ecli": "ECLI:EU:C:2013:720"},
                    target_ref_raw=None,
                    target_ref_scheme=None,
                    source_dataset="rs_text_ecli",
                    match_method="ecli",
                    confidence=1.0,
                    mentions=two_mentions,
                ),
                _record(
                    target={"celex": "62012CJ0199"},
                    target_ref_raw=None,
                    target_ref_scheme=None,
                    source_dataset="cellar_relation_resolved",
                    match_method="celex/uuid_celex",
                    confidence=0.95,
                    mentions=[],
                ),
                # an alias ECLI of the new case, through case_identifier
                _record(
                    target={"ecli": "ECLI:EU:C:2013:999"},
                    target_ref_raw=None,
                    target_ref_scheme=None,
                    source_dataset="echr_text_cjeu",
                    match_method="ecli",
                    confidence=0.99,
                ),
            )
        ],
    )
    new = _add_case(conn, "ECLI:EU:C:2013:720", "62012CJ0199", decided="2013-11-21")
    _identifier(conn, new, "ecli", "ECLI:EU:C:2013:999")
    unrelated = _add_case(conn, "ECLI:EU:C:2014:1", "62013CJ0001")

    counts = resolve_late(conn, [new, unrelated])
    assert counts == {
        "rs_text_ecli": {"matched": 1, "resolved_inserted": 1, "mentions_copied": 2},
        "cellar_relation_resolved": {"matched": 1, "resolved_inserted": 1},
        "echr_text_cjeu": {"matched": 1, "resolved_inserted": 1, "mentions_copied": 1},
    }
    tag = "rs_text/test"
    assert _citations(conn) == [
        # the unresolved rows stay; each has a resolved twin
        ("cellar_relation_resolved", None, None, "62012CJ0199", None, "celex/uuid_celex",
         pytest.approx(0.95), True, tag, 1, 0),
        ("cellar_relation_resolved", "ECLI:EU:C:2013:720", None, None, None, "celex/uuid_celex",
         pytest.approx(0.95), True, tag, 1, 0),
        ("echr_text_cjeu", None, "ECLI:EU:C:2013:999", None, None, "ecli",
         pytest.approx(0.99), True, tag, 1, 1),
        ("echr_text_cjeu", "ECLI:EU:C:2013:720", None, None, None, "ecli",
         pytest.approx(0.99), True, tag, 1, 1),
        ("rs_text_ecli", None, "ECLI:EU:C:2013:720", None, None, "ecli", 1.0, True, tag, 2, 2),
        ("rs_text_ecli", "ECLI:EU:C:2013:720", None, None, None, "ecli", 1.0, True, tag, 2, 2),
    ]  # fmt: skip
    copied = _rows(
        conn,
        """SELECT m.text_field, m.raw_text, m.char_start, m.case_text_id IS NOT NULL
             FROM cle_v2.case_citation_mention m
             JOIN cle_v2.case_citation cc ON cc.id = m.citation_id
            WHERE cc.source_dataset = 'rs_text_ecli' AND cc.target_case_id IS NOT NULL
            ORDER BY m.text_field""",
    )
    assert copied == [("fulltext", "C‑221/17", 10, True), ("summary", "EU:C:2013:720", None, False)]

    # idempotent: a second run (or an overlapping range) inserts nothing
    again = resolve_late(conn, [new])
    assert again == {
        "rs_text_ecli": {"matched": 1},
        "cellar_relation_resolved": {"matched": 1},
        "echr_text_cjeu": {"matched": 1},
    }
    assert len(_citations(conn)) == 6


@needs_db
def test_late_binding_chooses_references_with_the_resolver(conn):
    from data_loading.link_loader import load_records, resolve_late

    _rows(conn, "UPDATE cle_v2.cases SET date_decision = '2020-03-01' RETURNING id")
    load_records(
        conn,
        [
            LinkRecord.from_dict(_ref("rs_text_cjeu_casenum", "cjeu_case_number", "C-5/18",
                                      "case_number")),
            LinkRecord.from_dict(_ref("rs_text_echr_appno", "echr_appno", "12345/67", "appno")),
        ],
    )  # fmt: skip
    opinion = _add_case(conn, "ECLI:EU:C:2018:900", "62018CC0005", decided="2018-11-01")
    judgment = _add_case(conn, "ECLI:EU:C:2019:300", "62018CJ0005", decided="2019-04-01")
    interim = _add_case(conn, "ECLI:EU:C:2018:100", "62018CO0005", decided="2018-02-01")
    _identifier(conn, opinion, "cjeu_case_number", "C-5/18")
    _identifier(conn, judgment, "cjeu_case_number", "C-5/18")
    _identifier(conn, interim, "cjeu_case_number", "C-5/18 R", "C-5/18")
    echr = _add_case(conn, "ECLI:CE:ECHR:2010:0101JUD001234567", sources=("ECHR",),
                     decided="2010-01-01", item_id="001-1")  # fmt: skip
    _identifier(conn, echr, "echr_appno", "12345/67")
    _rows(
        conn,
        f"""INSERT INTO cle_v2.echr_document (item_id, case_id, language, doctype)
            VALUES ('001-1', {echr}, 'en', 'HEJUD') RETURNING item_id""",
    )
    conn.commit()

    counts = resolve_late(conn, [opinion, judgment, interim, echr])
    assert counts == {
        "rs_text_cjeu_casenum": {"matched": 1, "resolved_inserted": 1, "mentions_copied": 1},
        "rs_text_echr_appno": {"matched": 1, "resolved_inserted": 1, "mentions_copied": 1},
    }
    resolved = [row for row in _citations(conn) if row[1] is not None]
    assert [row[:8] for row in resolved] == [
        ("rs_text_cjeu_casenum", "ECLI:EU:C:2019:300", None, None, "C-5/18",
         "case_number/cjeu_judgment", pytest.approx(0.95), True),
        ("rs_text_echr_appno", "ECLI:CE:ECHR:2010:0101JUD001234567", None, None, "12345/67",
         "appno/echr_judgment", pytest.approx(0.95), True),
    ]  # fmt: skip
    assert resolve_late(conn, [judgment, echr]) == {
        "rs_text_cjeu_casenum": {"matched": 1},
        "rs_text_echr_appno": {"matched": 1},
    }


@needs_db
def test_late_binding_leaves_ambiguous_references_alone(conn):
    from data_loading.link_loader import load_records, resolve_late

    _rows(conn, "UPDATE cle_v2.cases SET date_decision = '2020-03-01' RETURNING id")
    load_records(
        conn,
        [
            LinkRecord.from_dict(r)
            for r in (
                # an LJN shared by two decisions: not guessed between
                _ref("echr_text_rs", "ljn", "BK1234", "ljn"),
                # the only document of the number is dated after the source
                _ref("rs_text_cjeu_casenum", "cjeu_case_number", "C-8/21", "case_number"),
                # the number has only an interim order
                _ref("rs_text_cjeu_casenum", "cjeu_case_number", "C-9/19", "case_number"),
            )
        ],
    )
    ljn_a = _add_case(conn, "ECLI:NL:RBAMS:2010:BK1234", sources=("RS",), decided="2010-01-01")
    ljn_b = _add_case(conn, "ECLI:NL:RBAMS:2010:1", sources=("RS",), decided="2010-01-01")
    later = _add_case(conn, "ECLI:EU:C:2022:5", "62021CJ0008", decided="2022-01-01")
    interim = _add_case(conn, "ECLI:EU:C:2019:5", "62019CO0009", decided="2019-01-01")
    _identifier(conn, ljn_a, "ljn", "BK1234")
    _identifier(conn, ljn_b, "ljn", "BK1234")
    _identifier(conn, later, "cjeu_case_number", "C-8/21")
    _identifier(conn, interim, "cjeu_case_number", "C-9/19 R", "C-9/19")

    counts = resolve_late(conn, [ljn_a, ljn_b, later, interim])
    assert counts == {
        "echr_text_rs": {"ref_left_unresolved": 1},
        "rs_text_cjeu_casenum": {"ref_left_unresolved": 2},
    }
    assert _rows(conn, "SELECT count(*), count(target_case_id) FROM cle_v2.case_citation") == [
        (3, 0)
    ]


@needs_db
def test_late_binding_ignores_legacy_datasets(conn):
    from data_loading.link_loader import resolve_late

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO cle_v2.case_citation
                (source_case_id, target_ecli_raw, target_celex_raw, relation_type, source_dataset)
            SELECT id, 'ECLI:EU:C:2013:720', NULL, 'cites', 'rs_body_cite'
              FROM cle_v2.cases WHERE ecli = 'ECLI:NL:RVS:2020:423'
            UNION ALL
            SELECT id, NULL, '62012CJ0199', 'cites', 'cellar_sparql'
              FROM cle_v2.cases WHERE ecli = 'ECLI:NL:HR:2020:593'
            """)
    conn.commit()
    new = _add_case(conn, "ECLI:EU:C:2013:720", "62012CJ0199")
    assert resolve_late(conn, [new]) == {}
    assert _rows(conn, "SELECT count(*), count(target_case_id) FROM cle_v2.case_citation") == [
        (2, 0)
    ]


@needs_db
def test_dataset_delete_cascades_after_late_binding(conn):
    from data_loading.link_loader import load_records, resolve_late

    load_records(
        conn,
        [
            LinkRecord.from_dict(
                _record(
                    target={"ecli": "ECLI:EU:C:2013:720"},
                    target_ref_raw=None,
                    target_ref_scheme=None,
                    source_dataset="rs_text_ecli",
                    match_method="ecli",
                    confidence=1.0,
                )
            )
        ],
    )
    new = _add_case(conn, "ECLI:EU:C:2013:720")
    assert resolve_late(conn, [new])["rs_text_ecli"]["resolved_inserted"] == 1
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM cle_v2.case_citation WHERE source_dataset = 'rs_text_ecli'")
        assert cursor.rowcount == 2
    conn.commit()
    assert _rows(conn, "SELECT count(*) FROM cle_v2.case_citation_mention") == [(0,)]


@needs_db
def test_cli_load_and_resolve_late(conn, tmp_path, monkeypatch, capsys):
    from data_loading import link_loader

    base, _, _ = DSN.rpartition("/")
    name = _rows(conn, "SELECT current_database()")[0][0]
    monkeypatch.setenv("LINK_LOADER_TEST_DSN", f"{base}/{name}")
    path = tmp_path / "links.jsonl"
    record = _record(target={"ecli": "ECLI:EU:C:2013:720"}, target_ref_raw=None,
                     target_ref_scheme=None, source_dataset="rs_text_ecli",
                     match_method="ecli", confidence=1.0)  # fmt: skip
    write_jsonl([LinkRecord.from_dict(record)], path)
    assert link_loader.main(["load", "--dsn-env", "LINK_LOADER_TEST_DSN", str(path)]) == 0
    loaded = json.loads(capsys.readouterr().out)
    assert loaded == {
        str(path): {"rs_text_ecli": {"inserted_unresolved": 1, "mentions_inserted": 1}}
    }
    new = _add_case(conn, "ECLI:EU:C:2013:720")
    argv = ["resolve-late", "--dsn-env", "LINK_LOADER_TEST_DSN", "--from-id", str(new)]
    assert link_loader.main(argv + ["--to-id", str(new)]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "rs_text_ecli": {"matched": 1, "resolved_inserted": 1, "mentions_copied": 1}
    }


# ---------------------------------------------------------------------------
# bulk loading: same result as one record at a time
# ---------------------------------------------------------------------------


def _bulk_records(n):
    """n records full of conflicts: the same resolved pair again and again,
    unresolved rows overlapping on their ECLI and on their case number, missing
    sources, item_id-only targets, repeated mentions."""
    out = []
    for i in range(n):
        source = {"ecli": f"ECLI:NL:RVS:2021:{i % 50}"}
        if i % 13 == 0:
            source = {"ecli": f"ECLI:NL:RVS:1999:{i}"}  # not in the database
        mentions = [
            {
                "text_field": "fulltext",
                "language": "nl",
                "text_source": "RECHTSPRAAK" if i % 3 else None,
                "char_start": 10 * j + i % 5,
                "char_end": 10 * j + i % 5 + 8,
                "raw_text": f"ref {i % 7}",
                "segment_hash": f"h{i % 4}" if j else None,
            }
            for j in range(i % 3)
        ]
        value = {
            "source": source,
            "relation_type": "cites" if i % 11 else "applies",
            "extractor_version": f"bulk/{i % 2}",
            "mentions": mentions,
        }
        kind = i % 5
        if kind == 0:  # resolved, pairs repeat across and within batches
            value.update(
                target={"ecli": f"ECLI:EU:C:2019:{i % 300}"},
                source_dataset="rs_text_ecli",
                match_method="ecli",
                confidence=round(0.5 + (i % 5) / 10, 2),
            )
        elif kind == 1:  # target not loaded: unresolved by ECLI, sometimes with a case number
            value.update(
                target={"ecli": f"ECLI:EU:C:2099:{i % 200}"},
                source_dataset="rs_text_cjeu_casenum",
                match_method="case_number/cjeu_judgment",
                confidence=0.9,
            )
            if i % 2:
                value.update(target_ref_raw=f"C-{i % 70}/17", target_ref_scheme="cjeu_case_number")
        elif kind == 2:  # a reference only, overlapping the case numbers above
            value.update(
                target=None,
                target_ref_raw=f"C-{i % 70}/17",
                target_ref_scheme="cjeu_case_number",
                source_dataset="rs_text_cjeu_casenum",
                match_method="case_number",
            )
        elif kind == 3:  # target by CELEX, absent
            value.update(
                target={"celex": f"62099CJ{i % 90:04d}"},
                source_dataset="rs_text_ecli",
                match_method="celex",
                confidence=0.8,
            )
        else:  # every fourth one names its target by an item_id nothing has
            item = f"001-{i % 400}" if i % 4 else f"001-absent-{i}"
            value.update(
                target={"item_id": item}, source_dataset="echr_text_rs", match_method="ecli"
            )
        out.append(LinkRecord.from_dict(value))
    return out


def _bulk_seed(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            TRUNCATE cle_v2.case_citation, cle_v2.case_citation_mention RESTART IDENTITY CASCADE;
            INSERT INTO cle_v2.cases (ecli, sources)
            SELECT 'ECLI:NL:RVS:2021:' || g, '{RS}' FROM generate_series(0, 49) g
            ON CONFLICT DO NOTHING;
            INSERT INTO cle_v2.cases (ecli, sources)
            SELECT 'ECLI:EU:C:2019:' || g, '{CJEU}' FROM generate_series(0, 299) g
            ON CONFLICT DO NOTHING;
            INSERT INTO cle_v2.cases (item_id, sources)
            SELECT '001-' || g, '{ECHR}' FROM generate_series(0, 399) g
            ON CONFLICT DO NOTHING;
            INSERT INTO cle_v2.case_text (case_id, language, source, fulltext)
            SELECT id, 'nl', 'RECHTSPRAAK', 'tekst' FROM cle_v2.cases
             WHERE ecli LIKE 'ECLI:NL:RVS:2021:%'
            ON CONFLICT DO NOTHING;
            INSERT INTO cle_v2.case_segment (case_id, segment_hash)
            SELECT c.id, 'h' || g FROM cle_v2.cases c, generate_series(0, 2) g
             WHERE c.ecli LIKE 'ECLI:NL:RVS:2021:%'
            ON CONFLICT DO NOTHING;
            """)
    conn.commit()


def _bulk_state(conn):
    """Citation and mention rows without their ids (a batch inserts its
    resolved rows before its unresolved ones, so ids are numbered
    differently), each mention with its citation's values."""
    citations = {
        row[0]: row[1:]
        for row in _rows(
            conn,
            """SELECT id, source_case_id, target_case_id, target_ecli_raw, target_celex_raw,
                      target_ref_raw, target_ref_scheme, relation_type, source_dataset, weight,
                      is_cross_jurisdiction, extractor_version, match_method, confidence
                 FROM cle_v2.case_citation""",
        )
    }
    mentions = [
        (citations[row[0]],) + row[1:]
        for row in _rows(
            conn,
            """SELECT citation_id, case_text_id, text_field, language, char_start, char_end,
                      raw_text, context, segment_id, section, extractor_version
                 FROM cle_v2.case_citation_mention""",
        )
    ]
    return sorted(citations.values(), key=repr), sorted(mentions, key=repr)


@needs_db
def test_bulk_load_matches_loading_one_record_at_a_time(conn):
    """2,400 records in batches of 700 give the same counts and the same rows
    as batches of one, i.e. as inserting record by record."""
    from data_loading.link_loader import load_records

    records = _bulk_records(2400)
    results = []
    for batch_size in (1, 700):
        _bulk_seed(conn)
        before = load_records(conn, records[:300], batch_size=1)  # rows that already exist
        counts = load_records(conn, records, batch_size=batch_size)
        results.append((before, counts, _bulk_state(conn)))
    assert results[0] == results[1]
    _before, counts, (citations, mentions) = results[1]
    totals = {}
    for dataset_counts in counts.values():
        for key, value in dataset_counts.items():
            totals[key] = totals.get(key, 0) + value
    for key in (
        "inserted",
        "inserted_unresolved",
        "existing",
        "source_missing",
        "target_unwritable",
        "mentions_inserted",
    ):
        assert totals.get(key), key
    assert len(citations) > 300 and len(mentions) > 300
    assert any(m[1] is not None for m in mentions) and any(m[8] is not None for m in mentions)


@needs_db
def test_loader_finds_echr_variants_by_echr_document_item_id(conn):
    """A HUDOC variant's item_id is in echr_document, not in cases.item_id."""
    from data_loading.link_loader import load_records

    case_id = _add_case(conn, item_id="001-100", sources=("ECHR",))
    with conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO cle_v2.echr_document (item_id, case_id, language)
               VALUES ('001-100', %s, 'en'), ('001-200', %s, 'fr')""",
            (case_id, case_id),
        )
    conn.commit()
    record = _record(
        source={"item_id": "001-200"},
        target={"ecli": "ECLI:NL:HR:2020:593"},
        source_dataset="echr_text_rs",
        match_method="ecli",
        target_ref_raw=None,
        target_ref_scheme=None,
        mentions=[],
    )
    counts = load_records(conn, [LinkRecord.from_dict(record)])
    assert counts == {"echr_text_rs": {"inserted": 1}}
    assert _rows(
        conn, "SELECT source_case_id, is_cross_jurisdiction FROM cle_v2.case_citation"
    ) == [(case_id, True)]
