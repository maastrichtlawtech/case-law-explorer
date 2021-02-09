"""
The final set of attribute names to be used.
Original RS terminology: see example_Rechtspraak.xml tags
Original LI terminology: see https://www.legalintelligence.com/files/li-search-endpoint.pdf
"""

# corresponding fields in RS and LI (change here if you want to remap fields):
ECLI = RS_IDENTIFIER = 'ecli'  # ECLI (European Case Law Identifier) -- unique identifier for court decisions in Europe
SOURCE = LI_DOCUMENT_TYPE = 'source'  # source of case (so far: always 'Rechtspraak')
JURISDICTION_COUNTRY = LI_JURISDICTION = 'jurisdiction_country'  # country of jurisdiction (so far: always 'NL')
RS_ISSUED = LI_PUBLICATION_DATE = 'date_publication'  # date of document publication
RS_CREATOR = LI_ISSUING_INSTITUTION = 'instance'  # name of instance (court)
RS_DATE = LI_ENACTMENT_DATE = 'date_decision'  # date of court decision
RS_ZAAKNUMMER = LI_CASE_NUMBER = 'case_number'  # case number, for internal use by courts -- main identifier prior to introduction of ECLI
RS_SUBJECT = LI_LAW_AREA = 'domains'  # domain(s) (area(s) of the law) applicable to case
RS_HASVERSION = LI_SOURCES = 'alternative_publications'  # references to other publications
RS_IDENTIFIER2 = LI_ORIGINAL_URL = 'url_publication'  # URL to original document by publisher
RS_INHOUDSINDICATIE = LI_SUMMARY = 'summary'  # case summary
RS_TITLE = LI_TITLE = 'title'  # title of case
RS_FULL_TEXT = 'full_text'  # full text of case

# fields only in RS
RS_LANGUAGE = 'language'
RS_TYPE = 'document_type'  # 'uitspraak' (decision) or 'conclusie' (opinion)
RS_PROCEDURE = 'procedure_type'  # procedure type (e.g. summary proceedings)
RS_SPATIAL = 'jurisdiction_city'  # court location (municipality)
RS_RELATION = 'predecessor_successor_cases'  # predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc)
RS_REFERENCES = 'referenced_legislation_titles'  # title of applicable legislation
RS_INFO = 'info'  # information about case, often not systematic or already captured in other fields
ECLI_DECISION = 'ecli_decision'  # ecli of case decision corresponding to case opinion

# fields only in LI
LI_ID = 'document_id'  # internal document id in LI
LI_DISPLAY_TITLE = 'display_title'  # title of document entry in LI
LI_DISPLAY_SUBTITLE = 'display_subtitle'  # subtitle of document entry in LI
LI_URL = 'url_entry'  # URL to LI entry of document
LI_PUBLICATION_NUMBER = 'publication_number'  # internal document id of publisher
LI_ISSUE_NUMBER = 'issue_number'  # collection id of publisher
LI_DATE_ADDED = 'date_added'  # date of document added to the LI platform

# fields only in LIDO
LIDO_ECLI = 'source_ecli'  # @TODO before re run pipeline change to: ECLI
LIDO_JURISPRUDENTIE = 'target_ecli'  # @TODO before re run pipeline change to: 'target_ecli'  # cited case ecli
LIDO_WET = 'target_article'  # @TODO before re run pipeline change to: 'target_legislation_url'  # URL to cited legislation
LIDO_ARTIKEL = 'target_article_webpage'  # @TODO before re run pipeline change to: 'target_legislation_article_url'  # URL to cited legislation article