"""
The final set of attribute names to be used.
Original RS terminology: see example_Rechtspraak.xml tags
Original LI terminology: see https://www.legalintelligence.com/files/li-search-endpoint.pdf
"""

# corresponding fields in RS, LI, and ECHR (change here if you want to remap fields):
ECLI = RS_IDENTIFIER = ECHR_ECLI = 'ecli' # ECLI (European Case Law Identifier) -- unique identifier for court decisions in Europe
SOURCE = LI_DOCUMENT_TYPE = ECHR_DOCUMENT_TYPE = 'source'  # source of case (so far: always 'Rechtspraak')
RS_CREATOR = LI_ISSUING_INSTITUTION = ECHR_DIVISION = 'instance'  # name of instance (court)
RS_DATE = LI_ENACTMENT_DATE = ECHR_JUDGEMENT_DATE = 'date_decision'  # date of court decision
RS_SUBJECT = LI_LAW_AREA = ECHR_ARTICLES = 'domains'  # domain(s) (area(s) of the law) applicable to case
RS_HASVERSION = LI_SOURCES = ECHR_PUBLISHED_BY = 'alternative_publications'  # references to other publications
RS_INHOUDSINDICATIE = LI_SUMMARY = ECHR_CONCLUSION = 'summary'  # case summary
RS_TITLE = LI_TITLE = ECHR_TITLE = 'title'  # title of case

# corresponding fields in RS and LI (change here if you want to remap fields):
JURISDICTION_COUNTRY = LI_JURISDICTION = 'jurisdiction_country'  # country of jurisdiction (so far: always 'NL')
RS_ISSUED = LI_PUBLICATION_DATE = 'date_publication'  # date of document publication
RS_ZAAKNUMMER = LI_CASE_NUMBER = 'case_number'  # case number, for internal use by courts -- main identifier prior to introduction of ECLI
RS_IDENTIFIER2 = LI_ORIGINAL_URL = 'url_publication'  # URL to original document by publisher
RS_FULL_TEXT = 'full_text'  # full text of case

# corresponding fields in RS and ECHR (change here if you want to remap fields)
RS_TYPE = ECHR_BRANCH = 'document_type'  # 'uitspraak' (decision) or 'conclusie' (opinion)
RS_LANGUAGE = ECHR_LANGUAGE = 'language'
RS_REFERENCES = ECHR_APPLICABLE_ARTICLES = 'referenced_legislation_titles'  # title of applicable legislation

# corresponding fields in LI and ECHR (change here if you want to remap fields)
LI_ID = ECHR_DOCUMENT_ID = 'document_id'  # internal document id in LI

# fields only in RS
RS_PROCEDURE = 'procedure_type'  # procedure type (e.g. summary proceedings)
RS_SPATIAL = 'jurisdiction_city'  # court location (municipality)
RS_RELATION = 'predecessor_successor_cases'  # predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc)
RS_INFO = 'info'  # information about case, often not systematic or already captured in other fields
ECLI_DECISION = 'ecli_decision'  # ecli of case decision corresponding to case opinion
ECLI_OPINION = 'ecli_opinion'  # ecli of case opinion corresponding to case decision

# fields only in LI
LI_DISPLAY_TITLE = 'display_title'  # title of document entry in LI
LI_DISPLAY_SUBTITLE = 'display_subtitle'  # subtitle of document entry in LI
LI_URL = 'url_entry'  # URL to LI entry of document
LI_PUBLICATION_NUMBER = 'publication_number'  # internal document id of publisher
LI_ISSUE_NUMBER = 'issue_number'  # collection id of publisher
LI_DATE_ADDED = 'date_added'  # date of document added to the LI platform
LI_SEARCH_NUMBERS = 'search_numbers'  # @TODO what is this?

# fields only in LIDO
LIDO_JURISPRUDENTIE = 'target_ecli'  # cited case ecli
LIDO_LABEL = 'label'  # descriptive type of citation (conclusie, appeal, cassatie, ...)
LIDO_TYPE = 'type'  # type id of citation as given in the linktype URL
LIDO_WET = 'legal_provision_url_lido'  # URL to lido entry of cited legislation
LIDO_ARTIKEL = 'legal_provision_url'  # URL to cited legislation (on wetten.nl)
LIDO_ARTIKEL_TITLE = 'legal_provision'  # title of cited legislation
