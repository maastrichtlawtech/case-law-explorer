# Precision sample: `cjeu_text` (R2.6)

Extractor `cjeu_text/1.0.0`, dataset `cjeu_text_echr`.

**Result: 22 correct of 22 checked** (20 ECLI references from the research
scan without surrounding text, 2 ECLI references with real context). Plus the
gold-set reference (application number 17341/03) as a unit test. Name + date
links (flag `NAME_DATE_LINKS`, D5): **0 checked**, see below.

## How the sample was made

- `cjeu/echr.json` (cjeu-migration `migration/verify/research-2026-11-24/`)
  holds the `CE:ECHR` identifiers a regular expression found in a 6% sample of
  production's English CELLAR texts: 200 distinct (text, identifier) pairs, 179
  distinct ECLIs, all present in production (`hit`). The file keeps the
  identifier and the source case id, not the surrounding text. Sample: every
  10th pair of the sorted 200 (20 rows), each run through
  `cjeu_text.extract_text` as `CE:ECHR:` + the captured token (the form the
  research regex required in the text).
- Checked: the extractor yields exactly one link, to the ECLI written, and that
  ECLI is a case in production. For an explicit ECLI this is what "correct"
  means; whether the citing passage relies on the case is not judged.
- Rows 21-22: CJEU text quoted verbatim in ECtHR judgments
  (`echr/handcheck.txt`, the CJEU's own paragraph with its citations), run as
  CJEU text.

| # | Source (production case_id) | Mention as written | Chosen target | Rule | Correct | Why |
|---|---|---|---|---|---|---|
| 1 | 3856766 | `CE:ECHR:1989:0707JUD001403888` | ECLI:CE:ECHR:1989:0707JUD001403888 | ecli | y | parsed exactly; date 1989-07-07, JUD, application 14038/88 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 2 | 3857268 | `CE:ECHR:2011:0707JUD003745202` | ECLI:CE:ECHR:2011:0707JUD003745202 | ecli | y | parsed exactly; date 2011-07-07, JUD, application 37452/02 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 3 | 3858345 | `CE:ECHR:2009:0210JUD001493903` | ECLI:CE:ECHR:2009:0210JUD001493903 | ecli | y | parsed exactly; date 2009-02-10, JUD, application 14939/03 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 4 | 3858345 | `CE:ECHR:2015:0430JUD000345312` | ECLI:CE:ECHR:2015:0430JUD000345312 | ecli | y | parsed exactly; date 2015-04-30, JUD, application 3453/12 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 5 | 3858485 | `CE:ECHR:2003:1127JUD002662495` | ECLI:CE:ECHR:2003:1127JUD002662495 | ecli | y | parsed exactly; date 2003-11-27, JUD, application 26624/95 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 6 | 3859304 | `CE:ECHR:2010:0624JUD003014104` | ECLI:CE:ECHR:2010:0624JUD003014104 | ecli | y | parsed exactly; date 2010-06-24, JUD, application 30141/04 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 7 | 3859667 | `CE:ECHR:2012:0117JUD000813909` | ECLI:CE:ECHR:2012:0117JUD000813909 | ecli | y | parsed exactly; date 2012-01-17, JUD, application 8139/09 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 8 | 3860014 | `CE:ECHR:1990:0830JUD001224486` | ECLI:CE:ECHR:1990:0830JUD001224486 | ecli | y | parsed exactly; date 1990-08-30, JUD, application 12244/86 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 9 | 3862517 | `CE:ECHR:2007:0607JUD007125101` | ECLI:CE:ECHR:2007:0607JUD007125101 | ecli | y | parsed exactly; date 2007-06-07, JUD, application 71251/01 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 10 | 3864744 | `CE:ECHR:2018:0628JUD000182806` | ECLI:CE:ECHR:2018:0628JUD000182806 | ecli | y | parsed exactly; date 2018-06-28, JUD, application 1828/06 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 11 | 3865769 | `CE:ECHR:1987:0326JUD000924881` | ECLI:CE:ECHR:1987:0326JUD000924881 | ecli | y | parsed exactly; date 1987-03-26, JUD, application 9248/81 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 12 | 3865769 | `CE:ECHR:2021:0525JUD005817013` | ECLI:CE:ECHR:2021:0525JUD005817013 | ecli | y | parsed exactly; date 2021-05-25, JUD, application 58170/13 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 13 | 3866310 | `CE:ECHR:2014:0227JUD001710310` | ECLI:CE:ECHR:2014:0227JUD001710310 | ecli | y | parsed exactly; date 2014-02-27, JUD, application 17103/10 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 14 | 3867387 | `CE:ECHR:2015:0113JUD003563213` | ECLI:CE:ECHR:2015:0113JUD003563213 | ecli | y | parsed exactly; date 2015-01-13, JUD, application 35632/13 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 15 | 3867611 | `CE:ECHR:2010:1221JUD002940808` | ECLI:CE:ECHR:2010:1221JUD002940808 | ecli | y | parsed exactly; date 2010-12-21, JUD, application 29408/08 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 16 | 3868071 | `CE:ECHR:2016:0323JUD004361111` | ECLI:CE:ECHR:2016:0323JUD004361111 | ecli | y | parsed exactly; date 2016-03-23, JUD, application 43611/11 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 17 | 3870420 | `CE:ECHR:2002:0207JUD002849695` | ECLI:CE:ECHR:2002:0207JUD002849695 | ecli | y | parsed exactly; date 2002-02-07, JUD, application 28496/95 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 18 | 3872038 | `CE:ECHR:1978:0118JUD000531071` | ECLI:CE:ECHR:1978:0118JUD000531071 | ecli | y | parsed exactly; date 1978-01-18, JUD, application 5310/71 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 19 | 3872038 | `CE:ECHR:2010:0601JUD002297805` | ECLI:CE:ECHR:2010:0601JUD002297805 | ecli | y | parsed exactly; date 2010-06-01, JUD, application 22978/05 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 20 | 3872707 | `CE:ECHR:2006:0301JUD005658100` | ECLI:CE:ECHR:2006:0301JUD005658100 | ecli | y | parsed exactly; date 2006-03-01, JUD, application 56581/00 encoded in it; in the research's resolved list (`hit`), i.e. `cases.ecli` exists in production |
| 21 | D. and A. (C-175/11) as quoted in handcheck.txt L4 | `CE:ECHR:1984:0628JUD000781977` | ECLI:CE:ECHR:1984:0628JUD000781977 | ecli | y | "ECtHR, 28 June 1984, Campbell and Fell v. United Kingdom , CE:ECHR:1984:0628JUD000781977, § 79": date and application 7819/77 match the case named |
| 22 | L and P (C-354/20 PPU) as quoted in handcheck.txt L18 | `CE:ECHR:2016:1020JUD000733413` | ECLI:CE:ECHR:2016:1020JUD000733413 | ecli | y | ", 20 October 2016, Muršić v. Croatia , CE:ECHR:2016:1020JUD000733413, §§ 75 and 114": date and application 7334/13 match the case named |

In the same two excerpts nothing else was extracted: "2 June 2005, Zolotas v"
is cut off by the excerpt, and no application number appears.

## Application numbers

No CJEU text with an application-number citation is in the research files
(the gold-set opinion 62012CC0199 is recorded without its text). The gold
reference is covered by unit tests on the minimal citation strings carrying
the recorded forms (`F. c. Royaume-Uni`, `17341/03`; `(déc.)` and without):
both resolve to ECLI:CE:ECHR:2004:0622DEC001734103. Guards against false
positives (regulation numbers such as "Regulation (EEC) No 1408/71" and
"règlement (CEE) n° 1408/71", directive numbers, numbers without an ECtHR cue)
are unit-tested, not measured on real text.

## Name + date (D5)

Implemented behind `NAME_DATE_LINKS` (default off): exact normalised
`echr_document.docname` and `judgement_date`, `match_method = 'name_date'`,
written unresolved when no document or more than one document matches.
Number checked against real data: **0** (no database with CJEU texts and
`echr_document` was available here; D5 requires a 100-row stratified sample at
95% precision before the flag is switched on).
