# Precision sample: Rechtspraak text extractor (rs_text/1.0.0)

Hand check of `data_extraction/linking/rs_text.py` on real passages, roadmap R2.1
(ground rule 6: at least 20 links checked by hand against the text).

## Material

The research files of 2026-11-24 (cjeu-migration,
`migration/verify/research-2026-11-24/`) hold no Rechtspraak passages: `rs/` has
aggregate SQL, reference strings and resolution lists only, and the `goldset/` trace
files record which reference forms occur in each decision, not the text. The only
verbatim case-law passages that cite CJEU and ECtHR decisions are the `ctx` column of
`echr/handcheck.txt` (ECtHR judgments citing CJEU judgments, in English and French). The
extractor's scanning rules do not depend on the citing court, so every non-empty passage
of that file (20 of 22 rows; rows 3754501 and 3772472 have no context) went through the
pure entry point (`extract_records`) as if it were an RS text, with no decision date.

Candidates came from real identifiers only: `cjeu/cn_map.json` (case number → CELEX),
`rs/allres_eclis.txt` and `rs/res_eclis.txt` (ECLI → CELEX), the judgment each hand-check
row names, and the documents the R0.3 evaluation fixture records for the same case numbers
(AG opinions, orders). The research files have no join map, so non-lead joined members
come out unresolved here; in a database run they resolve through `case_identifier`
(source `cellar_joins`).

Application numbers could not be sampled: no research file holds a passage citing an
ECtHR application number (`rs/appno.sql` gives counts only). The `rs_text_echr_appno`
rules are covered by unit tests only.

## Result

**30 of 30 extractions correct** (24 resolved to the cited document, 6 written unresolved
with the right normalised case number and no target). 0 wrong targets, 0 spurious
references. By dataset: `rs_text_ecli` 18 of 18, `rs_text_cjeu_casenum` 12 of 12
(6 resolved, 6 unresolved). Not in the table because no record was written for them: 14
case-number mentions skipped by the nearby-ECLI rule, each written next to the ECLI of
its own case (C-13/05, C-175/11, C-670/22, C-144/23, C-206/13, C-6/90, C-511/18,
C-520/18, T-254/17, C-293/12, C-354/20 PPU, C-127/08, C-135/08, C-179/11; all correct
skips, the ECLI carries the citation), and `C-204/21 R`, dropped because no candidate in
the pool carries the `R` suffix (the right outcome: the only C-204/21 documents in the
pool are not the interim order, which its ECLI EU:C:2021:593 names, row 27).

"Correct" means: the passage cites this document (resolved), or cites this case number
and no document in the candidate pool is it (unresolved).

