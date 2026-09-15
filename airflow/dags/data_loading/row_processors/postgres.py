import logging
from datetime import date

from data_loading.language_codes import normalize_language_code
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
    ECHR_APPLICANTS,
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
    ECHR_REFERENCE_DATE,
    ECHR_REPRESENTATION,
    ECHR_RESPONDENT,
    ECHR_SEPARATE_OPINION,
    ECHR_TITLE,
    ECHR_VIOLATIONS,
    ECLI,
    JURISDICTION_COUNTRY,
    RS_BWB_ID,
    RS_CITING,
    RS_CREATOR,
    RS_DATE,
    RS_FULL_TEXT,
    RS_IDENTIFIER2,
    RS_INHOUDSINDICATIE,
    RS_ISSUED,
    RS_LANGUAGE,
    RS_LEGISLATIONS,
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

SET_SEP = "; "  # used to separate set items in string


def _split_set(value):
    if not value:
        return None
    return [v for v in value.split(SET_SEP) if v]


def _earliest_iso_date(value):
    """Reduce a semicolon-separated timestamp list to one PostgreSQL date."""
    dates = []
    for item in str(value or "").split(";"):
        try:
            dates.append(date.fromisoformat(item.strip()[:10]))
        except ValueError:
            continue
    return min(dates) if dates else None


class _BaseRowProcessor:
    """
    Shared upsert logic for one processed CSV. Subclasses declare their
    natural key and cle_v2 detail table, plus the dict shapes for the
    cases / detail / case_text rows; this class provides both the
    row-at-a-time path (upload_row) and the batched path (upload_rows,
    one multi-row statement per table per batch).
    """

    key_field = None  # processed-CSV column holding the natural key
    conflict_col = None  # matching cle_v2.cases conflict column
    detail_table = None
    detail_conflict_cols = ["case_id"]

    def __init__(self, path, client):
        self.path = path
        self.client = client

    def _key(self, row):
        return row.get(self.key_field)

    def _case_row(self, row):
        raise NotImplementedError

    def _detail_row(self, row, case_id):
        raise NotImplementedError

    def _text_row(self, row, case_id):
        return None

    def _citation_rows(self, row, case_id):
        """Optional: kwargs dicts for client.upsert_citation (source_case_id
        filled in by the caller). Default: none."""
        return []

    def _law_reference_rows(self, row, case_id):
        """Optional: kwargs dicts for client.upsert_law_reference (case_id
        filled in by the caller). Default: none."""
        return []

    def _log_failure(self, key, error):
        logging.error(f"{error} {key} ; while upserting {self.detail_table} row into Postgres")
        with open(get_path_processed(CSV_LOAD_FAILED), "a") as f:
            f.write(f"{key}\n{error}\n")

    def upload_row(self, row: dict) -> int:
        key = self._key(row)
        if not key:
            logging.warning(f"NO {self.key_field} FOUND, skipping row")
            return 0
        try:
            with self.client.transaction():
                case_id = self.client.upsert_case(**self._case_row(row))
                self.client.upsert(
                    table=self.detail_table,
                    conflict_cols=self.detail_conflict_cols,
                    values=self._detail_row(row, case_id),
                )
                text_row = self._text_row(row, case_id)
                if text_row is not None:
                    self.client.upsert_case_text(**text_row)
                for citation in self._citation_rows(row, case_id):
                    self.client.upsert_citation(source_case_id=case_id, **citation)
                for law_reference in self._law_reference_rows(row, case_id):
                    self.client.upsert_law_reference(case_id=case_id, **law_reference)
            return 1
        except Exception as e:
            self._log_failure(key, e)
            return 0

    def upload_rows(self, rows: list) -> int:
        """
        Batched variant: one bulk statement each for cases, the detail
        table, and case_text. Rows sharing a natural key are collapsed to
        the last occurrence (a single multi-row INSERT cannot touch the
        same row twice). Falls back to row-by-row on failure so one bad
        row doesn't discard the batch.
        """
        by_key = {}
        for row in rows:
            key = self._key(row)
            if not key:
                logging.warning(f"NO {self.key_field} FOUND, skipping row")
                continue
            by_key[key] = row
        valid = list(by_key.values())
        if not valid:
            return 0

        try:
            with self.client.transaction():
                case_ids = self.client.bulk_upsert_cases(
                    self.conflict_col, [self._case_row(row) for row in valid]
                )
                self.client.bulk_upsert(
                    self.detail_table,
                    self.detail_conflict_cols,
                    [self._detail_row(row, case_ids[self._key(row)]) for row in valid],
                )
                text_rows = [
                    text_row
                    for row in valid
                    if (text_row := self._text_row(row, case_ids[self._key(row)])) is not None
                ]
                if text_rows:
                    self.client.bulk_upsert_case_text(text_rows)
                # Citations/law references are per-row, one upsert_* call each
                # (there's no bulk variant -- the count per case varies from
                # zero to several, unlike the one-row-per-case tables above).
                for row in valid:
                    case_id = case_ids[self._key(row)]
                    for citation in self._citation_rows(row, case_id):
                        self.client.upsert_citation(source_case_id=case_id, **citation)
                    for law_reference in self._law_reference_rows(row, case_id):
                        self.client.upsert_law_reference(case_id=case_id, **law_reference)
            return len(valid)
        except Exception:
            logging.exception(
                f"Bulk upsert of {len(valid)} rows into {self.detail_table} failed; "
                "retrying row by row"
            )
            return sum(self.upload_row(row) for row in valid)


