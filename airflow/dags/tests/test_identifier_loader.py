"""
case_identifier loader (data_loading/identifier_loader.py).

The splitting tests are pure and use real values from the 2026-11-24
research files (cjeu-migration migration/verify/research-2026-11-24:
goldset/data.js, cjeu/cn_map.json, cjeu/uuid_dossier.json, cjeu/uuid_rows.json,
echr/nl_refs.txt, rs/allnums.txt), copied here so the tests stand alone.

The loader tests need a real Postgres and run only when CLE_TEST_PG_DSN
points at a server where the test may create and drop a scratch database
(see test_link_loader.py). The schema is built from db/schema.sql.
"""

import json

import pytest

from data_extraction.linking.identifiers import (
    normalize_cjeu_case_number,
    normalize_echr_appno,
    zaaknummer_variants,
)
from data_loading.identifier_loader import (
    case_number_from_celex,
    cellar_uuid,
    merge_counts,
    split_appnos,
    split_cjeu_case_numbers,
    split_ljns,
    split_zaaknummers,
)
from tests.linking_db import DSN, execute, needs_db, scratch_db  # noqa: F401

# ---------------------------------------------------------------------------
# splitting, pure
# ---------------------------------------------------------------------------

# cn_map.json keys (cjeu_document.case_number as stored in production): one
# number each, already normalised.
CN_MAP_SAMPLE = [
    "C-1/01",
    "C-1/19",
    "C-1/25",
    "C-10/06",
    "C-100/17",
    "C-101/11",
    "C-102/24",
    "C-199/12",
    "C-221/17",
    "T-131/16",
    "F-1/05",
]


@pytest.mark.parametrize("value", CN_MAP_SAMPLE)
def test_stored_case_number_is_one_identifier(value):
    assert split_cjeu_case_numbers(value) == [value]
    assert normalize_cjeu_case_number(value) == value


@pytest.mark.parametrize(
    "text, found, normalized",
    [
        # goldset/data.js caseno of ECLI:EU:C:2013:720
        (
            "C-199/12, C-200/12, C-201/12 (joined)",
            ["C-199/12", "C-200/12", "C-201/12"],
            ["C-199/12", "C-200/12", "C-201/12"],
        ),
        # how the CJEU's own texts write a joined range (U+2011 hyphens)
        (
            "gevoegde zaken C‑199/12 tot en met C‑201/12",
            ["C‑199/12", "C-200/12", "C‑201/12"],
            ["C-199/12", "C-200/12", "C-201/12"],
        ),
        ("C-199/12 to C-201/12", ["C-199/12", "C-200/12", "C-201/12"], None),
        # "TO" is also a suffix (third-party opposition) when no number follows
        ("T-12/20 TO", ["T-12/20 TO"], ["T-12/20"]),
        # French ECtHR texts: plain space
        ("C 199/12", ["C 199/12"], ["C-199/12"]),
        # rs/allnums.txt: leading zero
        ("C-04/19", ["C-04/19"], ["C-4/19"]),
        # uuid_dossier.json (Cellar dossier identifiers)
        ("C-406/16 P(R)", ["C-406/16 P"], ["C-406/16"]),
        ("case:C-297/22 P", ["C-297/22 P"], ["C-297/22"]),
        ("C-924/19 PPU", ["C-924/19 PPU"], ["C-924/19"]),
        ("case:T-462/19", ["T-462/19"], ["T-462/19"]),
        # pre-1989, no court letter
        ("26/62", ["26/62"], ["26/62"]),
    ],
)
def test_split_cjeu_case_numbers(text, found, normalized):
    assert split_cjeu_case_numbers(text) == found
    if normalized is not None:
        assert [normalize_cjeu_case_number(v) for v in found] == normalized


@pytest.mark.parametrize(
    "text",
    [
        "C-199/12 to C-201/13",  # different years: not a range
        "C-199/12 to T-201/12",  # different courts
        "C-1/12 to C-200/12",  # too long to be one joined batch
        "C-199/12, C-201/12",  # a list, not a range
    ],
)
def test_ranges_expand_only_within_court_year_and_limit(text):
    assert len(split_cjeu_case_numbers(text)) == 2


def test_unparseable_case_number_yields_nothing():
    assert split_cjeu_case_numbers("unknown") == []
    assert split_cjeu_case_numbers("") == []
    assert split_cjeu_case_numbers(None) == []


