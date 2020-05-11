SELECT CASES.*
,COUNTRY.name as country_name
,COURT.name as court_name
,SUBJ.name as subject_name
FROM caselaw.recht_li_merge as CASES
LEFT JOIN caselaw.case_country as CC ON CASES.id_case = CC.case_id
LEFT JOIN caselaw.country as COUNTRY ON COUNTRY.id = CC.country_id
LEFT JOIN caselaw.case_subject as CS ON CASES.id_case = CS.case_id
LEFT JOIN caselaw.subject as SUBJ ON SUBJ.id = CS.subject_id
LEFT JOIN caselaw.court as COURT ON COURT.id = CASES.court_id_case
WHERE COUNTRY.name = 'Netherlands'
OR SUBJ.name = 'Aanbestedingsrecht'
OR COURT.name = 'Gerechtshof Amsterdam';
