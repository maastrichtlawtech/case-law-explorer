# Linking evaluation set

`linking_evaluation.json` is the regression fixture of roadmap item R0.3: every
cross-dataset link extractor (RS, ECtHR and CJEU text extractors, Cellar
referral parsing, AG opinion links) is scored on it after each change. It holds
the 17 citation links of the hand-checked E-01 gold set (Tjebbes C-221/17 and
X, Y and Z C-199/12 to C-201/12), the 3 gold-set links that are not citations,
and adversarial and negative pairs taken from the research files of
2026-11-24 (cjeu-migration, branch `docs/cross-dataset-linking-roadmap`,
commit `13a9904`, `migration/verify/research-2026-11-24/`).

Every excerpt (`text`) is copied byte for byte from those files: the
`national_judgement_xml` of the CJEU document (`cjeu/nj_nl.json`) or the
`ctx` column of `echr/handcheck.txt`. Where the files hold no passage, `text`
is null and `requires_db` is true. Each entry's `provenance` names the file and
line it comes from.

## Using it

```python
from tests.linking_evaluation import load_fixture, score

fixture = load_fixture()
predictions = [
    {"source": "ECLI:NL:HR:2020:593", "target": "ECLI:EU:C:2019:189", "relation_type": "cites"},
    {"source": {"case_id": 3743832}, "target": {"celex": "61998CJ0448"}, "relation_type": "cites"},
]
result = score(predictions, fixture, mode="document")
result["overall"]        # {"tp", "fp", "fn", "tn", "entries", "precision", "recall"}
result["by_category"]    # the same per category
result["by_tag"]         # the same per tag
result["misses"]         # false negatives and false positives, with the offending predictions
result["unjudged"]       # predictions from a fixture source that no entry judges
```

- **Modes.** `mode="document"` scores a run over whole documents (database or
  backfill run): entries with `document_level: true` (69). `mode="excerpt"`
  scores a pure-text unit run, where the extractor is applied to each entry's
  `text` and its predictions carry that entry's `source`: entries with an
  excerpt (54). The 14 entries with `document_level: false` are only valid for
  their excerpt.
- **Counting.** A positive is a TP when a matching prediction exists, otherwise
  an FN. A negative is an FP when any of its `must_not_link` targets is
  predicted, otherwise a TN. Precision and recall are `fractions.Fraction`
  (`None` when the denominator is 0). Predictions the fixture doesn't judge are
  listed in `unjudged` and not counted as FP, because the fixture isn't
  exhaustive.
- **Matching.** Endpoints are compared on the first identifier both sides
  carry, in the order `ecli`, `celex`, `case_id`, `case_number`, `appno`, after
  normalisation (hyphen variants such as U+2011, spaces in `C 199/12`, leading
  zeros, `PPU`/`P`/`R` suffixes, `ECLI:` prefix). A bare string endpoint is
  read as whichever identifier it looks like. `case_id` is the production
  `cle_v2` id that `echr/handcheck.txt` records for ECtHR sources; resolve it to
  an ECLI before using it against another database (R1.5).
- **Relation types.** `cites`, `preliminary_reference` (national referral →
  CJEU ruling), `national_follow_up` (national decision after the ruling →
  ruling), `opinion_of` (AG opinion → judgment). A negative may list several
  and may set `direction: "either"` to forbid the reverse link too. A `null`
  source on a negative forbids the link from any source.

## Categories