@pytest.mark.parametrize(
    "text, pieces",
    [
        # goldset/data.js caseno fields
        (
            "201504577/1/A3, 201507057/1/A3, 201508588/1/A3 en 201601993/1/A3",
            ["201504577/1/A3", "201507057/1/A3", "201508588/1/A3", "201601993/1/A3"],
        ),
        (
            "201504577/2/A3, 201507057/2/A3, 201508588/2/A3, 201601993/2/A3, "
            "201604943/1/A3 en 201608752/1/A3",
            [
                "201504577/2/A3",
                "201507057/2/A3",
                "201508588/2/A3",
                "201601993/2/A3",
                "201604943/1/A3",
                "201608752/1/A3",
            ],
        ),
        ("19/02010", ["19/02010"]),
        ("201012342/1/T1/V2", ["201012342/1/T1/V2"]),
        ("201109928/T1/V2", ["201109928/T1/V2"]),
        ("13/01234; 13/01235", ["13/01234", "13/01235"]),
        # a slash with spaces is part of one civil case number
        ("C/13/123456 / HA ZA 12-345", ["C/13/123456 / HA ZA 12-345"]),
    ],
)
def test_split_zaaknummers(text, pieces):
    assert split_zaaknummers(text) == pieces


def test_zaaknummer_variants_of_split_pieces():
    pieces = split_zaaknummers("201012342/1/T1/V2 en 201109928/T1/V2")
    assert [zaaknummer_variants(p) for p in pieces] == [
        ["201012342/1/T1/V2", "201012342/T1/V2"],
        ["201109928/T1/V2"],
    ]


@pytest.mark.parametrize(
    "text, ljns",
    [
        ("BW3076", ["BW3076"]),
        ("LJN BR0132", ["BR0132"]),  # echr/nl_refs.txt
        ("LJN: BJ3435", ["BJ3435"]),
        ("bh5761", ["bh5761"]),
        ("ECLI:NL:HR:2013:BZ3640", []),  # an ECLI is not an LJN
        ("201012342/1/T1/V2", []),
        ("", []),
    ],
)
def test_split_ljns(text, ljns):
    assert split_ljns(text) == ljns


def test_split_appnos_goldset():
    values = split_appnos("52273/16; 52285/16; 52290/16; 52294/16; 52302/16")
    assert [normalize_echr_appno(v) for v in values] == [
        "52273/16",
        "52285/16",
        "52290/16",
        "52294/16",
        "52302/16",
    ]
    assert split_appnos("17341/03") == ["17341/03"]


def test_cellar_uuid_and_case_number_from_celex():
    # cjeu/uuid_rows.json
    uri = "http://publications.europa.eu/resource/cellar/9787a9ff-fdbf-11e6-8a35-01aa75ed71a1"
    assert cellar_uuid(uri) == "9787a9ff-fdbf-11e6-8a35-01aa75ed71a1"
    assert cellar_uuid("62015CJ0404") is None
    assert case_number_from_celex("62012CJ0199") == "C-199/12"
    assert case_number_from_celex("62019TO0395(01)") == "T-395/19"
    assert case_number_from_celex("32011L0095") is None


def test_merge_counts_keeps_twenty_examples():
    total = {}
    part = {
        "schemes": {"ecli": {"inserted": 2}},
        "examples": {"ecli": [{"v": i} for i in range(15)]},
    }
    merge_counts(total, part)
    merge_counts(total, part)
    assert total["schemes"]["ecli"]["inserted"] == 4
    assert len(total["examples"]["ecli"]) == 20


def test_maintenance_is_off_by_default(monkeypatch):
    from data_loading import identifier_loader

    monkeypatch.delenv(identifier_loader.FLAG, raising=False)

    class Exploding:
        def transaction(self):
            raise AssertionError("must not touch the database")

    assert identifier_loader.maintain_for_keys(Exploding(), "ecli", ["ECLI:X"]) is None
    assert identifier_loader.record_echr_owner_appnos(Exploding(), [("001-1", "1/01")]) == 0


# ---------------------------------------------------------------------------
# loader, against a real database
# ---------------------------------------------------------------------------

DOSSIER_200 = "http://publications.europa.eu/resource/cellar/aaaaaaaa-0000-0000-0000-000000000200"
DOSSIER_UNKNOWN = (
    "http://publications.europa.eu/resource/cellar/bbbbbbbb-0000-0000-0000-000000000999"
)

