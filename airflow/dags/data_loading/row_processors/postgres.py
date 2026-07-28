from definitions.storage_handler import CSV_LOAD_FAILED, get_path_processed
from definitions.terminology.attribute_names import (
    CELLAR_CELEX,
    CELLAR_CITATIONS_EXTRA_INFO,
    CELLAR_CREATION_OF_WORK,
    CELLAR_DATE_OF_DOCUMENT,
    CELLAR_JOURNAL_ARTICLES,
    CELLAR_SECTOR,
    CELLAR_TYPE_PROCEDURE,
    ECHR_APPLICABILITY,
    ECHR_BRANCH,
    ECHR_CONCLUSION,
    ECHR_DOCUMENT_ID,
    ECHR_DOCUMENT_TYPE,
    ECHR_IMPORTANCE,
    ECHR_JUDGMENT_DATE,
    ECHR_LANGUAGE,
    ECHR_NON_VIOLATIONS,
    ECHR_PARTICIPANTS,
    ECHR_PUBLISHED_BY,
    ECHR_REPRESENTATION,
    ECHR_RESPONDENT,
    ECHR_SEPARATE_OPINION,
    ECHR_TITLE,
    ECHR_VIOLATIONS,
    ECLI,
    JURISDICTION_COUNTRY,
    RS_CREATOR,
    RS_DATE,
    RS_FULL_TEXT,
    RS_IDENTIFIER2,
    RS_INHOUDSINDICATIE,
    RS_ISSUED,
    RS_LANGUAGE,
    RS_PROCEDURE,
    RS_REFERENCES,
    RS_RELATION,
    RS_SPATIAL,
    RS_SUBJECT,
    RS_SUMMARY,
    RS_TITLE,
    RS_TYPE,
    RS_ZAAKNUMMER,
    SOURCE,
)

SET_SEP = "; "  # used to separate set items in string (matches row_processors/dynamodb.py)


def _split_set(value):
    if not value:
        return None
    return [v for v in value.split(SET_SEP) if v]


class PostgresRSProcessor:
    """Rechtspraak rows -> cle_v2.cases + cle_v2.rs_document + cle_v2.case_text."""

    def __init__(self, path, client):
        self.path = path
        self.client = client

    def upload_row(self, row: dict) -> int:
        if ECLI not in row or not row[ECLI]:
            print("NO ECLI FOUND")
            return 0

        try:
            with self.client.transaction():
                case_id = self.client.upsert_case(
                    ecli=row[ECLI],
                    title=row.get(RS_TITLE),
                    date_decision=row.get(RS_DATE) or None,
                    source=row.get(SOURCE, "Rechtspraak"),
                )

                self.client.upsert(
                    table="rs_document",
                    conflict_cols=["case_id"],
                    values={
                        "case_id": case_id,
                        "date_decision": row.get(RS_DATE) or None,
                        "document_type": row.get(RS_TYPE),
                        "instance": row.get(RS_CREATOR),
                        "domains": _split_set(row.get(RS_SUBJECT)),
                        "source": row.get(SOURCE, "Rechtspraak"),
                        "jurisdiction_country": row.get(JURISDICTION_COUNTRY, "NL"),
                        "procedure_type": row.get(RS_PROCEDURE),
                        "url_publication": row.get(RS_IDENTIFIER2),
                        "legal_provisions": _split_set(row.get(RS_REFERENCES)),
                        "predecessor_successor_cases": row.get(RS_RELATION),
                        "date_published": row.get(RS_ISSUED) or None,
                        "title": row.get(RS_TITLE),
                        "language": row.get(RS_LANGUAGE),
                        "zittingsplaats": row.get(RS_SPATIAL),
                        "zaaknummer": row.get(RS_ZAAKNUMMER),
                    },
                )

                self.client.upsert_case_text(
                    case_id=case_id,
                    language=row.get(RS_LANGUAGE, "nl"),
                    source="RECHTSPRAAK",
                    fulltext=row.get(RS_FULL_TEXT),
                    summary=row.get(RS_INHOUDSINDICATIE) or row.get(RS_SUMMARY),
                    summary_source="rechtspraak",
                )
            return 1
        except Exception as e:
            print(e, row.get(ECLI), "; while upserting RS row into Postgres")
            with open(get_path_processed(CSV_LOAD_FAILED), "a") as f:
                f.write(str(row.get(ECLI)) + "\n")
                f.write(str(e) + "\n")
            return 0