| # | ECtHR source (cle_v2 case_id) | dataset | mention as written | chosen target | match_method, confidence | correct | why | context |
|---|---|---|---|---|---|---|---|---|
| 1 | 3743832 | rs_text_cjeu_casenum | `C-448/98` | 61998CJ0448 | cjeu_judgment 0.95 | y | Guimont judgment of 5 December 2000 = C-448/98 judgment; no Opinion cue, so not the AG opinion 61998CC0448 that also exists (fixture echr-hc-02-not-ag) | …tion.) The Court of Justice had subsequently, in the Guimont judgment of 5 December 2000 (C-448/98), confirmed the application of the Pistre case-law to natio… |
| 2 | 3773393 | rs_text_ecli | `ECLI:EU:C:2006:456` | ECLI:EU:C:2006:456 | ecli 1.0 | y | Chacón Navas, C-13/05, written with its ECLI; the ECLI is the citation (its case number next to it is skipped by the nearby-ECLI rule) | …owing: judgment of 11 July 2006, Sonia Chacón Navas v Eurest Colectividades SA , C-13/05, ECLI:EU:C:2006:456, in which the CJEU had held that Directive 2000/78/EC could… |
| 3 | 3769528 | rs_text_ecli | `EU:C:2013:45` | ECLI:EU:C:2013:45 | ecli 1.0 | y | D. and A., C-175/11, short ECLI of the judgment of 31 January 2013 | …ng out their role (see, to that effect, judgment of 31 January 2013, D. and A., C‑175/11, EU:C:2013:45, paragraph 99, and ECtHR, 28 June 1984, Campbell and Fell v… |
| 4 | 3769528 | rs_text_ecli | `CE:ECHR:1984:0628JUD000781977` | ECLI:CE:ECHR:1984:0628JUD000781977 | ecli 1.0 | y | Campbell and Fell v. United Kingdom, 28 June 1984, ECtHR ECLI written out (application 7819/77) | …U:C:2013:45, paragraph 99, and ECtHR, 28 June 1984, Campbell and Fell v. United Kingdom , CE:ECHR:1984:0628JUD000781977, § 79; 2 June 2005, Zolotas v… |
| 5 | 3777361 | rs_text_ecli | `EU:C:2024:372` | ECLI:EU:C:2024:372 | ecli 1.0 | y | M.N. (EncroChat), arrêt du 30 avril 2024, affaire C-670/22: short ECLI of that judgment | …oints 25 à 27). 74 . Dans son arrêt M.N. (EncroChat) du 30 avril 2024 (affaire C-670/22, EU:C:2024:372), la CJUE a examiné, en Grande chambre, une série de questi… |
| 6 | 3722101 | rs_text_cjeu_casenum | `C-9/91` | 61991CJ0009 | cjeu_judgment 0.95 | y | Case C-9/91 (EOC case), the judgment; no Opinion cue | …ssarily linked to the difference between pensionable ages for men and women. In the Case C-9/91 The Queen v. Secretary of State for Social Security , ex pa… |
| 7 | 3779973 | rs_text_ecli | `EU:C:2024:881` | ECLI:EU:C:2024:881 | ecli 1.0 | y | KUBERA, judgment of 15 October 2024, C-144/23: short ECLI | …he CJEU confirmed this obligation in its judgment of 15 October 2024 in KUBERA (C-144/23, EU:C:2024:881, paragraph 65) in the context of decisions refusing leave t… |
| 8 | 3928993 | rs_text_ecli | `EU:C:2014:126` | ECLI:EU:C:2014:126 | ecli 1.0 | y | Siragusa, judgment of 6 March 2014, C-206/13: short ECLI | …of affecting it (see, among others, CJEU, judgment of 6 March 2014, Siragusa , C-206/13, EU:C:2014:126, paragraph 25; judgment of 10 July 2014, Julián Hernández… |
| 9 | 3928993 | rs_text_ecli | `EU:C:2014:2055` | ECLI:EU:C:2014:2055 | ecli 1.0 | y | Julián Hernández and Others, judgment of 10 July 2014: short ECLI | …:126, paragraph 25; judgment of 10 July 2014, Julián Hernández and Others , C ‑ 198/13, EU:C:2014:2055, paragraph 37; and judgment of 5 May… |
| 10 | 3928993 | rs_text_cjeu_casenum | `C ‑ 198/13` | unresolved C-198/13 | case_number None | y | C ‑ 198/13 (spaced U+2011) is Julián Hernández; unresolved only because the research files hold no document row for C-198/13 (in a database run its own ECLI next to it makes the rule skip it) | …3, EU:C:2014:126, paragraph 25; judgment of 10 July 2014, Julián Hernández and Others , C ‑ 198/13, EU:C:2014:2055, paragraph 37; and judgment of 5 May… |
| 11 | 3742097 | rs_text_cjeu_casenum | `C-72/06` | 62006CJ0072 | cjeu_judgment 0.95 | y | Case C-72/06 Commission v. Greece, judgment of 19 April 2007 | …ts obligations concerning the reception of refugees. In a judgment of 19 April 2007 (Case C-72/06 Commission v . Greece ), the CJEC found that Greece had fai… |
| 12 | 3747337 | rs_text_cjeu_casenum | `C-143/06` | 62006CJ0143 | cjeu_judgment 0.95 | y | Ludwigs-Apotheke, arrêt du 8 novembre 2007, C-143/06, Rec. p. I-9623: the judgment | …de mise sur le marché] (voir, en ce sens, l’arrêt du 8 novembre 2007, Ludwigs-Apotheke , C-143/06, Rec. p. I-9623, points 33 et 35). 33. Ainsi que l’a expos… |
| 13 | 3761947 | rs_text_ecli | `EU:C:1991:428` | ECLI:EU:C:1991:428 | ecli 1.0 | y | Francovich (C-6/90 and C-9/90): short ECLI of the judgment | …ment under appeal did not derive from a Francovich breach of EU law (C-6/90 and C ‑ 9/90, EU:C:1991:428) but rather from the damage allegedly caused by the impleme… |
| 14 | 3761947 | rs_text_cjeu_casenum | `C ‑ 9/90` | unresolved C-9/90 | case_number None | y | C ‑ 9/90 is the non-lead joined member of Francovich; unresolved because the research files have no join map; correct reference, no wrong target | …n the judgment under appeal did not derive from a Francovich breach of EU law (C-6/90 and C ‑ 9/90, EU:C:1991:428) but rather from the damage allegedly caused… |
| 15 | 3776363 | rs_text_cjeu_casenum | `C-219/15` | 62015CJ0219 | cjeu_judgment 0.95 | y | Schmitt, CJUE 16 février 2017, C-219/15: the judgment | …ts 3.2, 3.3, 4.1 à 4.3 et 5.1 de l’annexe II de celle-ci (CJUE, 16 février 2017, Schmitt, C-219/15). Il résulte de cette décision que, en présence d’indices… |
| 16 | 3776066 | rs_text_ecli | `EU:C:2020:791` | ECLI:EU:C:2020:791 | ecli 1.0 | y | La Quadrature du Net and Others, ECLI of the judgment of 6 October 2020 (the earlier case-number guess picked the AG opinion in C-520/18; fixture echr-ecli-wins-14) | …such offences.” La Quadrature du Net and Others (C ‑ 511/18, C ‑ 512/18 and C ‑ 520/18, EU:C:2020:791) 78 . In a judgment of 6 October 2020, given pursuant to r… |
| 17 | 3776066 | rs_text_cjeu_casenum | `C ‑ 512/18` | unresolved C-512/18 | case_number None | y | C ‑ 512/18, non-lead member of La Quadrature du Net; unresolved here (no join map), correct reference | …ration for or commission of such offences.” La Quadrature du Net and Others (C ‑ 511/18, C ‑ 512/18 and C ‑ 520/18, EU:C:2020:791) 78 . In a judgment of 6 Oct… |
| 18 | 3778523 | rs_text_ecli | `EU:T:2020:459` | ECLI:EU:T:2020:459 | ecli 1.0 | y | Intermarché Casino Achats v. Commission, T‑254/17, General Court judgment of 5 October 2020: short ECLI | …. In the judgment of 5 October 2020 in Intermarché Casino Achats v. Commission (T‑254/17, EU:T:2020:459), the General Court based its examination of the effectiven… |
| 19 | 3780170 | rs_text_cjeu_casenum | `C-40/21` | ECLI:EU:C:2023:367 | cjeu_judgment 0.95 | y | T.A.C. v. ANI, C-40/21, judgment of 4 May 2023 (the text's truncated 'C:2023:367' is not taken as an ECLI; the case number resolves to the judgment ECLI:EU:C:2023:367) | …tice of the European Union (“the CJEU”) T.A.C. v. Agenția Națională de Integritate (ANI) (C-40/21, C:2023:367) of 4 May 2023 may be found in Păcurar v. Roman… |
| 20 | 3755428 | rs_text_ecli | `EU:C:2014:238` | ECLI:EU:C:2014:238 | ecli 1.0 | y | Digital Rights Ireland and Seitlinger, joined cases, short ECLI of the judgment of 8 April 2014 | …e joined cases of Digital Rights Ireland and Seitinger and Others (C-293/12 and C-594/12, EU:C:2014:238) declared invalid the Data Retention Directive 2006/24/EC l… |
| 21 | 3755428 | rs_text_cjeu_casenum | `C-594/12` | unresolved C-594/12 | case_number None | y | C-594/12, non-lead member of Digital Rights Ireland; unresolved here (no join map), correct reference | …2014 in the joined cases of Digital Rights Ireland and Seitinger and Others (C-293/12 and C-594/12, EU:C:2014:238) declared invalid the Data Retention Directi… |
| 22 | 3768689 | rs_text_ecli | `CE:ECHR:2016:1020JUD000733413` | ECLI:CE:ECHR:2016:1020JUD000733413 | ecli 1.0 | y | Muršić v. Croatia, 20 October 2016, ECtHR ECLI written out (quoted inside a CJEU passage) | …, 20 October 2016, Muršić v. Croatia , CE:ECHR:2016:1020JUD000733413, §§ 75 and 114 and the case-law cited).” 53. In its judgme… |
| 23 | 3768689 | rs_text_ecli | `EU:C:2020:1033` | ECLI:EU:C:2020:1033 | ecli 1.0 | y | Openbaar Ministerie (Independence of the issuing judicial authority), C-354/20 PPU and C-412/20 PPU: short ECLI of the judgment | …sterie (Independence of the issuing judicial authority) , (C-354/20 PPU and C-412/20 PPU, EU:C:2020:1033), the CJEU ruled that where the executing judicial authorit… |
| 24 | 3768689 | rs_text_cjeu_casenum | `C-412/20 PPU` | unresolved C-412/20 | case_number None | y | C-412/20 PPU, non-lead member; unresolved here (no join map), correct reference, PPU suffix dropped from the key | …Openbaar Ministerie (Independence of the issuing judicial authority) , (C-354/20 PPU and C-412/20 PPU, EU:C:2020:1033), the CJEU ruled that where the executing j… |
| 25 | 3756512 | rs_text_ecli | `EU:C:2008:449` | ECLI:EU:C:2008:449 | ecli 1.0 | y | Metock, C ‑ 127/08, short ECLI of the judgment (not the order or the CP document, fixture echr-hc-20-not-ag) | …e Baheten Metock and Others v. Minister for Justice, Equality and Law Reform (C ‑ 127/08, EU:C:2008:449) the Court of Justice of the European Union (CJEU) clarifie… |
| 26 | 3767008 | rs_text_ecli | `EU:C:2010:104` | ECLI:EU:C:2010:104 | ecli 1.0 | y | Rottmann, judgment of 2 March 2010, C ‑ 135/08: short ECLI | …ICE OF THE EUROPEAN UNION 23. In its judgment of 2 March 2010, in Rottmann , C ‑ 135/08, EU:C:2010:104, the Court of Justice of the European Union (CJEU) examined… |
| 27 | 3778535 | rs_text_ecli | `EU:C:2021:593` | ECLI:EU:C:2021:593 | ecli 1.0 | y | Commission v. Poland, order of the Vice-President of 14 July 2021, C-204/21 R: the ECLI names the order; the case number next to it is not linked to the 2023 judgment (fixture echr-ecli-wins-22) | …order of the Vice-President of CJEU of 14 July 2021 ( Commission v. Poland , C-204/21 R, EU:C:2021:593) and the judgment of that court of 15 July 2021 (in Commiss… |
| 28 | 3778535 | rs_text_ecli | `EU:C:2021:596` | ECLI:EU:C:2021:596 | ecli 1.0 | y | Commission v. Poland (Disciplinary regime for judges), judgment of 15 July 2021: short ECLI | …urt of 15 July 2021 (in Commission v. Poland (Disciplinary regime for judges) , C-791/19, EU:C:2021:596),… |
| 29 | 3778535 | rs_text_cjeu_casenum | `C-791/19` | unresolved C-791/19 | case_number None | y | C-791/19 is that judgment; unresolved here (no document row for C-791/19 in the research files); in a database run its own ECLI next to it makes the rule skip it | …of that court of 15 July 2021 (in Commission v. Poland (Disciplinary regime for judges) , C-791/19, EU:C:2021:596),… |
| 30 | 3767037 | rs_text_ecli | `EU:C:2012:594` | ECLI:EU:C:2012:594 | ecli 1.0 | y | Cimade and GISTI, C ‑ 179/11, judgment of 27 September 2012: short ECLI | …rieur, de l’Outre ‑ mer, des Collectivités territoriales et de l’Immigration (C ‑ 179/11, EU:C:2012:594) of 27 September 2012, the CJEU held: “... Regarding the p… |