FIXTURE_SQL = f"""
INSERT INTO cle_v2.cases (id, ecli, celex_id, item_id, case_number, sources)
OVERRIDING SYSTEM VALUE VALUES
  (1, 'ECLI:EU:C:2013:720', '62012CJ0199', NULL, 'C-199/12', '{{CJEU}}'),
  (2, 'ECLI:EU:C:2013:999', '62012CO0200', NULL, 'C-200/12', '{{CJEU}}'),
  (3, 'ECLI:EU:C:2019:189', '62017CJ0221', NULL, 'C-221/17', '{{CJEU}}'),
  (10, 'ECLI:CE:ECHR:2004:0622DEC001734103', NULL, '001-1', '17341/03', '{{ECHR}}'),
  (20, 'ECLI:NL:RVS:2012:BW3076', NULL, NULL, NULL, '{{RS}}'),
  (21, 'ECLI:NL:RVS:2020:423', NULL, NULL, NULL, '{{RS}}'),
  (22, 'bogus-ecli', NULL, NULL, NULL, '{{RS}}');
INSERT INTO cle_v2.cjeu_document (case_id, celex_id, ecli, case_number, dossier_uri) VALUES
  (1, '62012CJ0199', 'ECLI:EU:C:2013:720', 'C-199/12', NULL),
  (2, '62012CO0200', 'ECLI:EU:C:2013:999', 'C-200/12', '{DOSSIER_200}'),
  (3, '62017CJ0221', 'ECLI:EU:C:2019:189', 'C-221/17', NULL);
-- joins of case 1: a member resolved through another document's dossier, a
-- member named by CELEX that we do not hold, and one we cannot resolve.
INSERT INTO cle_v2.case_citation (source_case_id, target_case_id, target_celex_raw,
                                  relation_type, source_dataset) VALUES
  (1, NULL, '{DOSSIER_200}', 'joins', 'cellar_sparql'),
  (1, NULL, '62012CJ0201', 'joins', 'cellar_sparql'),
  (1, NULL, '{DOSSIER_UNKNOWN}', 'joins', 'cellar_sparql'),
  (1, 3, '62017CJ0221', 'cites', 'cellar_sparql'),
  -- a 'joins' row of another dataset is not Cellar's join
  (1, NULL, '62012CJ0202', 'joins', 'cellar_relation_resolved');
INSERT INTO cle_v2.echr_document (item_id, case_id, language, extractedappno) VALUES
  ('001-1', 10, 'en', '17341/03;12345/99');
INSERT INTO cle_v2.echr_document_appno (item_id, appno, source) VALUES
  ('001-1', '17341/03', 'appno'),
  ('001-1', '12345/99', 'extractedappno');
INSERT INTO cle_v2.rs_document (case_id, zaaknummer, replaces_identifier) VALUES
  (20, '201012342/1/T1/V2 en 201109928/T1/V2', 'BW3076'),
  (21, '201504577/1/A3, 201507057/1/A3', 'ECLI:NL:XX:2020:1');
"""


@pytest.fixture
def conn(scratch_db):  # noqa: F811
    with scratch_db.cursor() as cursor:
        cursor.execute(FIXTURE_SQL)
    scratch_db.commit()
    yield scratch_db


