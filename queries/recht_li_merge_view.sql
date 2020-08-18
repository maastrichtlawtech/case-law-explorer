CREATE OR REPLACE VIEW recht_li_merge AS
	SELECT 
		C.id as id_case,
        C.ecli,
        C.date as date_case,
        C.name,
        C.description,
        C.language,
        C.venue,
        C.abstract,
        C.procedure_type,
        C.lodge_date,
        C.link,
        C.court_id as court_id_case,
		LI.name as LI_name,
		LI.date as LI_date,
		LI.abstract as LI_abstract,
		LI.subject as LI_subject,
		LI.link as LI_link,
		LI.OriginalUrl,
		LI.Jurisdiction,
		LI.DocumentType,
		LI.CaseNumber,
		LI.lodge_date as LI_lodge_date,
		LI.DateAdded as LI_date_added,
		LI.Sources as LI_sources,
		LI.court as LI_court
	FROM caselaw.case as C
	LEFT JOIN caselaw.legal_intelligence_case as LI ON C.ecli = LI.ecli