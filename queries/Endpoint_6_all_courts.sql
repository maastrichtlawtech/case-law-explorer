SELECT DISTINCT court.*
FROM caselaw.case, caselaw.court as court
WHERE caselaw.case.court_id = court.id