def _identifiers(conn, case_id=None):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT case_id, scheme, value, value_normalized, source, is_primary
              FROM cle_v2.case_identifier
             WHERE %(case_id)s::bigint IS NULL OR case_id = %(case_id)s
             ORDER BY case_id, scheme, value_normalized
            """,
            {"case_id": case_id},
        )
        return cursor.fetchall()


@needs_db
def test_cjeu_case_numbers_celex_ecli_and_joins(conn):
    from data_loading.identifier_loader import load_identifiers

    result = load_identifiers(conn, case_ids=[1], commit=True)
    assert _identifiers(conn, 1) == [
        (1, "celex", "62012CJ0199", "62012CJ0199", "cases.celex_id", True),
        (1, "cjeu_case_number", "C-199/12", "C-199/12", "cjeu_document.case_number", True),
        (1, "cjeu_case_number", "C-200/12", "C-200/12", "cellar_joins", False),
        (1, "cjeu_case_number", "C-201/12", "C-201/12", "cellar_joins", False),
        (1, "ecli", "ECLI:EU:C:2013:720", "ECLI:EU:C:2013:720", "cases.ecli", True),
    ]
    cn = result["schemes"]["cjeu_case_number"]
    assert cn["inserted"] == 3
    assert cn["unresolved"] == 1
    assert result["examples"]["cjeu_case_number:unresolved"][0]["value"] == DOSSIER_UNKNOWN
    # the 'cites' row is not a join, nor a 'joins' row of another dataset
    assert "C-221/17" not in [row[3] for row in _identifiers(conn, 1)]
    assert "C-202/12" not in [row[3] for row in _identifiers(conn, 1)]


@needs_db
def test_echr_owner_appno_only(conn):
    from data_loading.identifier_loader import load_identifiers

    load_identifiers(conn, case_ids=[10], commit=True)
    appnos = [row for row in _identifiers(conn, 10) if row[1] == "echr_appno"]
    assert appnos == [(10, "echr_appno", "17341/03", "17341/03", "echr_document_appno", True)]


@needs_db
def test_rs_zaaknummer_variants_and_ljn(conn):
    from data_loading.identifier_loader import load_identifiers

    result = load_identifiers(conn, case_ids=[20, 21], commit=True)
    rows = [row for row in _identifiers(conn) if row[1] in ("nl_zaaknummer", "ljn")]
    assert rows == [
        (20, "ljn", "BW3076", "BW3076", "rs_document.replaces_identifier", False),
        (
            20,
            "nl_zaaknummer",
            "201012342/1/T1/V2",
            "201012342/1/T1/V2",
            "rs_document.zaaknummer",
            False,
        ),
        (
            20,
            "nl_zaaknummer",
            "201012342/1/T1/V2",
            "201012342/T1/V2",
            "rs_document.zaaknummer",
            False,
        ),
        (
            20,
            "nl_zaaknummer",
            "201109928/T1/V2",
            "201109928/T1/V2",
            "rs_document.zaaknummer",
            False,
        ),
        (21, "nl_zaaknummer", "201504577/1/A3", "201504577/1/A3", "rs_document.zaaknummer", False),
        (21, "nl_zaaknummer", "201504577/1/A3", "201504577/A3", "rs_document.zaaknummer", False),
        (21, "nl_zaaknummer", "201507057/1/A3", "201507057/1/A3", "rs_document.zaaknummer", False),
        (21, "nl_zaaknummer", "201507057/1/A3", "201507057/A3", "rs_document.zaaknummer", False),
    ]
    # case 21's replaces_identifier is an ECLI: rejected, not stored as an LJN
    assert result["schemes"]["ljn"] == {"candidates": 1, "inserted": 1, "rejected": 1}


@needs_db
def test_idempotent_and_range_mode(conn):
    from data_loading.identifier_loader import backfill_range, load_identifiers

    first = backfill_range(conn, 1, 30, batch_size=7)
    before = _identifiers(conn)
    second = load_identifiers(conn, id_range=(1, 30), commit=True)
    assert _identifiers(conn) == before
    assert all(c.get("inserted", 0) == 0 for c in second["schemes"].values())
    for scheme, counts in first["schemes"].items():
        assert second["schemes"][scheme]["already_present"] == counts["inserted"]
    # the malformed ECLI of case 22 is rejected and reported
    assert first["schemes"]["ecli"]["rejected"] == 1
    assert first["examples"]["ecli"][0]["value"] == "bogus-ecli"


@needs_db
def test_cli_prints_counts(conn, monkeypatch, capsys):
    from data_loading import identifier_loader

    dsn = conn.get_dsn_parameters()
    base, _, _ = DSN.rpartition("/")
    monkeypatch.setenv("CLE_IDENT_TEST_DSN", f"{base}/{dsn['dbname']}")
    assert (
        identifier_loader.main(
            ["--dsn-env", "CLE_IDENT_TEST_DSN", "--from-id", "1", "--to-id", "3"]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["from_id"] == 1 and out["to_id"] == 3
    assert out["schemes"]["ecli"]["inserted"] == 3
    assert out["schemes"]["cjeu_case_number"]["inserted"] == 5  # 3 own + 2 joined members


class _Client:
    """The two PostgresCLEClient members maintain_for_keys uses."""

    def __init__(self, conn):
        self.conn = conn

    def _get_conn(self):
        return self.conn

    def transaction(self):
        from contextlib import contextmanager

        @contextmanager
        def tx():
            try:
                yield
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

        return tx()

    def execute_arrays(self, sql, params):
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount


@needs_db
def test_weekly_maintenance_behind_flag(conn, monkeypatch):
    from data_loading import identifier_loader

    client = _Client(conn)
    monkeypatch.delenv(identifier_loader.FLAG, raising=False)
    assert identifier_loader.maintain_for_keys(client, "ecli", ["ECLI:NL:RVS:2020:423"]) is None
    assert _identifiers(conn) == []

    monkeypatch.setenv(identifier_loader.FLAG, "true")
    result = identifier_loader.maintain_for_keys(client, "ecli", ["ECLI:NL:RVS:2020:423"])
    assert result["schemes"]["ecli"]["inserted"] == 1
    assert {row[0] for row in _identifiers(conn)} == {21}

    # ECHR: the owner number from HUDOC's appno field lands in echr_document_appno
    assert identifier_loader.record_echr_owner_appnos(client, [("001-1", "17341/03;55555/05")]) == 1
    identifier_loader.maintain_for_keys(client, "id", [10])
    appnos = sorted(row[3] for row in _identifiers(conn, 10) if row[1] == "echr_appno")
    assert appnos == ["17341/03", "55555/05"]

    # stored normalised (as case_identifier reads them), unparsable pieces skipped
    assert (
        identifier_loader.record_echr_owner_appnos(
            client, [("001-1", "no. 017341/03; 066666/06 ;n/a")]
        )
        == 1
    )
    assert sorted(
        row[0]
        for row in execute(
            conn, "SELECT appno FROM cle_v2.echr_document_appno WHERE source = 'appno'"
        )
    ) == ["17341/03", "55555/05", "66666/06"]


# ---------------------------------------------------------------------------
# wiring: each loader calls the maintenance once per batch
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_client(monkeypatch, tmp_path):
    from data_loading.clients import postgres as postgres_module
    from data_loading.row_processors import postgres as row_processors_module

    from .fakes import FakeHook

    hook = FakeHook()
    monkeypatch.setattr(postgres_module, "PostgresHook", lambda postgres_conn_id=None: hook)
    monkeypatch.setattr(
        row_processors_module, "get_path_processed", lambda name: str(tmp_path / "failed.csv")
    )
    return postgres_module.PostgresCLEClient()


@pytest.fixture
def maintenance_calls(monkeypatch):
    from data_loading import identifier_loader

    calls = []
    monkeypatch.setattr(
        identifier_loader,
        "maintain_for_keys",
        lambda client, key, values: calls.append((key, sorted(values))),
    )
    monkeypatch.setattr(
        identifier_loader,
        "record_echr_owner_appnos",
        lambda client, pairs: calls.append(("echr_appno", sorted(pairs))),
    )
    return calls


def test_rs_batch_maintains_identifiers_once(fake_client, maintenance_calls):
    from data_loading.row_processors.postgres import PostgresRSProcessor
    from definitions.terminology.attribute_names import ECLI

    rows = [{ECLI: "ECLI:NL:HR:2024:10"}, {ECLI: "ECLI:NL:HR:2024:11"}]
    assert PostgresRSProcessor("unused", fake_client).upload_rows(rows) == 2
    assert maintenance_calls == [("ecli", ["ECLI:NL:HR:2024:10", "ECLI:NL:HR:2024:11"])]


def test_echr_batch_records_owner_appnos_then_maintains(fake_client, maintenance_calls):
    from data_loading.row_processors.postgres import PostgresItemIdProcessor
    from definitions.terminology.attribute_names import ECHR_APPLICANTS, ECHR_DOCUMENT_ID

    rows = [{ECHR_DOCUMENT_ID: "001-1", ECHR_APPLICANTS: "17341/03"}]
    assert PostgresItemIdProcessor("unused", fake_client).upload_rows(rows) == 1
    assert [call[0] for call in maintenance_calls] == ["echr_appno", "id"]
    assert maintenance_calls[0][1] == [("001-1", "17341/03")]
    assert len(maintenance_calls[1][1]) == 1


def test_cjeu_batch_maintains_only_loaded_cases(fake_client, maintenance_calls, monkeypatch):
    from data_loading import cjeu_loader

    def fake_write(_client, mappings):
        if len(mappings) > 1 or mappings[0].ecli == "ECLI:EU:C:2026:2":
            raise RuntimeError("boom")
        return {}

    monkeypatch.setattr(cjeu_loader, "write", fake_write)
    rows = [
        {"ECLI": "ECLI:EU:C:2026:1", "celex": "62025CJ0001"},
        {"ECLI": "ECLI:EU:C:2026:2", "celex": "62025CJ0002"},
    ]
    monkeypatch.setattr(cjeu_loader, "validate", lambda client, mappings: (mappings, []))
    assert cjeu_loader.load_rows(fake_client, rows, lambda key, error: None) == 1
    assert maintenance_calls == [("ecli", ["ECLI:EU:C:2026:1"])]
