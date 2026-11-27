# Precision sample: `echr_text` (R2.2)

Extractor `echr_text/1.0.0`, datasets `echr_text_cjeu` and `echr_text_rs`.

**Result: 22 correct of 22 checked** (`echr_text_cjeu`). For `echr_text_rs` no
excerpt with context exists in the research files, so 0 RS links were checked
by hand (see below).

## How the sample was made

- Texts: every row of `echr/handcheck.txt` with a context (`ctx` column; 20 of
  22 rows, lines 7 and 19 have none), cjeu-migration
  `migration/verify/research-2026-11-24/`. The excerpts are real HUDOC text,
  copied verbatim; nothing was written for the sample.
- Run: `echr_text.extract_text` on each excerpt, `domestic_flag=True`.
- Candidates: what production holds for each case number and ECLI,
  from `rs/allres_nums.txt`, `rs/res_nums.txt` (case number -> CELEX=case id)
  and `rs/allres_eclis.txt` (ECLI -> case id, CELEX). Dates are not in those
  files, so the "not after the citing decision" rule was not exercised here
  (it is covered by unit tests).
- Every extraction the run produced is listed (22), not a selection. Each was
  checked by reading the excerpt: does the reference name that document?
- The excerpts carry no headings, so every link came out with section `None`
  and relation `cites`; sections and `cites_in_domestic_law` are covered by
  unit tests only.

The Rule column is written in the `<method>/<rule>` form of `artifact.py`; the sample was taken before that convention and its values are restated in it.

