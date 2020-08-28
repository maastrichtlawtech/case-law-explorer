CREATE OR REPLACE VIEW citations_count AS
	SELECT source_ecli as ecli, count(*) as citations
	FROM caselaw.case_citation
	GROUP BY source_ecli