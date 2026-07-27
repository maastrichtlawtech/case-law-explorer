import logging

from airflow.providers.postgres.hooks.postgres import PostgresHook

CONN_PG_CLE = "pg_cle"
SCHEMA = "cle_v2"


class PostgresCLEClient:
    """
    Thin wrapper around the pg_cle Airflow connection. Replaces the
    DynamoDB/S3 loading path (issue #42): case metadata, full text, and
    citations all land in Postgres instead of DynamoDB items / S3 blobs.
    """

    def __init__(self, postgres_conn_id: str = CONN_PG_CLE):
        self.hook = PostgresHook(postgres_conn_id=postgres_conn_id)

    def upsert_case(
        self,
        ecli: str | None = None,
        celex_id: str | None = None,
        item_id: str | None = None,
        title: str | None = None,
        date_decision=None,
        source: str = "",
    ) -> int:
        """
        Upsert a row into cle_v2.cases keyed on whichever natural identifier
        is present (ecli / celex_id / item_id each have their own unique
        constraint), returning the generated case_id for use by the
        source-specific detail-table upserts.
        """
        if not any([ecli, celex_id, item_id]):
            raise ValueError("upsert_case requires at least one of ecli/celex_id/item_id")

        conflict_col = "ecli" if ecli else ("celex_id" if celex_id else "item_id")

        sql = f"""
            INSERT INTO {SCHEMA}.cases (ecli, celex_id, item_id, title, date_decision, sources)
            VALUES (%(ecli)s, %(celex_id)s, %(item_id)s, %(title)s, %(date_decision)s, ARRAY[%(source)s])
            ON CONFLICT ({conflict_col}) DO UPDATE SET
                title = COALESCE(EXCLUDED.title, {SCHEMA}.cases.title),
                date_decision = COALESCE(EXCLUDED.date_decision, {SCHEMA}.cases.date_decision),
                updated_at = now(),
                sources = array(
                    SELECT DISTINCT unnest({SCHEMA}.cases.sources || EXCLUDED.sources)
                )
            RETURNING id;
        """
        params = {
            "ecli": ecli,
            "celex_id": celex_id,
            "item_id": item_id,
            "title": title,
            "date_decision": date_decision,
            "source": source,
        }
        return self._execute_returning_id(sql, params)

    def upsert_case_text(
        self,
        case_id: int,
        language: str,
        source: str,
        fulltext: str | None,
        summary: str | None = None,
        summary_source: str | None = None,
    ) -> None:
        """Replaces upload_fulltext()/S3 (fulltext_bucket_saving.py): full text lands directly in case_text."""
        sql = f"""
            INSERT INTO {SCHEMA}.case_text (case_id, language, source, fulltext, summary, summary_source)
            VALUES (%(case_id)s, %(language)s, %(source)s, %(fulltext)s, %(summary)s, %(summary_source)s)
            ON CONFLICT (case_id, language, source) DO UPDATE SET
                fulltext = COALESCE(EXCLUDED.fulltext, {SCHEMA}.case_text.fulltext),
                summary = COALESCE(EXCLUDED.summary, {SCHEMA}.case_text.summary),
                summary_source = COALESCE(EXCLUDED.summary_source, {SCHEMA}.case_text.summary_source),
                updated_at = now();
        """
        self._execute(
            sql,
            {
                "case_id": case_id,
                "language": language,
                "source": source,
                "fulltext": fulltext,
                "summary": summary,
                "summary_source": summary_source,
            },
        )

    def upsert_citation(
        self,
        source_case_id: int,
        relation_type: str,
        source_dataset: str,
        target_case_id: int | None = None,
        target_ecli_raw: str | None = None,
        target_celex_raw: str | None = None,
        weight: int = 1,
        is_cross_jurisdiction: bool = False,
    ) -> None:
        """
        Replaces nodes_and_edges_loader.py's S3 txt-file merge: citation edges
        become rows here, resolved (target_case_id) or unresolved
        (target_ecli_raw/target_celex_raw), deduped via the table's own
        unique indexes instead of a manual read-modify-write S3 merge.
        """
        if target_case_id is not None:
            conflict_cols = "(source_case_id, target_case_id, relation_type, source_dataset)"
        elif target_ecli_raw is not None:
            conflict_cols = "(source_case_id, target_ecli_raw, relation_type, source_dataset)"
        elif target_celex_raw is not None:
            conflict_cols = "(source_case_id, target_celex_raw, relation_type, source_dataset)"
        else:
            raise ValueError("upsert_citation requires one of target_case_id/target_ecli_raw/target_celex_raw")

        sql = f"""
            INSERT INTO {SCHEMA}.case_citation
                (source_case_id, target_case_id, target_ecli_raw, target_celex_raw,
                 relation_type, source_dataset, weight, is_cross_jurisdiction)
            VALUES
                (%(source_case_id)s, %(target_case_id)s, %(target_ecli_raw)s, %(target_celex_raw)s,
                 %(relation_type)s, %(source_dataset)s, %(weight)s, %(is_cross_jurisdiction)s)
            ON CONFLICT {conflict_cols} DO NOTHING;
        """
        self._execute(
            sql,
            {
                "source_case_id": source_case_id,
                "target_case_id": target_case_id,
                "target_ecli_raw": target_ecli_raw,
                "target_celex_raw": target_celex_raw,
                "relation_type": relation_type,
                "source_dataset": source_dataset,
                "weight": weight,
                "is_cross_jurisdiction": is_cross_jurisdiction,
            },
        )

    def upsert(self, table: str, conflict_cols: list[str], values: dict) -> None:
        """
        Generic upsert into a cle_v2 detail table (rs_document, cjeu_document,
        echr_document, ...), keyed on the given conflict column(s). `values`
        keys must already match real column names in `table` -- callers are
        internal row processors, not external input.
        """
        columns = list(values.keys())
        col_list = ", ".join(columns)
        placeholders = ", ".join(f"%({c})s" for c in columns)
        update_cols = [c for c in columns if c not in conflict_cols]
        update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols) or "updated_at = now()"
        sql = f"""
            INSERT INTO {SCHEMA}.{table} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({", ".join(conflict_cols)}) DO UPDATE SET {update_clause};
        """
        self._execute(sql, values)

    def resolve_case_id(self, ecli: str | None = None, celex_id: str | None = None) -> int | None:
        """Look up an existing case_id by ecli or celex_id, for citation-target resolution."""
        if ecli:
            sql = f"SELECT id FROM {SCHEMA}.cases WHERE ecli = %(val)s"
            val = ecli
        elif celex_id:
            sql = f"SELECT id FROM {SCHEMA}.cases WHERE celex_id = %(val)s"
            val = celex_id
        else:
            return None
        row = self.hook.get_first(sql, parameters={"val": val})
        return row[0] if row else None

    def resolve_case_id_by_item_id(self, item_id: str) -> int | None:
        row = self.hook.get_first(
            f"SELECT id FROM {SCHEMA}.cases WHERE item_id = %(val)s", parameters={"val": item_id}
        )
        return row[0] if row else None

    def list_rs_eclis(self) -> list[str]:
        """All Rechtspraak ECLIs known so far, for the citation-refresh DAGs to iterate over."""
        rows = self.hook.get_records(
            f"SELECT ecli FROM {SCHEMA}.cases WHERE ecli IS NOT NULL AND 'Rechtspraak' = ANY(sources)"
        )
        return [r[0] for r in rows]

    def has_legal_provisions(self, ecli: str) -> bool:
        """Whether an RS case already has resolved legal provisions (replaces the DynamoDB legal_provisions_url check)."""
        row = self.hook.get_first(
            f"""
            SELECT 1 FROM {SCHEMA}.rs_document rd
            JOIN {SCHEMA}.cases c ON c.id = rd.case_id
            WHERE c.ecli = %(ecli)s
              AND rd.legal_provisions IS NOT NULL
              AND array_length(rd.legal_provisions, 1) > 0
            """,
            parameters={"ecli": ecli},
        )
        return row is not None

    def upsert_law_reference(
        self,
        case_id: int,
        raw_reference: str,
        raw_resource: str | None = None,
        role: str = "cited",
        source_dataset: str = "LIDO",
    ) -> None:
        """Upsert into case_law_reference (bwb-scheme citations resolved via LIDO)."""
        sql = f"""
            INSERT INTO {SCHEMA}.case_law_reference
                (case_id, raw_scheme, raw_resource, raw_reference, role, source_dataset)
            VALUES
                (%(case_id)s, 'bwb', %(raw_resource)s, %(raw_reference)s, %(role)s, %(source_dataset)s)
            ON CONFLICT (case_id, raw_scheme, raw_resource, COALESCE(raw_subdivision, ''), role, source_dataset)
            DO NOTHING;
        """
        self._execute(
            sql,
            {
                "case_id": case_id,
                "raw_resource": raw_resource,
                "raw_reference": raw_reference,
                "role": role,
                "source_dataset": source_dataset,
            },
        )

    def _execute(self, sql: str, params: dict) -> None:
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            logging.exception("pg_cle write failed for statement: %s", sql[:120])
            raise

    def _execute_returning_id(self, sql: str, params: dict) -> int:
        conn = self.hook.get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                (returned_id,) = cur.fetchone()
            conn.commit()
            return returned_id
        except Exception:
            conn.rollback()
            logging.exception("pg_cle upsert failed for statement: %s", sql[:120])
            raise
