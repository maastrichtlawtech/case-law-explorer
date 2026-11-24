# Precision sample: ag_opinions (R2.4)

Extractor `ag_opinions/1.0.0`, source_dataset `cjeu_ag_link`, relation
`opinion_of`. Date of the check: 2026-11-24.

## Data

Real research data only: cjeu-migration
`migration/verify/research-2026-11-24/rs/allres_nums.txt`, the production
`cases` rows (CELEX = case id) of 952 CJEU case numbers cited in the RS
sample. Each case number's documents are the candidates; every CELEX with type
`CC` is run as an opinion through `ag_opinions.resolve_opinion` with the other
documents of its number as the CELEX lookup. The file carries no dates, so
the date guard and the case-number fallback (rule 2) cannot be exercised
here; they are covered by the unit tests.

## Run

| Result | Opinions |
|---|---|
| CC → CJ (`celex/celex_cj`) | 686 |
| CC → CO (`celex/celex_co`) | 5 |
| nothing to link in the file | 16 |

The 5 CC → CO results are all members of the joined Aalborg Portland appeals
(62000CC0205, 0211, 0213, 0217, 0219), whose judgment is 62000CJ0204 under the
lead number. They are not counted as correct: an order sharing a non-lead
number is weaker evidence than the joined judgment, which is why rule 2 (the
first judgment carrying the opinion's case number, via `case_identifier`, which
holds joined members) now runs before the CO swap, and the CO swap has
confidence 0.8. The 16 without a target are opinions whose number has no CJ or
CO document in the file (e.g. the PVC II members C-244/99 ... C-254/99, joined
under C-238/99 P; C-520/18, joined under La Quadrature du Net C-511/18): rule 2
resolves those in the database when `case_identifier` lists the joined member.

## Hand check

22 CC → CJ records drawn with `random.seed(20261124)`; `random.sample(records, 22)`.
For each: the judgment's CELEX has the opinion's year and number with type CJ,
both documents are listed under the same case number in production, and the
judgment is the only CJ document of that number (where an order exists too, the
judgment was preferred).

**22 correct of 22 checked.** (Including the 5 CO results above as not
verified, 22 of 27 records looked at are confirmed correct; the 5 are the
reason for the rule order.)

| # | Case number | Opinion | Judgment | Rule | Documents of the case number | Verdict |
|---|---|---|---|---|---|---|
| 1 | C-219/17 | 62017CC0219 | 62017CJ0219 | celex_cj | 62017CC0219, 62017CJ0219 | correct |
| 2 | C-104/95 | 61995CC0104 | 61995CJ0104 | celex_cj | 61995CC0104, 61995CJ0104 | correct |
| 3 | C-135/08 | 62008CC0135 | 62008CJ0135 | celex_cj | 62008CC0135, 62008CJ0135 | correct |
| 4 | C-9/87 | 61987CC0009 | 61987CJ0009 | celex_cj | 61987CC0009, 61987CJ0009 | correct |
| 5 | C-201/13 | 62013CC0201 | 62013CJ0201 | celex_cj | 62013CC0201, 62013CJ0201 | correct |
| 6 | C-6/90 | 61990CC0006 | 61990CJ0006 | celex_cj | 61990CC0006, 61990CJ0006 | correct |
| 7 | C-467/04 | 62004CC0467 | 62004CJ0467 | celex_cj | 62004CC0467, 62004CJ0467 | correct |
| 8 | C-496/01 | 62001CC0496 | 62001CJ0496 | celex_cj | 62001CC0496, 62001CJ0496 | correct |
| 9 | C-212/06 | 62006CC0212 | 62006CJ0212 | celex_cj | 62006CC0212, 62006CJ0212 | correct |
| 10 | C-440/19 | 62019CC0440 | 62019CJ0440 | celex_cj | 62019CC0440, 62019CJ0440 | correct |
| 11 | C-42/17 | 62017CC0042 | 62017CJ0042 | celex_cj | 62017CC0042, 62017CJ0042, 62017CO0042 | correct |
| 12 | C-617/10 | 62010CC0617 | 62010CJ0617 | celex_cj | 62010CC0617, 62010CJ0617, 62010CO0617 | correct |
| 13 | C-280/93 | 61993CC0280 | 61993CJ0280 | celex_cj | 61993CC0280, 61993CJ0280, 61993CO0280 | correct |
| 14 | C-162/22 | 62022CC0162 | 62022CJ0162 | celex_cj | 62022CC0162, 62022CJ0162 | correct |
| 15 | C-103/18 | 62018CC0103 | 62018CJ0103 | celex_cj | 62018CC0103, 62018CJ0103 | correct |
| 16 | C-641/18 | 62018CC0641 | 62018CJ0641 | celex_cj | 62018CC0641, 62018CJ0641 | correct |
| 17 | C-6/01 | 62001CC0006 | 62001CJ0006 | celex_cj | 62001CC0006, 62001CJ0006 | correct |
| 18 | C-148/02 | 62002CC0148 | 62002CJ0148 | celex_cj | 62002CC0148, 62002CJ0148 | correct |
| 19 | C-203/15 | 62015CC0203 | 62015CJ0203 | celex_cj | 62015CC0203, 62015CJ0203, 62015CO0203 | correct |
| 20 | C-791/19 | 62019CC0791 | 62019CJ0791 | celex_cj | 62019CC0791, 62019CJ0791, 62019CO0791(01) | correct |
| 21 | C-452/16 | 62016CC0452 | 62016CJ0452 | celex_cj | 62016CC0452, 62016CJ0452 | correct |
| 22 | C-316/19 | 62019CC0316 | 62019CJ0316 | celex_cj | 62019CC0316, 62019CJ0316 | correct |