class PostgresRSProcessor(_BaseRowProcessor):
    """Rechtspraak rows -> cle_v2.cases + cle_v2.rs_document + cle_v2.case_text.

    Defaults here are written as `or`, not as a second argument to get(). The
    transformer emits every mapped column as a header, so a column the source
    did not fill is present and empty rather than absent, and a get() default
    never fires for it. That put an empty string in cases.sources on every row
    and, for language, broke the foreign key onto language.iso_code outright.
    """

    key_field = ECLI
    conflict_col = "ecli"
    detail_table = "rs_document"

    def _case_row(self, row):
        return {
            "ecli": row[ECLI],
            "title": row.get(RS_TITLE),
            "date_decision": row.get(RS_DATE) or None,
            "source": row.get(SOURCE) or "Rechtspraak",
        }

    def _detail_row(self, row, case_id):
        return {
            "case_id": case_id,
            "date_decision": row.get(RS_DATE) or None,
            "document_type": row.get(RS_TYPE),
            "instance": row.get(RS_CREATOR),
            "domains": _split_set(row.get(RS_SUBJECT)),
            "source": row.get(SOURCE) or "Rechtspraak",
            "jurisdiction_country": row.get(JURISDICTION_COUNTRY) or "NL",
            "procedure_type": row.get(RS_PROCEDURE),
            "url_publication": row.get(RS_IDENTIFIER2),
            "legal_provisions": _split_set(row.get(RS_REFERENCES)),
            "predecessor_successor_cases": row.get(RS_RELATION),
            "date_published": row.get(RS_ISSUED) or None,
            "title": row.get(RS_TITLE),
            "language": row.get(RS_LANGUAGE),
            "zittingsplaats": row.get(RS_SPATIAL),
            "zaaknummer": row.get(RS_ZAAKNUMMER),
        }

    def _text_row(self, row, case_id):
        fulltext = row.get(RS_FULL_TEXT)
        has_fulltext = bool(str(fulltext or "").strip())
        return {
            "case_id": case_id,
            # "or", not a get() default: the transformer writes every mapped
            # column as a header, so language is present-and-empty rather than
            # absent and the default never fired. Lowercased because
            # case_text.language is a foreign key onto language.iso_code, and
            # the RS value arrives as the jurisdiction "NL".
            "language": (row.get(RS_LANGUAGE) or "nl").lower(),
            "source": "RECHTSPRAAK",
            "fulltext": fulltext if has_fulltext else None,
            "summary": row.get(RS_INHOUDSINDICATIE) or row.get(RS_SUMMARY),
            "summary_source": "rechtspraak",
            # Rechtspraak's feed and content endpoint do not distinguish a
            # genuinely unpublished body from a fetch that exhausted retries.
            # Persist that ambiguity instead of treating an empty string as a
            # successful full-text load.
            "missing_reasons": (
                None if has_fulltext else "RECHTSPRAAK_BODY_UNAVAILABLE_OR_FETCH_FAILED"
            ),
            "is_stub": not has_fulltext,
        }

    def _citation_rows(self, row, case_id):
        """citations_outgoing -> case_citation, one row per cited ECLI.
        Sourced from lido.db (built monthly by lido_sqlite_build), or the
        live per-ECLI API for cases missing from it -- outgoing-only, same
        convention citation_update.py already uses, since citations_incoming
        is just the mirror of another case's own outgoing edge."""
        rows = []
        for target_ecli in _split_set(row.get(RS_CITING)) or []:
            target_case_id = self.client.resolve_case_id(ecli=target_ecli)
            rows.append(
                {
                    "target_case_id": target_case_id,
                    "target_ecli_raw": None if target_case_id else target_ecli,
                    "relation_type": "cites",
                    "source_dataset": "rs_lido_sqlite",
                }
            )
        return rows

    def _law_reference_rows(self, row, case_id):
        """legislations_cited -> case_law_reference, one row per citation.
        Independent of, and additional to, the pg_lido-sourced rows
        lido_reference_loader.py already writes (distinct source_dataset
        keeps the two from colliding on the unique index).

        bwb_id is a single value per case today, not one per legislation
        citation, so every row from the same case currently gets the same
        raw_resource -- a known limitation until lido.db's legislations_cited/
        bwb_id are populated in a way that lines up per-entry."""
        bwb_id = row.get(RS_BWB_ID) or None
        return [
            {
                "raw_reference": legislation,
                "raw_resource": bwb_id,
                "source_dataset": "rs_lido_sqlite",
            }
            for legislation in (_split_set(row.get(RS_LEGISLATIONS)) or [])
        ]