class PostgresCelexProcessor:
    """Cellar/CJEU rows -> cle_v2.cases + cle_v2.cjeu_document. Full text loaded separately (case_text_loader.py)."""

    def __init__(self, path, client):
        self.path = path
        self.client = client

    def upload_row(self, row: dict) -> int:
        if CELLAR_CELEX not in row or not row[CELLAR_CELEX]:
            print("NO CELEX FOUND")
            return 0

        try:
            with self.client.transaction():
                case_id = self.client.upsert_case(
                    celex_id=row[CELLAR_CELEX],
                    # no dedicated title field extracted for Cellar cases today
                    date_decision=row.get(CELLAR_DATE_OF_DOCUMENT) or None,
                    source="EURLEX",
                )

                self.client.upsert(
                    table="cjeu_document",
                    conflict_cols=["case_id"],
                    values={
                        "case_id": case_id,
                        "celex_id": row.get(CELLAR_CELEX),
                        "sector": row.get(CELLAR_SECTOR),
                        "proc_type": row.get(CELLAR_TYPE_PROCEDURE),
                        # best available proxy for date_lodged; CELLAR extraction doesn't
                        # capture a distinct "lodged" date today
                        "date_lodged": row.get(CELLAR_CREATION_OF_WORK) or None,
                        "journal_refs": row.get(CELLAR_JOURNAL_ARTICLES),
                        "citations_extra_info": row.get(CELLAR_CITATIONS_EXTRA_INFO),
                    },
                )
            return 1
        except Exception as e:
            print(e, row.get(CELLAR_CELEX), "; while upserting Cellar row into Postgres")
            with open(get_path_processed(CSV_LOAD_FAILED), "a") as f:
                f.write(str(row.get(CELLAR_CELEX)) + "\n")
                f.write(str(e) + "\n")
            return 0


class PostgresItemIdProcessor:
    """ECHR rows -> cle_v2.cases + cle_v2.echr_document. Full text loaded separately (case_text_loader.py)."""

    def __init__(self, path, client):
        self.path = path
        self.client = client

    def upload_row(self, row: dict) -> int:
        if ECHR_DOCUMENT_ID not in row or not row[ECHR_DOCUMENT_ID]:
            print("NO DOCUMENT ID FOUND")
            return 0

        try:
            with self.client.transaction():
                case_id = self.client.upsert_case(
                    item_id=row[ECHR_DOCUMENT_ID],
                    title=row.get(ECHR_TITLE),
                    date_decision=row.get(ECHR_JUDGMENT_DATE) or None,
                    source="HUDOC",
                )

                self.client.upsert(
                    table="echr_document",
                    conflict_cols=["item_id"],
                    values={
                        "item_id": row[ECHR_DOCUMENT_ID],
                        "case_id": case_id,
                        "language": row.get(ECHR_LANGUAGE, "en"),
                        "extractedappno": row.get(ECHR_PARTICIPANTS),
                        "docname": row.get(ECHR_TITLE),
                        "doctype": row.get(ECHR_DOCUMENT_TYPE),
                        "doctype_branch": row.get(ECHR_BRANCH),
                        "judgement_date": row.get(ECHR_JUDGMENT_DATE) or None,
                        "conclusion": row.get(ECHR_CONCLUSION),
                        "violation": row.get(ECHR_VIOLATIONS),
                        "nonviolation": row.get(ECHR_NON_VIOLATIONS),
                        "respondent": row.get(ECHR_RESPONDENT),
                        "represented_by": row.get(ECHR_REPRESENTATION),
                        "published_by": row.get(ECHR_PUBLISHED_BY),
                        "applicability": row.get(ECHR_APPLICABILITY),
                        "separate_opinion": row.get(ECHR_SEPARATE_OPINION),
                        "importance": row.get(ECHR_IMPORTANCE) or None,
                    },
                )
            return 1
        except Exception as e:
            print(e, row.get(ECHR_DOCUMENT_ID), "; while upserting ECHR row into Postgres")
            with open(get_path_processed(CSV_LOAD_FAILED), "a") as f:
                f.write(str(row.get(ECHR_DOCUMENT_ID)) + "\n")
                f.write(str(e) + "\n")
            return 0
