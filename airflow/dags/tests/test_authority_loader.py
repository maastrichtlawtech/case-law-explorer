"""
Phase 4 authorities against a scratch database (db/schema.sql), as in
test_link_loader.py: the extractors read the database, the loader writes
authority_document and case_authority_reference insert-only. Runs only when
CLE_TEST_PG_DSN is set.

Texts here are ILLUSTRATIVE (see test_authority_extractors.py), except the
national_judgement lines and the sector 8 CELEX, which are REAL (research
files).
"""

import json
from datetime import date

import linking_tasks
from data_extraction.linking import authority_text, cellar_authority, rs_publication
from data_extraction.linking.artifact import CaseKey
from data_extraction.linking.authority_artifact import (
    AuthorityDoc,
    AuthorityMention,
    AuthorityRecord,
    read_jsonl,
)
from data_loading import authority_loader
from tests.linking_db import DSN, add_case, execute, needs_db, scratch_db  # noqa: F401

pytestmark = needs_db

RS_TEXT = (
    "Uit de wetsgeschiedenis (Kamerstukken II 2015/16, 34 356, nr. 3, p. 12) volgt dat "
    "paragraaf C2/3.2 van de Vc 2000 van toepassing is (Stcrt. 2019, 12345)."
)
HUDOC_TEXT = (
    "See the Venice Commission opinion CDL-AD(2016)007 and the Human Rights Committee, "
    "communication No. 2149/2012; compare ECLI:BE:GHCC:2021:ARR.168."
)
NOTICE = (
    "<national_judgement>\n"
    "        <p>*A9* Gerechtshof te &#39;s-Gravenhage, arrest van 30/06/1961</p>\n"
    "        <p>- Nederlandse jurisprudentie ; Uitspraken in burgerlijke en strafzaken "
    "1961 nº 375 (*)</p>\n"
    "        <p>*P1* Grondwettelijk Hof, arrest van 25/11/2021 (ECLI:BE:GHCC:2021:ARR.168)</p>\n"
    "      </national_judgement>"
)


def _rs_case(conn, ecli, text=RS_TEXT, summary=None):
    case_id = add_case(conn, ecli, None, date(2020, 1, 1), sources=("RS",))
    execute(conn, "INSERT INTO cle_v2.rs_document (case_id) VALUES (%s)", (case_id,))
    execute(
        conn,
        """INSERT INTO cle_v2.case_text (case_id, language, fulltext, summary, source)
           VALUES (%s, 'nl', %s, %s, 'RECHTSPRAAK')""",
        (case_id, text, summary),
    )
    return case_id


def _echr_case(conn, item_id="001-1"):
    case_id = execute(
        conn,
        """INSERT INTO cle_v2.cases (item_id, date_decision, sources)
           VALUES (%s, '2020-01-01', ARRAY['ECHR']) RETURNING id""",
        (item_id,),
    )[0][0]
    execute(
        conn,
        """INSERT INTO cle_v2.case_text (case_id, language, fulltext, source)
           VALUES (%s, 'en', %s, 'HUDOC')""",
        (case_id, HUDOC_TEXT),
    )
    return case_id


def _cjeu_case(conn, ecli="ECLI:EU:C:1962:11", celex="61961CJ0013"):
    case_id = add_case(conn, ecli, celex, date(1962, 4, 6))
    execute(
        conn,
        """INSERT INTO cle_v2.cjeu_document (case_id, celex_id, ecli, national_judgement_xml)
           VALUES (%s, %s, %s, %s)""",
        (case_id, celex, ecli, NOTICE),
    )
    for target, relation in (
        ("52012PC0011", "cites"),
        ("52012PC0011", "cited_by"),
        ("82020DE0512(51)", "cited_by"),
        ("32013R0604", "cites"),
    ):
        execute(
            conn,
            """INSERT INTO cle_v2.case_citation
                   (source_case_id, target_celex_raw, relation_type, source_dataset)
               VALUES (%s, %s, %s, 'cellar_sparql')""",
            (case_id, target, relation),
        )
    return case_id


def _counts(conn):
    return dict(
        execute(
            conn,
            "SELECT source_dataset, count(*) FROM cle_v2.case_authority_reference GROUP BY 1",
        )
    )


