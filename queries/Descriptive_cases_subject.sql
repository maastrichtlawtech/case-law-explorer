SELECT S.name as subject, cases FROM 
(SELECT subject_id, count(*) as cases
FROM caselaw.case_subject
GROUP BY subject_id
) AS T LEFT JOIN caselaw.subject AS S ON S.id = T.subject_id
;