| # | Source (handcheck line, production case_id) | Mention(s) as written | Chosen target (CELEX / ECLI) | Rule | Correct | Why |
|---|---|---|---|---|---|---|
| 1 | L2, 3743832 | `C-448/98` | 61998CJ0448 | case_number/cjeu_judgment (AG opinion 61998CC0448 not taken) | y | "the Guimont judgment of 5 December 2000 (C-448/98)": the judgment, no Opinion cue |
| 2 | L3, 3773393 | `C-13/05`, `ECLI:EU:C:2006:456` | 62005CJ0013 / ECLI:EU:C:2006:456 | ecli in the same citation | y | "judgment of 11 July 2006, Sonia Chacón Navas ..., C-13/05, ECLI:EU:C:2006:456" |
| 3 | L4, 3769528 | `C‑175/11` (U+2011), `EU:C:2013:45` | 62011CJ0175 / ECLI:EU:C:2013:45 | ecli | y | "judgment of 31 January 2013, D. and A., C‑175/11, EU:C:2013:45" |
| 4 | L5, 3777361 | `C-670/22`, `EU:C:2024:372` | 62022CJ0670 / ECLI:EU:C:2024:372 | ecli | y | "arrêt M.N. (EncroChat) du 30 avril 2024 (affaire C-670/22, EU:C:2024:372)" |
| 5 | L6, 3722101 | `C-9/91` | 61991CJ0009 | case_number/cjeu_judgment | y | "In the Case C-9/91 The Queen v. Secretary of State for Social Security ... [2000] ECR I-3701": the judgment (EOC case), no Opinion cue |
| 6 | L8, 3779973 | `C-144/23`, `EU:C:2024:881` | 62023CJ0144 / ECLI:EU:C:2024:881 | ecli | y | "judgment of 15 October 2024 in KUBERA (C-144/23, EU:C:2024:881, paragraph 65)" |
| 7 | L9, 3928993 | `C-206/13`, `EU:C:2014:126` | 62013CJ0206 / ECLI:EU:C:2014:126 | ecli | y | "judgment of 6 March 2014, Siragusa , C-206/13, EU:C:2014:126" |
| 8 | L9, 3928993 | `C ‑ 198/13`, `EU:C:2014:2055` | 62013CJ0198 / ECLI:EU:C:2014:2055 | ecli | y | "judgment of 10 July 2014, Julián Hernández and Others , C ‑ 198/13, EU:C:2014:2055" (a second citation in the same excerpt, not in the research check) |
| 9 | L10, 3742097 | `C-72/06` | 62006CJ0072 | case_number/cjeu_judgment | y | "In a judgment of 19 April 2007 (Case C-72/06 Commission v . Greece )" |
| 10 | L11, 3747337 | `C-143/06` | 62006CJ0143 | case_number/cjeu_judgment | y | "l'arrêt du 8 novembre 2007, Ludwigs-Apotheke , C-143/06": "conclusions" comes after the citation, in the next paragraph, so no opinion |
| 11 | L12, 3761947 | `C-6/90`, `C ‑ 9/90`, `EU:C:1991:428` | 61990CJ0006 / ECLI:EU:C:1991:428 | ecli; joined member C-9/90 as a mention of the same link | y | "Francovich breach of EU law (C-6/90 and C ‑ 9/90, EU:C:1991:428)": the joined Francovich judgment |
| 12 | L13, 3776363 | `C-219/15` | 62015CJ0219 | case_number/cjeu_judgment | y | "(CJUE, 16 février 2017, Schmitt, C-219/15)" |
| 13 | L14, 3776066 | `C ‑ 511/18`, `C ‑ 512/18`, `C ‑ 520/18`, `EU:C:2020:791` | 62018CJ0511 / ECLI:EU:C:2020:791 | ecli wins (research picked the AG opinion 62018CC0520) | y | "La Quadrature du Net and Others (C ‑ 511/18, C ‑ 512/18 and C ‑ 520/18, EU:C:2020:791) ... In a judgment of 6 October 2020" |
| 14 | L15, 3778523 | `T‑254/17`, `EU:T:2020:459` | 62017TJ0254 / ECLI:EU:T:2020:459 | ecli | y | "judgment of 5 October 2020 in Intermarché Casino Achats v. Commission (T‑254/17, EU:T:2020:459), the General Court" |
| 15 | L16, 3780170 | `C-40/21` | 62021CJ0040 | case_number/cjeu_judgment; truncated `C:2023:367` not read as an ECLI | y | "judgment of the CJEU ... T.A.C. v. ANI (C-40/21, C:2023:367) of 4 May 2023" |
| 16 | L17, 3755428 | `C-293/12`, `C-594/12`, `EU:C:2014:238` | 62012CJ0293 / ECLI:EU:C:2014:238 | ecli; joined member as a mention | y | "judgment ... of 8 April 2014 in the joined cases of Digital Rights Ireland and Seitinger and Others (C-293/12 and C-594/12, EU:C:2014:238)" |
| 17 | L18, 3768689 | `C-354/20 PPU`, `C-412/20 PPU`, `EU:C:2020:1033` | 62020CJ0354 / ECLI:EU:C:2020:1033 | ecli | y | "judgment of 17 December 2020 in the case of L and P ... (C-354/20 PPU and C-412/20 PPU, EU:C:2020:1033)" |
| 18 | L20, 3756512 | `C ‑ 127/08`, `EU:C:2008:449` | 62008CJ0127 / ECLI:EU:C:2008:449 | ecli (order 62008CO0127 and 62008CP0127 not taken) | y | "a judgment of 25 July 2008 in Blaise Baheten Metock and Others ... (C ‑ 127/08, EU:C:2008:449)" |
| 19 | L21, 3767008 | `C ‑ 135/08`, `EU:C:2010:104` | 62008CJ0135 / ECLI:EU:C:2010:104 | ecli | y | "In its judgment of 2 March 2010, in Rottmann , C ‑ 135/08, EU:C:2010:104" |
| 20 | L22, 3778535 | `C-204/21 R`, `EU:C:2021:593` | 62021CO0204(02) / ECLI:EU:C:2021:593 | ecli wins (research picked the 2023 judgment 62021CJ0204) | y | "the order of the Vice-President of CJEU of 14 July 2021 ( Commission v. Poland , C-204/21 R, EU:C:2021:593)": the interim order |
| 21 | L22, 3778535 | `C-791/19`, `EU:C:2021:596` | 62019CJ0791 / ECLI:EU:C:2021:596 | ecli | y | "the judgment of that court of 15 July 2021 (in Commission v. Poland (Disciplinary regime for judges) , C-791/19, EU:C:2021:596)" (second citation in the excerpt) |
| 22 | L23, 3767037 | `C ‑ 179/11`, `EU:C:2012:594` | 62011CJ0179 / ECLI:EU:C:2012:594 | ecli | y | "its judgment in Cimade and GISTI ... (C ‑ 179/11, EU:C:2012:594) of 27 September 2012" |

Rows 2 and 11 (L3, L12) are cited inside a domestic court's reasoning
reported by the ECtHR (D4). In a full judgment their
section would decide between `cites` and `cites_in_domestic_law`; the excerpts
have no headings.

## Not checked

- `echr_text_rs`: `echr/nl_refs.txt` lists 230 ECLI and ~69 LJN references
  without the surrounding text, and the LJN -> document map lives only in the
  database (`case_identifier` scheme `ljn`), so no RS link could be judged
  here. As a parse check only: all 299 lines of `nl_refs.txt` (230 ECLIs, 69
  LJNs) yield exactly one reference, equal to the value written (ECLIs normalised to upper case,
  LJNs as the 6-character code); this says nothing about which RS document an
  LJN resolves to.
- The 3rd research miss (lines 7 and 19 of `handcheck.txt`) has no context.