def test_rs_text_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    case_id = _rs_case(scratch_db, "ECLI:NL:RBDHA:2020:1")
    out = tmp_path / "rs.jsonl"
    written, stats = authority_text.extract(scratch_db, "rs", id_range=(None, None), out_path=out)
    assert written == 3
    records = list(read_jsonl(out))
    assert sorted(r.authority.identifier for r in records) == [
        "kst-34356-3",
        "stcrt-2019-12345",
        "vc2000-C",
    ]
    result = authority_loader.load_artifact(scratch_db, out)
    assert result == {"rs_text_authority": {"inserted": 3, "documents_inserted": 3}}
    rows = execute(
        scratch_db,
        """SELECT r.raw_reference, r.pinpoint, r.char_start, r.char_end, r.case_text_id IS NOT NULL,
                  d.kind, d.identifier_scheme, d.identifier, d.url
             FROM cle_v2.case_authority_reference r
             JOIN cle_v2.authority_document d ON d.id = r.authority_document_id
            WHERE r.case_id = %s ORDER BY r.char_start""",
        (case_id,),
    )
    raw, pinpoint, start, end, has_text, kind, scheme, identifier, url = rows[0]
    assert RS_TEXT[start:end] == raw == "Kamerstukken II 2015/16, 34 356, nr. 3, p. 12"
    assert (pinpoint, has_text, kind, scheme, identifier) == (
        "p. 12",
        True,
        "nl_parliamentary_paper",
        "officielebekendmakingen",
        "kst-34356-3",
    )
    assert url == "https://zoek.officielebekendmakingen.nl/kst-34356-3.html"
    # insert-only: loading again changes nothing
    again = authority_loader.load_artifact(scratch_db, out)
    assert again == {"rs_text_authority": {"existing": 3}}
    assert _counts(scratch_db) == {"rs_text_authority": 3}


def test_documents_are_shared_across_cases_and_datasets(scratch_db, tmp_path):  # noqa: F811
    _rs_case(scratch_db, "ECLI:NL:RBDHA:2020:1")
    _rs_case(scratch_db, "ECLI:NL:RBDHA:2020:2", text="Zie Kamerstukken II 2015/16, 34 356, nr. 3.")
    _echr_case(scratch_db)
    rs_out, echr_out = tmp_path / "rs.jsonl", tmp_path / "echr.jsonl"
    authority_text.extract(scratch_db, "rs", out_path=rs_out)
    authority_text.extract(scratch_db, "echr", out_path=echr_out)
    authority_loader.load_artifact(scratch_db, rs_out)
    result = authority_loader.load_artifact(scratch_db, echr_out)
    assert result["echr_text_authority"]["inserted"] == 3
    shared = execute(
        scratch_db,
        """SELECT d.identifier, count(DISTINCT r.case_id)
             FROM cle_v2.authority_document d
             JOIN cle_v2.case_authority_reference r ON r.authority_document_id = d.id
            GROUP BY d.identifier HAVING count(*) > 1""",
    )
    assert shared == [("kst-34356-3", 2)]
    assert execute(
        scratch_db,
        "SELECT count(*) FROM cle_v2.authority_document WHERE identifier = 'kst-34356-3'",
    ) == [(1,)]


def test_cellar_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    case_id = _cjeu_case(scratch_db)
    out = tmp_path / "cellar.jsonl"
    written, stats = cellar_authority.extract(scratch_db, out_path=out)
    records = sorted(read_jsonl(out), key=lambda r: r.raw_reference)
    assert [(r.authority.kind, r.authority.identifier, r.match_method) for r in records] == [
        (
            "literature",
            "nederlandse jurisprudentie ; uitspraken in burgerlijke en strafzaken|1961|no. 375",
            "national_judgement_literature",
        ),
        ("eu_preparatory_act", "52012PC0011", "cellar_cited_by,cellar_cites"),
        ("national_court_decision", "82020DE0512(51)", "cellar_cited_by"),
        ("national_court_decision", "ECLI:BE:GHCC:2021:ARR.168", "national_judgement_ecli"),
    ]
    assert stats["celex_sector3_not_authority"] == 1
    assert authority_loader.load_artifact(scratch_db, out) == {
        "cellar_authority": {"inserted": 4, "documents_inserted": 4}
    }
    (dated,) = execute(
        scratch_db,
        "SELECT issuer, date FROM cle_v2.authority_document WHERE identifier = '82020DE0512(51)'",
    )
    assert dated == ("DE", date(2020, 5, 12))
    assert execute(
        scratch_db,
        "SELECT count(*) FROM cle_v2.case_authority_reference WHERE case_id = %s",
        (case_id,),
    ) == [(4,)]


