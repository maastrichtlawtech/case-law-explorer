# Case context: outcomes, status and procedural timeline

Roadmap Phase 5 (cjeu-migration `docs/CROSS_DATASET_ROADMAP.md`): R5.1 outcomes,
R5.2 status, R5.3 timeline. Tables `case_outcome` and `case_status` come from
caselaw-coolify migration `0009`; their `confidence` columns and the
`case_procedural_link` view from `0012` (mirrored in `db/schema.sql`).

## Data path

Like the link extractors: extractors read only the database they are given and
write JSONL keyed by natural keys (ECLI, else CELEX, else item_id); the
insert-only loader `data_loading/outcome_loader.py` maps them to ids in the
database it runs against (`ON CONFLICT DO NOTHING` on `case_outcome_uk` /
`case_status_uk`). Existing tables are never updated: `cjeu_document.proc_type`
and `procedure_result` stay as they are, the raw value is copied into
`raw_value`. A dataset is removed with one
`DELETE ... WHERE source_dataset = '...'`.

| Source | Dataset | Table | Module |
|---|---|---|---|
| Cellar | `cjeu_proc_type` | case_outcome | `data_extraction/case_context/cjeu_outcomes.py` |
| Cellar | `cjeu_appeal_status` | case_status | `case_status.extract_cjeu` |
| HUDOC | `echr_conclusion` | case_outcome | `echr_outcomes.py` |
| HUDOC | `echr_status` | case_status | `case_status.extract_echr` |
| Rechtspraak | `rs_dictum` | case_outcome | `rs_dictum.py` (needs `RS_DICTUM_ENABLED`) |
| Rechtspraak | `rs_appeal_status` | case_status | `case_status.extract_rs` (needs `RS_DICTUM_ENABLED`) |

Each module's docstring lists its rules, outcome values and confidence.

## Flags

- `OUTCOME_EXTRACTION_ENABLED` (default off): adds the `extract_outcomes` task as
  the last task of each ETL DAG's monthly group (after `extract_links` when
  that is on). Off: the DAGs are unchanged.
- `RS_DICTUM_ENABLED` (default off): the Dutch dictum rules have only been
  tested on illustrative strings; keep it off until a hand-checked db-dev
  sample exists. Off: the two RS files are written empty.

Weekly files: `processed/<month>/outcomes/<source_dataset>.jsonl` (every file
written, possibly empty) and `processed/<month>/outcomes/_counts.<PREFIX>.json`.

Backfill (read-only without `--load`):

```
cd airflow/dags
python -m linking_tasks outcomes --dsn-env CLE_DSN --source echr \
    --from-id 1 --to-id 500000 --out /data/outcomes/echr-1-500000 [--load]
python -m data_loading.outcome_loader --dsn-env CLE_DSN /data/outcomes/echr-1-500000/*.jsonl
```

## Procedural timeline (R5.3)

No new table: `case_procedural_link` (migration `0012`) turns the typed
relations in `case_citation` into time-ordered pairs (`earlier_case_id`,
`later_case_id`, `step`):

| relation_type | step | orientation |
|---|---|---|
| `preliminary_reference` | referral | as stored (national referral -> ruling) |
| `opinion_of` | opinion | as stored (opinion -> judgment) |
| `subject_to_appeal` | appeal | as stored (decision -> appeal, Cellar) |
| `reexamined_by` | review | as stored (decision -> review, Cellar) |
| `national_follow_up` | follow_up | reversed (ruling -> national decision) |
| `appeal_of` | appeal | reversed (decision under appeal -> appeal) |
| `earlier_instance` | earlier_instance | reversed |
| RS `hogerberoep`, `cassatie`, `conclusie`, `prejudicielevraag`, `tussenuitspraak` | appeal, cassation, opinion, referral, interim | by decision date (equal or missing dates left out) |

`db/queries/case_timeline.sql` walks the view from one case in both directions
(parameters `case_id`, `max_depth`) and returns every link of the component,
oldest first, with the relation types, datasets and highest confidence behind
each step. citations-api can serve it as is (R7.5); it reads only the view and
`cases`. Tested in `airflow/dags/tests/test_case_context_db.py::test_case_timeline`
(Tjebbes-shaped fixture: first instance -> appeal -> referral -> ruling <- opinion,
ruling -> follow-up).
