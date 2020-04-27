SELECT s.name

FROM caselaw.subject as s, 

(SELECT subject_id
FROM (
(SELECT caselaw.case.* 
FROM caselaw.case, caselaw.court as court
WHERE court.name = "Rechtbank Rotterdam" and court.id=caselaw.case.court_id) case_court_ids)
, caselaw.case_subject
WHERE case_court_ids.id = caselaw.case_subject.case_id) selected_ids

WHERE s.id = selected_ids.subject_id