def test_cellar_ignores_resolved_rows_and_other_datasets(scratch_db, tmp_path):  # noqa: F811
    case_id = _cjeu_case(scratch_db)
    other = add_case(scratch_db, "ECLI:EU:C:2020:1", "52099PC0001")
    execute(
        scratch_db,
        """INSERT INTO cle_v2.case_citation
               (source_case_id, target_case_id, target_celex_raw, relation_type, source_dataset)
           VALUES (%s, %s, '52099PC0001', 'cites', 'cellar_sparql'),
                  (%s, NULL, '52098PC0001', 'cites', 'rs_text_ecli')""",
        (case_id, other, case_id),
    )
    out = tmp_path / "cellar.jsonl"
    cellar_authority.extract(scratch_db, case_ids=[case_id], out_path=out)
    identifiers = {r.authority.identifier for r in read_jsonl(out)}
    assert "52099PC0001" not in identifiers and "52098PC0001" not in identifiers


def test_rs_publication_extract_and_load(scratch_db, tmp_path):  # noqa: F811
    hr = _rs_case(scratch_db, "ECLI:NL:HR:2019:1")
    phr = _rs_case(scratch_db, "ECLI:NL:PHR:2019:1")
    execute(
        scratch_db,
        """INSERT INTO cle_v2.rs_document_publication
               (case_id, raw, journal_abbr, year, locator, annotator)
           VALUES (%s, 'NJ 2019/123 m.nt. J. Spier', 'NJ', 2019, '123', 'J. Spier'),
                  (%s, 'Rechtspraak.nl', NULL, NULL, NULL, NULL),
                  (%s, 'NJ 2019/123 met annotatie van mr. J. Spier', NULL, NULL, NULL, NULL)""",
        (hr, hr, phr),
    )
    execute(
        scratch_db,
        "UPDATE cle_v2.rs_document SET vindplaatsen = %s WHERE case_id = %s",
        (["NJ 2019/123 m.nt. J. Spier", "RvdW 2019/5"], hr),
    )
    out = tmp_path / "pub.jsonl"
    written, stats = rs_publication.extract(scratch_db, out_path=out)
    assert written == 3
    assert stats["rs_document_publication_skipped"] == 1
    result = authority_loader.load_artifact(scratch_db, out)
    assert result == {"rs_publication": {"inserted": 3, "documents_inserted": 2}}
    # the HR judgment and the Parket's conclusion share one annotation
    assert (
        execute(
            scratch_db,
            """SELECT d.kind, d.identifier, count(*)
             FROM cle_v2.authority_document d
             JOIN cle_v2.case_authority_reference r ON r.authority_document_id = d.id
            GROUP BY d.kind, d.identifier ORDER BY d.identifier""",
        )
        == [("annotation", "NJ 2019/123 m.nt. J. Spier", 2), ("literature", "RVDW 2019/5", 1)]
    )


def test_loader_counts_missing_sources_and_keeps_first_attributes(scratch_db):  # noqa: F811
    _rs_case(scratch_db, "ECLI:NL:HR:2019:1")

    def record(ecli, title, raw):
        return AuthorityRecord(
            source=CaseKey(ecli=ecli),
            authority=AuthorityDoc("literature", "nl_journal_locator", "NJ 2019/123", title=title),
            raw_reference=raw,
            source_dataset="rs_publication",
            extractor_version="rs_publication/1.0.0",
            mention=AuthorityMention(text_field="metadata"),
        )

    result = authority_loader.load_records(
        scratch_db,
        [
            record("ECLI:NL:HR:2019:1", "first", "NJ 2019/123"),
            record("ECLI:NL:HR:2019:1", "second", "NJ 2019, 123"),
            record("ECLI:NL:HR:2099:9", "third", "NJ 2019/123"),
        ],
        batch_size=2,
    )
    assert result == {
        "rs_publication": {"inserted": 2, "documents_inserted": 1, "source_missing": 1}
    }
    assert execute(scratch_db, "SELECT title FROM cle_v2.authority_document") == [("first",)]


