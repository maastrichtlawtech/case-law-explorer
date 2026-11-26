# Precision sample: EU-law references (R3.2-R3.4)

Extractors: `rs_eu_law` (`rs_text_eu_law`), `echr_eu_law` (`echr_text_eu_law`),
`cellar_law_refs` (`cellar_law_ref`); rules in `data_extraction/linking/eu_law.py`.

## What real text was available

The research files (cjeu-migration `migration/verify/research-2026-11-24/`)
hold **no Rechtspraak judgment text with an EU-law reference**: `rs/cjeu_refs_sample.txt`
lists only extracted case numbers, not passages. Every real passage with an EU
act in it was found by running `eu_law.scan` over all 18,612 text units
(1,333,380 characters) of the research files and of `fixtures/linking_evaluation.json`
(both profiles, every hit listed and checked by hand):

* `echr/handcheck.txt` (ECtHR judgment excerpts, also in `linking_evaluation.json`);
* `cjeu/nj_nl.json`: Cellar `national_judgement` lines for Dutch referrals, whose
  literature entries carry Dutch annotation titles. Not a text the extractors scan,
  but the only real Dutch EU-law references there.

That is **9 real passages: 6 with a reference, 3 without**. Fewer than the
20 the roadmap asks for, so this sample is **not a precision figure**: it needs a
db-dev sample (>= 20 per dataset, drawn from real `rs_text_eu_law` and
`echr_text_eu_law` output) before any of this data reaches production. The rest of
the unit tests are **illustrative strings** written in the forms courts use; they test
the rules, not the precision.

## Real passages, checked by hand

| # | Source (research file, case) | Text as written | Extracted | Correct? |
|---|---|---|---|---|
| 1 | handcheck.txt, ECtHR case 3773393 | "held that Directive 2000/78/EC could not be extended" | 32000L0078 | y |
| 2 | handcheck.txt, ECtHR case 3779973 | "... Article 267 TFEU, read in the light of the second paragraph" | TFEU (12016E/TXT) art. 267 | y |
| 3 | handcheck.txt, ECtHR case 3755428 | "the Data Retention Directive 2006/24/EC laying down" | 32006L0024 | y |
| 4 | nj_nl.json #885 (C-271/17 PPU) | "Kaderbesluit 2002/584/JBZ - Europees aanhoudingsbevel" | 32002F0584 | y |
| 5 | nj_nl.json #427 (C-126/97 Eco Swiss, 1 June 1999) | "schending art. 81 EG" | EC Treaty, Amsterdam numbering (12006E/TXT) art. 81 | y |
| 6 | nj_nl.json #427 (same) | "artikel 85, tweede lid EG-Verdrag" | EC Treaty, Amsterdam numbering (12006E/TXT) art. 85(2) | **n**: the author means the pre-1999 art. 85(2) (competition), now art. 81 |
| 7 | handcheck.txt, ECtHR case 3773393 | "Article 1 of that Directive" | nothing (anaphora) | y (true negative) |
| 8 | handcheck.txt, ECtHR case 3742097 | "the Reception Directive" | nothing (names 2003/9/EC or 2013/33/EU) | y (true negative) |
| 9 | handcheck.txt, ECtHR case 3776363 | "l'article 16, paragraphe 6, de ladite directive" | nothing (anaphora) | y (true negative) |

Result: **5 / 6** references right at act, article and treaty version; 6 / 6 at act
level; 3 / 3 true negatives. No false positive in the whole research corpus.

Miss #6 is the EC Treaty renumbering (1 May 1999): texts after that date still cite the
old numbers without a cue, sometimes next to the new ones for the same provision, as
here. The extractor reads "(oud)", "(old)", "(ancien)" as the old numbering and otherwise
goes by the citing decision's date; EC Treaty references carry confidence 0.8 so they
can be filtered.

## Cellar (R3.2)

The Cellar records are structured (one stored CELEX per row), so their precision is
the CELEX rule, unit-tested in `test_linking_eu_law.py::test_cellar_target`. The one
real Cellar value in the repository, `legal_resource = 12016P047` of the real
cellar-extractor row in `test_cjeu_loader.py` (ECLI:EU:C:2026:691), maps to the
Charter (2016) article 47, which is right. Sector counts on db-dev (expected from the
research: 3 = 127,681; 1 = 106,308; 2 = 2,828; 4 = 1,466; 5 skipped = 5,423) are to be
confirmed by the backfill's counts file.
