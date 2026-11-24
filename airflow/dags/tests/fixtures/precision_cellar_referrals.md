# Precision sample: cellar_referrals (R2.3)

Extractor `cellar_referrals/1.0.0`, source_dataset `cellar_national_judgement`.
Date of the check: 2026-11-24.

## Data

Real research data only (cjeu-migration `migration/verify/research-2026-11-24/cjeu/`):

- the notices: `nj_nl.json`, the `national_judgement_xml` of the 1,119 CJEU
  documents whose notice names a Dutch court;
- the Rechtspraak side: `matches.json`, the `rs_document` rows (ECLI, instance,
  zaaknummer) that the research query found on each line's date whose
  zaaknummer contains one of the line's numbers (capped at 1,000 rows by the
  sql-runner). The date of each candidate is the date of the line it was found
  for (`entries.json`).

The candidates are therefore only decisions that share a number with some
line, so the zaaknummer rules are tested against real near misses (other
courts, other numbers on the same day, duplicate publications, the Parket bij
de Hoge Raad), but the date + court fallback cannot be measured here (it is
off by default). No `rs_document.language` or `date_published` is in the
files, so duplicate publications fall back to "LJN-style ECLI first, then the
lowest ECLI".

## Run over the whole research set

2,487 tagged lines; 823 records written (821 before the publication rule was
relaxed on 2026-11-24, see below):

| Relation | match_method (method part) | Records |
|---|---|---|
| preliminary_reference | metadata | 450 |
| preliminary_reference | ecli | 27 |
| preliminary_reference | ljn | 2 |
| national_follow_up | metadata | 183 |
| national_follow_up | ecli | 119 |
| national_follow_up | ljn | 2 |
| earlier_instance | metadata | 40 |

The run counted methods only; written today these are `metadata/<rule>`
(`zaaknummer`, `zaaknummer_core`, `zaaknummer_base`), `ecli` (or
`ecli/ecli_inconsistent`) and `ljn`.

Lines skipped: 426 foreign or unrecognised court, 32 interim (`*I*`), 8
ambiguous (different decisions), 1,126 no candidate that day (expected: the
candidate file only has decisions sharing a number), 67 no zaaknummer match,
2 no date.

Against the research resolution (`resolved.json`, 634 unique pairs from
substring matching with court checks): 624 of the 634 are produced; the 10
not produced are all `*I*` interim lines, which this module skips. 197 pairs
are new: 140 from an ECLI written in the line or in the rechtspraak.nl link
after it, and 59 that the research left ambiguous (`resolved.json` `amb`)
and that the duplicate-publication rule (D2) resolves to one case. The 8
lines this module still finds ambiguous are candidates that differ in
instance or zaaknummer.

Publications count as one decision when they have the same instance and date
and every case number of one matches a number of the other in some written
form (with or without the Raad van State instance segment, with or without a
letter prefix). Before 2026-11-24 the sets of forms had to be equal, which
left two `amb` pairs ambiguous that this rule now resolves, both checked on
the metadata: `ECLI:NL:HR:1997:AG1530` (`Nr. 16.300`) = `ECLI:NL:HR:1997:AG7243`
(`16.300`), Hoge Raad 06/06/1997, -> ECLI:EU:C:1999:437 (metadata/zaaknummer
0.92); and `ECLI:NL:CBB:2013:37` (`AWB 11/780 AWB 13/243`) =
`ECLI:NL:CBB:2013:39` (`AWBB 11/780 AWB 13/243`, a typo of the prefix), CBB
04/07/2013, -> ECLI:EU:C:2014:2296 (metadata/zaaknummer_core 0.87). Both go to
the lowest ECLI, as for the other duplicate publications.

## Hand check

25 records drawn with `random.seed(20261124)`; `random.sample(records, 25)`
from the 821 records of the run before the publication rule change (the two
records it added are checked above).
For each: the line's court is the candidate's instance (same court seat for
district courts and courts of appeal), the line's date is the decision date,
and the line's number is the decision's zaaknummer (exactly, or its numeric
core); or the line itself names the ECLI. The CJEU target is the document
that carries the notice. The Rechtspraak texts themselves were not read (no
database access from this host); the check is on the metadata.

**25 correct of 25 checked.**

match_method is written in the `<method>/<rule>` form of `artifact.py`; the sample was taken before that convention and its values are restated in it. (0.92: the canonical one of several publications; 0.9: the numeric core of the number.)