def test_dataset_removal_is_one_delete(scratch_db, tmp_path):  # noqa: F811
    _rs_case(scratch_db, "ECLI:NL:RBDHA:2020:1")
    _cjeu_case(scratch_db)
    for corpus_out, extract in (
        (tmp_path / "rs.jsonl", lambda p: authority_text.extract(scratch_db, "rs", out_path=p)),
        (tmp_path / "c.jsonl", lambda p: cellar_authority.extract(scratch_db, out_path=p)),
    ):
        extract(corpus_out)
        authority_loader.load_artifact(scratch_db, corpus_out)
    execute(
        scratch_db,
        "DELETE FROM cle_v2.case_authority_reference WHERE source_dataset = 'rs_text_authority'",
    )
    assert _counts(scratch_db) == {"cellar_authority": 4}


# ---------------------------------------------------------------------------
# weekly month and backfill CLI
# ---------------------------------------------------------------------------


def _processed(tmp_path, month, name, column, keys):
    folder = tmp_path / "processed" / month
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("\n".join([f"{column},title"] + [f"{k},x" for k in keys]) + "\n")
    return folder


def test_rs_month_writes_both_files_and_loads(scratch_db, tmp_path):  # noqa: F811
    _rs_case(scratch_db, "ECLI:NL:RBDHA:2020:1")
    _rs_case(scratch_db, "ECLI:NL:RBDHA:2020:2", text="Kamerstukken II 2015/16, 34 356, nr. 4")
    folder = _processed(
        tmp_path, "2020-01-01", "RS_cases_clean.csv", "ECLI", ["ECLI:NL:RBDHA:2020:1"]
    )
    source = linking_tasks.SOURCES["rechtspraak"]
    counts = linking_tasks.run_month_authorities(scratch_db, source, str(tmp_path), "2020-01-01")
    out = folder / "authorities"
    assert sorted(p.name for p in out.iterdir()) == [
        "_counts.RS.json",
        "rs_publication.jsonl",
        "rs_text_authority.jsonl",
    ]
    assert counts["datasets"]["rs_text_authority"]["records"] == 3
    assert counts["datasets"]["rs_publication"]["records"] == 0
    assert (out / "rs_publication.jsonl").read_text() == ""
    assert counts["datasets"]["rs_text_authority"]["load"]["inserted"] == 3
    # only the month's case was scanned
    assert _counts(scratch_db) == {"rs_text_authority": 3}
    assert linking_tasks.authority_artifact_paths(source, "2020-01-01") == [
        "processed/2020-01-01/authorities/rs_text_authority.jsonl",
        "processed/2020-01-01/authorities/rs_publication.jsonl",
    ]
    assert json.loads((out / "_counts.RS.json").read_text())["case_ids"] == 1


def test_month_extractor_flag_off_writes_an_empty_file(  # noqa: F811
    scratch_db, tmp_path, monkeypatch  # noqa: F811
):
    _cjeu_case(scratch_db)
    folder = _processed(
        tmp_path, "1962-04-01", "cellar_csv_data_clean.csv", "celex", ["61961CJ0013"]
    )
    monkeypatch.setenv("AUTHORITY_CELLAR", "off")
    counts = linking_tasks.run_month_authorities(
        scratch_db, linking_tasks.SOURCES["cellar"], str(tmp_path), "1962-04-01"
    )
    assert counts["extractors"]["cellar_authority"]["status"] == "skipped"
    assert (folder / "authorities" / "cellar_authority.jsonl").read_text() == ""
    assert _counts(scratch_db) == {}


def test_backfill_authorities_cli(scratch_db, tmp_path, monkeypatch):  # noqa: F811
    first = _echr_case(scratch_db, "001-1")
    _echr_case(scratch_db, "001-2")
    monkeypatch.setenv("AUTH_TEST_DSN", DSN.rpartition("/")[0] + "/" + scratch_db.info.dbname)
    out = tmp_path / "out"
    argv = ["backfill-authorities", "--dsn-env", "AUTH_TEST_DSN", "--source", "echr"]
    argv += ["--from-id", str(first), "--to-id", str(first), "--out", str(out)]
    assert linking_tasks.main(argv) == 0
    assert len((out / "echr_text_authority.jsonl").read_text().splitlines()) == 3
    assert _counts(scratch_db) == {}  # read-only without --load
    assert linking_tasks.main(argv + ["--load"]) == 0
    assert _counts(scratch_db) == {"echr_text_authority": 3}
