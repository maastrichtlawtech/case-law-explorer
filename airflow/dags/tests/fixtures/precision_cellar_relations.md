# Precision sample: cellar_relations (R2.5)

Extractor `cellar_relations/1.0.0`, source_dataset `cellar_relation_resolved`.
Date of the check: 2026-11-24.

## Data

Real research data only (cjeu-migration `migration/verify/research-2026-11-24/cjeu/`):

- `uuid_rows.json`: 3,247 production `case_citation` rows (`cellar_sparql`)
  whose target is a Cellar URI, of which 1,790 `subject_to_appeal` and 22
  `referred_for_preliminary_ruling` are in scope (the file has no
  `reexamined_by` rows: production has 5);
- `uuid_dossier.json` (UUID → `cdm:dossier_identifier`, 2,742 URIs) and
  `uuid_map.json` (UUID → `cdm:resource_legal_id_celex`, 128 URIs), both from
  Cellar's public SPARQL endpoint, used as the cache files;
- `cn_map.json`: production case number → CELEX list (3,728 numbers), as the
  `case_identifier` candidates. The stored case numbers there carry no
  procedure suffix, and the files have no dates, so the date guards are not
  exercised here (unit tests cover them).

## Run

| Outcome | Rows |
|---|---|
| appeal_of, appeal judgment (`case_number/uuid_dossier_cjeu_judgment`) | 958 |
| appeal_of, appeal judgment, earliest of several | 4 |
| appeal_of, the only order (`case_number/uuid_dossier_cjeu_order`) | 641 |
| skipped: several orders and no judgment | 28 |
| skipped: no candidate without a conflicting suffix (`P(R)`, `P-OST`, ...) | 75 |
| skipped: case number not in `cn_map.json` | 74 |
| skipped: dossier without `P` (`case:C-176/19`, `C-560/22` for T-560/22) | 9 |
| skipped: appeal court does not match (C-454/17 P "appealing" a CJ judgment) | 1 |
| referred_for_preliminary_ruling: target is a published request (`CN`) | 5 |
| referred_for_preliminary_ruling: ruling not in the lookup (no dates here) | 17 |

1,603 records (1,596 distinct dossier UUIDs resolved, written as
`cellar_dossier_uuid` identifier candidates). The research estimate was 3,348
of 4,038 resolvable `subject_to_appeal` rows in production; this file holds
1,790 of them.

`referred_for_preliminary_ruling` on Cellar's sector-8 national decisions mixes
referrals and follow-ups: of the 17 resolved CELEX targets (judgments or
orders), the national decision (dated in its CELEX, `8YYYYCCMMDD`) is two or
more years after the year of the CJEU case number in 10 (e.g. 82023DE0526(51)
→ 62009CJ0256, 14 years; 82018AT0228(51) → 62016CJ0498), so those are almost
certainly decisions after the ruling, while 3 are from the case's own year
(e.g. 82022DE0525(51) → 62022CJ0462). The module therefore decides the
relation from the two decision dates in the database (on or before the ruling:
`preliminary_reference`, after: `national_follow_up`) and skips rows without
both dates. None of these are counted below: the research files have no ruling
dates.

## Hand check

22 `appeal_of` records drawn with `random.seed(20261124)`; 22 from
`random.sample(appeal_of_records, 22)`. For each: Cellar's dossier identifier
of the URI is an appeal (`P`) to the next court up (General Court → Court of
Justice, Civil Service Tribunal → General Court); the appeal decision's CELEX
has the dossier's year and number; it is a judgment, or the only order of that
number; its year is not before the year of the decision under appeal; and the
row direction is appeal → decision under appeal. The decisions' texts were not
read; the dossier identifier comes from Cellar itself.

**22 correct of 22 checked.**

match_method is written in the `<method>/<rule>` form of `artifact.py`; the sample was taken before that convention and its values are restated in it.

| # | Decision under appeal (target) | Cellar URI (UUID) | Dossier | Appeal decision (source) | Method, confidence | Verdict |
|---|---|---|---|---|---|---|
| 1 | 62011TJ0674 | `a0d2afab-4558-11e7-aea8-01aa75ed71a1` | C-657/15 P | 62015CJ0657 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 2 | 62021TJ0324 | `de71c42f-1e71-11ef-a251-01aa75ed71a1` | C-297/23 P | 62023CJ0297 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 3 | 62010TO0084 | `265cc4b6-2a7a-11e7-9412-01aa75ed71a1` | C-586/11 P | 62011CO0586 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
| 4 | 62011TO0466 | `3c3e00dd-29c2-11e7-ab65-01aa75ed71a1` | C-616/12 P | 62012CO0616 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
| 5 | 62021TJ0354 | `d89b4bc5-82bd-11ee-99ba-01aa75ed71a1` | C-249/23 P | 62023CJ0249 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 6 | 62021TJ0268 | `a219b131-d96d-11ef-be2a-01aa75ed71a1` | C-490/23 P | 62023CJ0490 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 7 | 62011TJ0217 | `ddedb7fe-4cfd-11e7-a5ca-01aa75ed71a1` | C-338/15 P | 62015CO0338 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
| 8 | 62020TO0684 | `b083e974-f772-11ec-b94a-01aa75ed71a1` | C-152/22 P | 62022CO0152 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
| 9 | 62018TO0599 | `aaee15c5-dfd5-11eb-895a-01aa75ed71a1` | C-874/19 P | 62019CJ0874 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 10 | 62018TO0282(01) | `9893ed2e-9556-11ec-b4e4-01aa75ed71a1` | C-364/20 P | 62020CJ0364 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 11 | 62015FO0021 | `3d36debb-e497-11e7-9749-01aa75ed71a1` | T-682/15 P | 62015TJ0682 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 12 | 62023TJ0370 | `a0452316-c074-11f0-a612-01aa75ed71a1` | C-779/24 P | 62024CJ0779 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 13 | 62016TJ0183 | `ce1330a4-ef10-11e9-a32c-01aa75ed71a1` | C-590/19 P | 62019CO0590 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
| 14 | 62017TJ0229 | `d2247210-eac6-11eb-93a8-01aa75ed71a1` | C-475/19 P | 62019CJ0475 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 15 | 62023TJ1061 | `d8ac7d55-d0e0-11f0-8da2-01aa75ed71a1` | C-532/25 P | 62025CO0532 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
| 16 | 62019TJ0670 | `e51a172d-3b2e-11ed-9c68-01aa75ed71a1` | C-613/21 P | 62021CJ0613 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 17 | 62013TJ0472 | `81219f14-a650-11ea-bb7a-01aa75ed71a1` | C-591/16 P | 62016CJ0591 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 18 | 62011TJ0305 | `484064e4-dd84-11e6-ad7c-01aa75ed71a1` | C-268/14 P | 62014CJ0268 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 19 | 62020TJ0513 | `f6fe5623-f1f5-11f0-8d3c-01aa75ed71a1` | C-124/24 P | 62024CJ0124 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 20 | 62008FJ0038 | `c2bf1392-3f82-11e7-a08e-01aa75ed71a1` | T-167/09 P | 62009TJ0167 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 21 | 62019TJ0279 | `6c9350f4-e78e-11ee-9ea8-01aa75ed71a1` | C-779/21 P | 62021CJ0779 | case_number/uuid_dossier_cjeu_judgment 0.95 | correct |
| 22 | 62020TJ0187 | `761069d8-5667-11ec-91ac-01aa75ed71a1` | C-490/21 P | 62021CO0490 | case_number/uuid_dossier_cjeu_order 0.85 | correct |
