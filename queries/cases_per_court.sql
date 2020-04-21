SELECT CASES.*, COURT.name as court_name
FROM caselaw.recht_li_merge as CASES
LEFT JOIN caselaw.court as COURT ON COU.id = CASES.court_id_case
WHERE COURT.name = 'Gerechtshof Amsterdam';