# CELLAR judgment-manifestation repair handoff

## Why this is required

The CJEU pipeline could treat an English summary, résumé/operative extract, or
information notice as the English judgment. Two independent behaviours allowed
that:

1. direct manifestation callers could query a composite or suffixed CELEX such
   as `62020CJ0414_SUM` instead of the canonical `62020CJ0414` work; and
2. when InfoCuria and CELLAR both exposed a language, `cellar-extractor` kept
   InfoCuria's body. InfoCuria's procedure search sometimes returns an Advocate
   General opinion, order, or notice under the judgment slot.

Kamil's 604-case check exposed the failure. In the 2026-09-15 HF snapshot, 294
were repaired to base `CJ` judgments but 310 still pointed at derived works:
282 `_SUM`, 27 `_RES`, and 1 `_INF`.

## Fixed package revision

Airflow must use this immutable `cellar-extractor` revision:

```text
d6024cf6f2773a885906f71116b5431eadefd8dc
```

Upstream PR: <https://github.com/maastrichtlawtech/cellar-extractor/pull/15>

The revision:

- enumerates the date-windowed InfoCuria document catalogue alongside CELLAR
  SPARQL, adding official orders and judgments missing from the CELLAR graph;
- lets InfoCuria correct ECLI/CELEX identity fields while retaining richer
  CELLAR metadata;
- requires an exact requested CELEX before choosing a document from an
  InfoCuria procedure, so a sibling judgment cannot populate an order row;
- limits language fanout to the selected logical document instead of every
  document in the procedure;
- converts InfoCuria numbered CELEX variants such as `.01` to EUR-Lex's
  canonical `(01)` notation;
- canonicalizes CELEX at the public manifestation API boundary;
- exposes `normalize_celex()` publicly;
- lets canonical CELLAR manifestations replace overlapping InfoCuria bodies;
- retains InfoCuria metadata while making CELLAR authoritative for full text;
- has 144 passing unit tests (53 integration tests skipped unless explicitly
  enabled).

`airflow/requirements.txt` pins the revision through an immutable Git URL, and
the Airflow image installs `git` for that build. A GitHub source archive is not
usable because `setuptools-scm` needs repository metadata to determine the
package version. Do not change the pin back to PyPI `2.0.3`; that release
contains the earlier manifestation fix but not catalogue reconciliation. Move
back to PyPI only after an upstream release containing PR #15 is verified.

## Airflow safeguards in this branch

- Extraction canonicalizes CELEX values when calculating coverage.
- Extraction refuses to write a full-text artifact containing composite or
  suffixed CELEX identifiers. This fails before the load stage.
- The full-text loader independently refuses non-canonical CELLAR identifiers.
- Extraction logs ECLI/CELEX identity cardinalities and refuses an ECLI mapped
  to multiple canonical CELEX identifiers in the same window.
- Manual DAG runs now accept `"force_refresh": true`; this is essential because
  existing month-scoped raw artifacts were produced with the old package and
  would otherwise be reused.

## Deployment

1. Merge the Airflow changes and build a fresh image from `airflow/Dockerfile`.
   The dependency must be installed during the image build; restarting an old
   image is not sufficient.
2. In the built image, verify:

   ```bash
   python -c "import cellar_extractor as c; print(c.normalize_celex('62020CJ0414_SUM'))"
   ```

   Expected output: `62020CJ0414`.
3. Deploy the image to every Airflow component that imports DAG code (scheduler
   and workers, and webserver if DAG serialization is not enabled).
4. Confirm the `cellar_etl` DAG parses successfully before enabling its schedule.

The repository's `airflow` branch workflow builds and publishes the Airflow
image. Tag-based publishing is defined in `.github/workflows/docker-publish.yml`
when a versioned release is preferred.

## Historical rerun

Old raw artifacts are unsafe. Trigger `cellar_etl` manually with explicit dates
and forced extraction:

```json
{
  "window_start": "1954-01-01",
  "window_end": "2026-09-22",
  "force_refresh": true,
  "requested_by": "cellar-catalogue-reconciliation"
}
```

The DAG is constrained to one active run/task and processes month windows
sequentially. For operationally smaller retries, submit non-overlapping yearly
runs in chronological order; `max_active_runs=1` will serialize them. Every run
must include `force_refresh: true` until all historical months have been rebuilt.

Do not reset the Airflow metadata database or `CELEX_LAST_DATE`. Explicit
`window_start`/`window_end` values bypass the incremental checkpoint, and a
database reset would destroy unrelated orchestration history.

## Acceptance checks

Before declaring the repair complete:

1. Airflow extraction and load tasks succeed for every historical window.
2. No extraction log contains `non-canonical full-text CELEX`.
3. Re-run the exact 604-case Kamil verification against the rebuilt corpus/data
   product; all 604 must resolve to the base `CJ` CELEX and a full English
   judgment, with zero `_SUM`, `_RES`, or `_INF` substitutions.
4. Recompute `case_text.is_stub` after the full-text replacement.
5. Compare pre/post controls: total cases, citations, Rechtspraak texts, and
   HUDOC texts must not move as a consequence of this repair.
6. Only then re-enable the normal `cellar_etl` schedule and communicate closure.

Also verify the identities that exposed the catalogue gap. At minimum the
rebuilt output must include these current InfoCuria mappings:

- `ECLI:EU:C:2013:654` -> `62012CO0041`
- `ECLI:EU:C:2013:656` -> `62011CO0444`
- `ECLI:EU:C:2014:72` -> `62013CO0298`
- `ECLI:EU:C:2021:965` -> `62021CO0201(01)`
- `ECLI:EU:F:2011:62` -> `62011FO0005`
- `ECLI:EU:T:2003:190` -> `62002TJ0065`
- `ECLI:EU:T:2014:1` -> `62013TO0505(02)`
- `ECLI:EU:T:2014:166` -> `62013TO0505(03)`

Do not reintroduce stale production aliases merely to make corpus and database
counts equal. `ECLI:EU:C:2012:820` and `ECLI:EU:T:2026:68`, for example, are
not present in the current InfoCuria catalogue; their CELEX identifiers resolve
there to `ECLI:EU:C:2012:834` and `ECLI:EU:T:2026:79` respectively. Reconcile
production identities from the authoritative rebuilt corpus and retain an audit
of aliases rather than loading both rows.

## Current production warning (2026-09-15)

An earlier SQL-runner sync applied 37,404 source replacements before it was
stopped during `is_stub` recomputation. Treat production's CJEU text layer and
stub flags as intermediate. The corrected full rerun and final control snapshot
are mandatory; do not use that interrupted run as acceptance evidence.