class PostgresCelexProcessor(_BaseRowProcessor):
    """Cellar/CJEU rows -> cle_v2.cases + cle_v2.cjeu_document. Full text loaded separately (case_text_loader.py)."""

    key_field = CELLAR_CELEX
    conflict_col = "celex_id"
    detail_table = "cjeu_document"

    def upload_rows(self, rows: list) -> int:
        # CJEU and Rechtspraak overlap for some Dutch sector-8 decisions.
        # Row-wise identity-aware upserts can merge those on ECLI; a bulk
        # ON CONFLICT (celex_id) cannot also arbitrate an ECLI conflict.
        return sum(self.upload_row(row) for row in rows)

    def _case_row(self, row):
        return {
            "celex_id": row[CELLAR_CELEX],
            "ecli": row.get(ECLI) or None,
            # no dedicated title field extracted for Cellar cases today
            "date_decision": row.get(CELLAR_DATE_OF_DOCUMENT) or None,
            "source": "EURLEX",
        }

    def _detail_row(self, row, case_id):
        return {
            "case_id": case_id,
            "celex_id": row.get(CELLAR_CELEX),
            "ecli": row.get(ECLI) or None,
            "sector": row.get(CELLAR_SECTOR),
            "proc_type": row.get(CELLAR_TYPE_PROCEDURE),
            # best available proxy for date_lodged; CELLAR extraction doesn't
            # capture a distinct "lodged" date today
            "date_lodged": _earliest_iso_date(row.get(CELLAR_CREATION_OF_WORK)),
            "journal_refs": row.get(CELLAR_JOURNAL_ARTICLES),
            "citations_extra_info": row.get(CELLAR_CITATIONS_EXTRA_INFO),
        }


