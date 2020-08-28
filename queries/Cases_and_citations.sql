SELECT C1.*
,C2.id as idT
,C2.date as dateT
,C2.description as descriptionT
,C2.venue as venueT
,C2.procedure_type as procedure_typeT
,C2.subject as subjectT
,C2.court as courtT 
FROM
	(# Table with all cases joined with their citations
    SELECT CS.id
	,CS.date
	,CS.description
	,CS.venue
	,CS.procedure_type
	,CS.subject
	,CS.court
	,CC.source_ecli
	,CC.target_ecli
	FROM caselaw.case_subjects as CS
	JOIN caselaw.case_citation as CC ON CS.ecli = CC.source_ecli
	WHERE 1=1
	AND CS.description is not NULL
	) AS C1
LEFT JOIN caselaw.case_subjects as C2 ON C2.ecli = C1.target_ecli
WHERE 1=1
OR C1.subject = 'Belastingrecht' 
OR C1.subject = 'Bestuursrecht' 
OR C1.subject = 'Civiel recht'
OR C1.subject = 'Strafrecht'
ORDER BY C2.id desc # Getting only the cases which target ecli has content
LIMIT 8 # Only 8 metadata of complete citations available
;