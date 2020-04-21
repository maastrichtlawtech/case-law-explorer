SELECT CASES.*, SUBJ.name as subject_name
FROM caselaw.recht_li_merge as CASES
LEFT JOIN caselaw.case_subject as CS ON CASES.id_case = CS.case_id
JOIN caselaw.subject as SUBJ ON SUBJ.id = CS.subject_id
WHERE SUBJ.name = 'Aanbestedingsrecht';