class PostgresItemIdProcessor(_BaseRowProcessor):
    """ECHR rows -> cle_v2.cases + cle_v2.echr_document. Full text loaded separately (case_text_loader.py)."""

    key_field = ECHR_DOCUMENT_ID
    conflict_col = "item_id"
    detail_table = "echr_document"
    detail_conflict_cols = ["item_id"]

    @staticmethod
    def _group_key(row):
        """Return the conceptual ECHR case key used by the production migration.

        HUDOC item IDs identify document/language variants, not cases. ECLI is
        the preferred case identity; communicated cases without an ECLI are
        grouped by application number plus reference date. If HUDOC supplies
        neither, retaining the item ID is the only lossless fallback.
        """
        ecli = str(row.get(ECLI) or "").strip().upper()
        if ecli:
            return f"ECLI:{ecli}"
        appno = str(row.get(ECHR_APPLICANTS) or "").strip()
        reference_date = str(row.get(ECHR_REFERENCE_DATE) or "").strip()[:10]
        if appno:
            return f"APPNO:{appno}:{reference_date}"
        return f"ITEM:{row[ECHR_DOCUMENT_ID]}"

    @staticmethod
    def _canonical_rank(row):
        language = str(row.get(ECHR_LANGUAGE) or "").strip().upper()
        language_rank = {"ENG": 0, "EN": 0, "FRE": 1, "FR": 1}.get(language, 2)
        doctype = str(row.get(ECHR_DOCUMENT_TYPE) or "").strip().upper()
        if "JUD" in doctype:
            doctype_rank = 0
        elif "DEC" in doctype:
            doctype_rank = 1
        elif "COM" in doctype:
            doctype_rank = 2
        else:
            doctype_rank = 3
        return language_rank, doctype_rank, str(row[ECHR_DOCUMENT_ID])

    def _case_row(self, row):
        return {
            "item_id": row[ECHR_DOCUMENT_ID],
            "ecli": row.get(ECLI) or None,
            "title": row.get(ECHR_TITLE),
            "date_decision": row.get(ECHR_JUDGMENT_DATE) or None,
            "source": "HUDOC",
        }

    def _detail_row(self, row, case_id):
        return {
            "item_id": row[ECHR_DOCUMENT_ID],
            "case_id": case_id,
            "language": normalize_language_code(row.get(ECHR_LANGUAGE)),
            "extractedappno": row.get(ECHR_PARTICIPANTS) or row.get(ECHR_APPLICANTS),
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
            "reference_date": row.get(ECHR_REFERENCE_DATE) or None,
        }

    def upload_rows(self, rows: list) -> int:
        """Load every HUDOC variant under one conceptual case.

        This is intentionally row-oriented: an ECHR batch contains multiple
        item IDs for the same case, while the base bulk loader assumes one
        natural key equals one case. The source volumes are small enough that
        correctness and lossless variant handling dominate round-trip count.
        """
        by_item_id = {}
        for row in rows:
            item_id = self._key(row)
            if not item_id:
                logging.warning("NO %s FOUND, skipping row", self.key_field)
                continue
            by_item_id[item_id] = row

        groups = {}
        for row in by_item_id.values():
            groups.setdefault(self._group_key(row), []).append(row)

        loaded = 0
        for group_rows in groups.values():
            canonical = min(group_rows, key=self._canonical_rank)
            try:
                with self.client.transaction():
                    case_id = self.client.upsert_case(**self._case_row(canonical))
                    for row in group_rows:
                        self.client.upsert(
                            table=self.detail_table,
                            conflict_cols=self.detail_conflict_cols,
                            values=self._detail_row(row, case_id),
                        )
                loaded += len(group_rows)
            except Exception as error:
                for row in group_rows:
                    self._log_failure(self._key(row), error)
        return loaded