| # | CJEU target | Line, relation | Line (as stored) | Dutch decision | RS instance, date, zaaknummer | Method, confidence | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | ECLI:EU:C:2003:270 | A9 preliminary_reference | `*A9* Centrale Raad van Beroep, verzoek van 06/10/1999 (97/8115 ZFW ; 97/10642 ZFW)` | ECLI:NL:CRVB:1999:ZB8801 | Centrale Raad van Beroep, 1999-10-06, `97/8115 ZFW-P, 97/10642 ZFW-P` | metadata/zaaknummer_core 0.9 | correct |
| 2 | ECLI:EU:C:2020:1033 | A9 preliminary_reference | `*A9* Rechtbank Amsterdam, Tussenuitspraak van 03/09/2020 (13/751520-20 ; 20/3065)` | ECLI:NL:RBAMS:2020:4328 | Rechtbank Amsterdam, 2020-09-03, `13/751520-20` | metadata/zaaknummer 0.95 | correct |
| 3 | ECLI:EU:C:1976:166 | P6 national_follow_up | `*P6* Hoge Raad der Nederlanden, arrest van 23/09/1988 (13303)` | ECLI:NL:HR:1988:AD5713 | Hoge Raad, 1988-09-23, `13303` | metadata/zaaknummer 0.95 | correct |
| 4 | ECLI:EU:C:1989:226 | A9 preliminary_reference | `*A9* Raad van State, afdeling rechtspraak, uitspraak van 20/10/1987 (R02.85.0196)` | ECLI:NL:RVS:1987:AN0789 | Raad van State, 1987-10-20, `R02.85.0196` | metadata/zaaknummer 0.95 | correct |
| 5 | ECLI:EU:C:2020:951 | A9 preliminary_reference | `*A9* Rechtbank Den Haag, zittingsplaats Haarlem, Tussenuitspraak van 05/03/2019 (AWB 18/3951)` | ECLI:NL:RBDHA:2019:2095 | Rechtbank Den Haag, 2019-03-05, `AWB 18/3951` | metadata/zaaknummer 0.95 | correct |
| 6 | ECLI:EU:T:2026:376 | A9 preliminary_reference | `*A9* Hoge Raad der Nederlanden, Belastingkamer, Arrest van 28/03/2025 (22/00711)` | ECLI:NL:HR:2025:472 | Hoge Raad, 2025-03-28, `22/00711` | metadata/zaaknummer 0.95 | correct |
| 7 | ECLI:EU:C:2021:506 | A9 preliminary_reference | `*A9* Raad van State, Beslissing van 25/09/2019 (201809965/1/V3)` | ECLI:NL:RVS:2019:3262 | Raad van State, 2019-09-25, `201809965/1/V3` | metadata/zaaknummer 0.95 | correct |
| 8 | ECLI:EU:C:2000:294 | A8 earlier_instance | `*A8* Gerechtshof 's-Gravenhage, 1e meervoudige belastingkamer, uitspraak van 10/04/1996 (93/2636)` | ECLI:NL:GHSGR:1996:AA4247 | Gerechtshof 's-Gravenhage, 1996-04-10, `93/2636` | metadata/zaaknummer 0.92 | correct |
| 9 | ECLI:EU:C:2019:125 | A9 preliminary_reference | `*A9* Gerechtshof Den Haag, Arrest van 04/07/2017 (200.185.962/01)` | ECLI:NL:GHDHA:2017:1935 | Gerechtshof Den Haag, 2017-07-04, `200.185.962/01` | metadata/zaaknummer 0.95 | correct |
| 10 | ECLI:EU:C:2014:2318 | P1 national_follow_up | `*P1* Hoge Raad der Nederlanden, 3e kamer, uitspraak van 04/12/2015 (12/02876)` | ECLI:NL:HR:2015:3467 | Hoge Raad, 2015-12-04, `12/02876` | metadata/zaaknummer 0.95 | correct |
| 11 | ECLI:EU:C:2015:261 | A9 preliminary_reference | `*A9* Centrale Raad van Beroep, meervoudige kamer, uitspraak van 01/07/2013 (08/5412 AKW-P ; 08/6650 AOW-P ; 09/6430 AOW-P)` | ECLI:NL:CRVB:2013:783 | Centrale Raad van Beroep, 2013-07-01, `08/5412 AKW-P, 08/6650 AOW-P, 09/6430 AOW-P` | metadata/zaaknummer 0.95 | correct |
| 12 | ECLI:EU:C:2002:750 | A8 earlier_instance | `*A8* Gerechtshof Amsterdam, 3e meervoudige belastingkamer, uitspraak van 16/09/1998 (96/2897)` | ECLI:NL:GHAMS:1998:AA7580 | Gerechtshof Amsterdam, 1998-09-16, `P96/2897` | metadata/zaaknummer_core 0.9 | correct |
| 13 | ECLI:EU:C:2024:892 | P1 national_follow_up | `*P1* Rechtbank Den Haag, zittingsplaats Roermond, Beslissing van 18/12/2024 (ECLI:NL:RBDHA:2024:21443)` | ECLI:NL:RBDHA:2024:21443 | (ECLI written in the line) | ecli 0.99 | correct |
| 14 | ECLI:EU:C:2014:136 | P1 national_follow_up | `*P1* Raad van State, afdeling bestuursrechtspraak, uitspraak van 20/08/2014 (201007849/1/V2)` | ECLI:NL:RVS:2014:3172 | Raad van State, 2014-08-20, `201007849/1/V2` | metadata/zaaknummer 0.95 | correct |
| 15 | ECLI:EU:C:2013:720 | A9 preliminary_reference | `*A9* Raad van State, afdeling bestuursrechtspraak, uitpsraak van 18/04/2012 (201109928/T1/V2)` | ECLI:NL:RVS:2012:BW3076 | Raad van State, 2012-04-18, `201109928/T1/V2` | metadata/zaaknummer 0.92 | correct |
| 16 | ECLI:EU:C:2025:662 | P1 national_follow_up | `*P1* Hoge Raad der Nederlanden, Beslissing van 21/11/2025 (ECLI:NL:HR:2025:1726)` | ECLI:NL:HR:2025:1726 | (ECLI written in the line) | ecli 0.99 | correct |
| 17 | ECLI:EU:C:2017:674 | A9 preliminary_reference | `*A9* Hoge Raad der Nederlanden, Arrest van 30/10/2015 (14/05851)` | ECLI:NL:HR:2015:3176 | Hoge Raad, 2015-10-30, `14/05851` | metadata/zaaknummer 0.95 | correct |
| 18 | ECLI:EU:C:2006:458 | P1 national_follow_up | `*P1* Hoge Raad der Nederlanden, 1e kamer, arrest van 30/11/2007 (C02/228 HR ; C02/280 HR)` | ECLI:NL:HR:2007:BA9608 | Hoge Raad, 2007-11-30, `C02/228HR en C02/280HR` | metadata/zaaknummer 0.95 | correct |
| 19 | ECLI:EU:C:1994:351 | A9 preliminary_reference | `*A9* Kantongerecht 's-Gravenhage, vonnis van 12/01/1993 (10092/92)` | ECLI:NL:KTGSGR:1993:AG0528 | Kantongerecht 's-Gravenhage, 1993-01-12, `10092/92` | metadata/zaaknummer 0.95 | correct |
| 20 | ECLI:EU:C:2026:884 | A9 preliminary_reference | `*A9* College van Beroep voor het bedrijfsleven, Beslissing van 21/01/2025 (22/362)` | ECLI:NL:CBB:2025:15 | College van Beroep voor het bedrijfsleven, 2025-01-21, `22/362` | metadata/zaaknummer 0.95 | correct |
| 21 | ECLI:EU:C:2023:346 | A9 preliminary_reference | `*A9* Gerechtshof Amsterdam, uitspraak van 08/02/2022 (20/00353 ; 20/00372)` | ECLI:NL:GHAMS:2022:296 | Gerechtshof Amsterdam, 2022-02-08, `20/00353 en 20/00372` | metadata/zaaknummer 0.95 | correct |
| 22 | ECLI:EU:C:1974:73 | P1 national_follow_up | `*P1* Gerechtshof 's-Gravenhage, 1e meervoudige belastingkamer, arrest van 28/10/1974 (1/1974)` | ECLI:NL:GHSGR:1974:AX4170 | Gerechtshof 's-Gravenhage, 1974-10-28, `1/1974` | metadata/zaaknummer 0.95 | correct |
| 23 | ECLI:EU:C:2018:110 | A9 preliminary_reference | `*A9* Hoge Raad der Nederlanden, Arrest van 08/07/2016 (15/00878)` | ECLI:NL:HR:2016:1351 | Hoge Raad, 2016-07-08, `15/00878` | metadata/zaaknummer 0.95 | correct |
| 24 | ECLI:EU:C:2017:362 | A9 preliminary_reference | `*A9* Hoge Raad der Nederlanden, arrest van 29/01/2016 (14/02778)` | ECLI:NL:HR:2016:133 | Hoge Raad, 2016-01-29, `14/02778` | metadata/zaaknummer 0.95 | correct |
| 25 | ECLI:EU:C:1992:435 | A9 preliminary_reference | `*A9* Gerechtshof te Amsterdam, 2e meervoudige belastingkamer, uitspraak van 04/06/1991 (5272/89)` | ECLI:NL:GHAMS:1991:AW6025 | Gerechtshof Amsterdam, 1991-06-04, `5272/89` | metadata/zaaknummer 0.95 | correct |

Notes on the sample:

- #1, #12: numeric-core matches (`97/8115 ZFW` = `97/8115 ZFW-P`, `96/2897` =
  `P96/2897`).
- #6: the target is a General Court document (ECLI:EU:T:2026:376): since 2024
  the General Court hears some preliminary references (here a Hoge Raad tax
  referral of 2025), so the target is right.
- #8, #15: duplicate publications resolved to one case (confidence 0.92); #15
  is the gold-set referral RVS:2012:BW3076.
- #19: `Kantongerecht 's-Gravenhage` maps to the seat Den Haag.
