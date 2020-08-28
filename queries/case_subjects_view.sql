CREATE OR REPLACE VIEW case_subjects AS
	SELECT C.*, SUB.subject, COU.name as court
	FROM caselaw.case as C 
	LEFT JOIN caselaw.court as COU ON C.court_id = COU.id
	RIGHT JOIN (
	SELECT case_id, S.name as subject
	FROM caselaw.case_subject as CS, caselaw.subject as S
	WHERE CS.subject_id = S.id ) as SUB ON C.id = SUB.case_id

