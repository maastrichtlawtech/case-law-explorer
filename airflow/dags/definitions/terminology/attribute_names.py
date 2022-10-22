"""
The final set of attribute names to be used.
Original RS terminology: see example_Rechtspraak.xml tags
Original LI terminology: see https://www.legalintelligence.com/files/li-search-endpoint.pdf
"""

# corresponding fields in RS and LI  and ECHR (change here if you want to remap fields):
SOURCE = LI_DOCUMENT_TYPE = ECHR_DOCUMENT_TYPE = 'source'  # source of case (so far: always 'Rechtspraak')
JURISDICTION_COUNTRY = LI_JURISDICTION = 'jurisdiction_country'  # country of jurisdiction (so far: always 'NL')
RS_CREATOR = LI_ISSUING_INSTITUTION = ECHR_DIVISION = 'instance'  # name of instance (court)
RS_DATE = LI_ENACTMENT_DATE = ECHR_JUDGEMENT_DATE =  'date_decision'  # date of court decision
RS_ZAAKNUMMER = LI_CASE_NUMBER = 'case_number'  # case number, for internal use by courts -- main identifier prior to introduction of ECLI
RS_SUBJECT = LI_LAW_AREA = ECHR_ARTICLES =  'domains'  # domain(s) (area(s) of the law) applicable to case
RS_HASVERSION = LI_SOURCES = ECHR_PUBLISHED_BY = 'alternative_publications'  # references to other publications
RS_IDENTIFIER2 = LI_ORIGINAL_URL = 'url_publication'  # URL to original document by publisher
RS_TITLE = LI_TITLE = ECHR_TITLE = 'title'  # title of case


# fields in RS and LI and CELLAR and ECHR at this point i dont know
RS_ISSUED = LI_PUBLICATION_DATE = CELLAR_DATE_OF_DOCUMENT = 'date_publication'  # date of document publication
RS_INHOUDSINDICATIE = LI_SUMMARY = CELLAR_SUMMARY = ECHR_CONCLUSION =   'summary'  # case summary
ECLI = RS_IDENTIFIER = 'ecli'  # ECLI (European Case Law Identifier) -- unique identifier for court decisions in Europe

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
RS_FULL_TEXT = 'full_text'  # full text of case

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

# fields only in CELLAR
CELLAR_COMMENTED_AGENT = 'commented_by_agent'  # which Member States submitted information
CELLAR_DIRECTORY_CODES = 'directory_codes'  # directory classification codes for case
CELLAR_SUBJECT_MATTER = 'subject_matter'  # subject matter of case
CELLAR_EUROVOC = 'eurovoc'  # eurovoc classification codes for the case
CELLAR_KEYWORDS = 'keywords'  # keywords for case
CELLAR_DELIVERED_COURT = 'delivered_by_court_formation'  # court (chamber) that delivered the judgment
CELLAR_JUDICIAL_TYPE = 'judicial_type_procedure'  # type of procedure with more info
CELLAR_TYPE_PROCEDURE = 'type_procedure'  # type of procedure
CELLAR_CONCLUSIONS = 'conclusions'  # opinion of the Advocate-General
CELLAR_LEGAL_RESOURCE = 'legal_resource'  # source that the case interprets
CELLAR_COUNTRY = 'origin_country'  # country of origin
CELLAR_COUNTRY_OR_ROLE = 'origin_country_or_role_qualifier'  # country of origin with more info
CELLAR_CELEX = 'celex'  # celex identifier
CELLAR_REQUEST_DATE = 'date_of_request'  # date of request for an opinion of Advocate-General
CELLAR_CREATION_OF_WORK = 'date_of_creation'  # date of latest modification in dataset
CELLAR_BASED_ON_TREATY = 'based_on_treaty'  # treaty on which judgment is based
CELLAR_NATIONAL_JUDGMENT = 'national_judgment'  # source of national case
CELLAR_JOURNAL_ARTICLES = 'references_journals'  # references to journal articles
CELLAR_SECTOR = 'sector'  # type of source
CELLAR_RESOURCE_TYPE = 'resource_type'  # document type
CELLAR_YEAR_OF_RESOURCE = 'judgment_year'  # judgment year
CELLAR_LANGUAGE = 'language_procedure'  # language of procedure
CELLAR_CITED_BY = 'cited_by'   # works citing the work
CELLAR_CITING = 'citing'   # works cited in work
CELLAR_CITATIONS='citations' # all work cited and works citing the work

# fields only in ECHR
ECHR_CITATIONS = 'citations' # list of citations by title
ECHR_APPLICANTS = 'applicants' # applicats by number
ECHR_IMPORTANCE = 'importance' # case importance
ECHR_PARTICIPANTS = 'participants' # applicants extracted form the report indicating the existing of the full text