| Category | Positive | Negative | With excerpt | What it tests |
|---|---|---|---|---|
| `goldset_citation` | 17 | 0 | 4 | The 17 citation links of the E-01 gold set: referrals from Cellar `*A9*` lines (incl. zaaknummer variants such as `201012342/T1/V2` for `201012342/1/T1/V2`), RS citations by ECLI and by case number only, HR:2022:637 citing only in `summary` (art. 81 RO), ECtHR citations of joined case numbers and `C 199/12` with a plain space, and the AG opinion 62012CC0199 citing F. v. UK by application number |
| `goldset_non_citation` | 0 | 3 | 0 | Ramadan, K2 and Usmanov ↔ Tjebbes: thematic links, not citations in either direction (D1) |
| `cellar_referral_follow_up` | 4 | 0 | 4 | `*P1*` lines → the decision after the ruling; the X, Y and Z lines give the referral's zaaknummer (`.../T1/V2`) while the decision is filed as `.../1/V2` |
| `referral_foreign_court` | 0 | 10 | 10 | Referral data naming only Belgian courts. 3 of them (Oudenaarde, Turnhout, Dendermonde) pass `parse_match.py`'s foreign-court pattern; no RS document may be linked as referral or follow-up |
| `target_after_source` | 0 | 4 | 0 | Referrals predate their ruling, so they never `cites` it |
| `referral_not_a_citation` | 0 | 4 | 0 | The rulings don't name their referring decisions, so no `cites` row from the ruling to the referral |
| `ag_opinion_vs_judgment` | 0 | 1 | 0 | The X, Y and Z judgment does not cite F. v. UK; only the AG opinion does (D3) |
| `ag_opinion_link` | 1 | 0 | 0 | 62012CC0199 → 62012CJ0199 by the CELEX CC → CJ swap (R2.4) |
| `rs_text_echr` | 1 | 0 | 0 | The referral RVS:2017:1098 cites Ramadan v. Malta |
| `rs_case_number_near_other_ecli` | 2 | 0 | 0 | RBGEL:2026:1195: C-684/16 sits 65 characters from the ECLI of C-619/16; both must be found |
| `echr_text_cjeu` | 16 | 0 | 16 | Hand-checked correct ECtHR → CJEU citations, with U+2011 and spaced hyphens, joined cases, `PPU`, a truncated ECLI (`C:2023:367`) and an Opinion cue next to a citation of the judgment |
| `echr_quoted_domestic_judgment` | 2 | 0 | 2 | CJEU citations inside a domestic court's reasoning reported by the ECtHR (D4 open: the relation may become `cites_in_domestic_law`) |
| `echr_ecli_overrides_case_number` | 2 | 2 | 4 | 2 of the 3 hand-check misses: an ECLI in the same citation names the right document (the La Quadrature du Net judgment, not the AG opinion in non-lead C-520/18; the order in C-204/21 R, not the 2023 judgment) |
| `ag_opinion_without_cue` | 0 | 13 | 13 | The cited case number also has an AG opinion in the database, but the excerpt cites the judgment with no Opinion cue (excerpt mode only) |
| `judgment_vs_order` | 0 | 1 | 1 | Metock C-127/08 also has an order and a CP document; the excerpt cites the judgment (excerpt mode only) |
| **Total** | **45** | **38** | **54** | 83 entries |

Tags record secondary aspects and are scored separately (`by_tag`). Counts
cover all entries carrying the tag, positives and negatives:
`ecli_in_same_citation` 26, `referral_xml` 18, `u2011_hyphen` 11, `referral` 8,
`joined_member_in_citation` 8, `spaced_hyphen` 8, `case_number` 6,
`case_number_only` 6, `joined_case_affaire` 6, `ecli` 5, `joined_member` 5,
`zaaknummer_variant` 5, `d4` 4, `echr_text_cjeu` 4, `d1` 3,
`passes_parse_match_filter` 3, `nearby_ecli_other_case` 2, `ppu_suffix` 2,
`target_after_source` 2, `truncated_ecli` 2, and 1 each for `ag_opinion_source`,
`appno`, `art81_ro`, `celex_cc_to_cj`, `cjeu_text_echr`, `d3`,
`opinion_cue_nearby`, `plain_space_case_number`, `summary_only`,
`zaaknummer_list`.

The scores of a perfect extractor: every positive found, no negative predicted
(`test_positive_predictions_never_trip_a_negative` checks that the positives
don't collide with the negatives).

## Not yet covered

These adversarial cases are named in the roadmap but the research files hold no
concrete source document or passage for them, so they are left out rather than
made up:

- **Court typos as known source errors** (C-178/98 written for C-178/94): the
  README records the typo but not the RS document it was found in.
- **Non-CJEU "C-"/"T-" codes**: no example with its source in the files.
- **The Caribbean "Gemeenschappelijk Hof van Justitie"**: mentioned as a
  warning only, with no document.
- **Application numbers shared by several ECtHR documents, and "(dec.)"
  selecting the decision**: `rs/appno.sql` gives only aggregate counts; the 7
  multi-judgment cases and the 24 checked mentions are not listed.
- **AG opinion with an Opinion cue present** (the link must go to the opinion):
  the 82 `prejudicielevraag` relations to AG opinions are counted, not listed.
- **The third ECtHR hand-check miss**: rows 7 (C-73/07) and 19 (C-254/99 →
  61999CC0254, the only C-254/99 document) have no context in
  `echr/handcheck.txt`, so neither can be judged. Both are left out.
- **Case numbers dated after the source decision**, other than the referrals:
  the ECtHR and RS scan files carry no source dates.
- **ECtHR → RS citations and LJN resolution** (`echr/nl_refs.txt`): 5 of them
  were hand-checked, but the file doesn't say which.
- **CJEU → ECtHR by ECLI** (`cjeu/echr.json`): 20 were checked, but the file
  doesn't say which.
- **Duplicate publications and HR/PHR ambiguity in referral matching**
  (`cjeu/resolved.json` `amb`; RVS:2012:BW3076 = RVS:2012:4057): which
  document is canonical waits on D2.
- **Cellar CELEX suffixes** (`_INF`, `_EXT`, `_RES` in `rs/unres6.txt`): the
  intended resolution of a suffixed target is not recorded.
- **ECtHR sources by ECLI**: the hand-check rows identify ECtHR sources only by
  production `case_id`.

## Updating

Add entries only from material that can be cited (a research file and line, or
a hand check recorded alongside it), keep excerpts verbatim, give every
negative a `reason`, and bump `schema_version` when a field changes meaning.
Run `python -m pytest tests/test_linking_evaluation.py -q` from `airflow/dags`.
