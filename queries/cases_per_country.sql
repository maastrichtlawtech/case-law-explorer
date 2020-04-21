SELECT CASES.*, COUNTRY.name as country_name
FROM caselaw.recht_li_merge as CASES
LEFT JOIN caselaw.case_country as CC ON CASES.id_case = CC.case_id
JOIN caselaw.country as COUNTRY ON COUNTRY.id = CC.country_id
WHERE COUNTRY.name = 'Netherlands';