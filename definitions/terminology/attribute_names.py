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

# fields only in ECHR
<<<<<<< HEAD
ECHR_CITATIONS = 'citations'  # list of citations by title
ECHR_APPLICANTS = 'applicants'  # applicats by number
ECHR_IMPORTANCE = 'importance'  # case importance
ECHR_PARTICIPANTS = 'participants'  # applicants extracted form the report indicating the existing of the full text
ECHR_CITATIONS = 'scl'  # the cases which are cited
ECHR_VIOLATIONS = 'violation'  # list of violated articles
ECHR_NON_VIOLATIONS = 'nonviolation'  # list of articles which were found not to have been violated
#ECHR_APPLICABILITY = 'applicability'
#ECHR_REPRESENTATION = 'representation'
#ECHR_RESPONDENT = 'respondent'
#ECHR_SEPARATE_OPINION = 'separate_opinion'
#ECHR_SHAREPOINT_ID = 'sharepointid'
<<<<<<< HEAD
=======
#ECHR_VIOLATIONS = 'violations'
#ECHR_NON_VIOLATIONS = 'non_violations'
>>>>>>> fc06f7546357193015790f3cbf0357c3fae7b69a
#ECHR_SOURCES = 'sources'
#ECHR_ISSUES = 'issues'
#ECHR_REFERENCE_DATE = 'reference_date'
#ECHR_RULES_OF_COURT = 'rules_of_court'
#ECHR_CITATIONS = 'citations'
#ECHR_DOCID = 'docid'
#ECHR_WORKID = 'workid'
#ECHR_RANK = 'rank'
#ECHR_AUTHOR = 'author'
#ECHR_SIZE = 'size'
#ECHR_PATH = 'path'
#ECHR_DESCRIPTION = 'desctiption'
#ECHR_WRITE = 'write'
#ECHR_COLLAPSINGSTATUS = 'collapsingstatus'
#ECHR_HIGHLIGHTEDSUMMARY = 'highlightedsummary'
#ECHR_HIGHLIGHTEDPROPERTIES = 'highlightedproperties'
#ECHR_CONTENTCLASS = 'contentclass'
#ECHR_PICTURETHUMBNAIL = 'picturethumbnail'
#ECHR_SERVERREDIRECTEDURL = 'serverredirectedurl'
#ECHR_SERVERREDIRECTEDEMBEDURL = 'serverredirectedembedurl'
#ECHR_SERVERREDIRECTEDPREVIEWURL = 'serverredirectedpreviewurl'
#ECHR_FILEEXTENSION = 'fileextension'
#ECHR_CONTENTTYPEID = 'contenttypeid'
#ECHR_PARENTLINK = 'parentlink'
#ECHR_VIEWSLIFETIME = 'viewslifetime'
#ECHR_VIEWSRECENT = 'viewsrecent'
#ECHR_SECTIONNAMES = 'sectionnames'
#ECHR_SECTIONINDEXES = 'sectionindexes'
#ECHR_SITELOGO = 'sitelogo'
#ECHR_SITEDESCRIPTION = 'sitedescription'
#ECHR_DEEPLINKS = 'deeplinks'
#ECHR_SITENAME = 'sitename'
#ECHR_ISDOCUMENT = 'isdocument'
#ECHR_LASTMODIFIEDTIME = 'lastmodifiedtime'
#ECHR_FILETYPE = 'filetype'
#ECHR_ISCONTAINER = 'iscontainer'
#ECHR_WEBTEMPLATE = 'webtemplate'
#ECHR_SECONDARYFILEEXTENSION = 'secondaryfileextension'
#ECHR_DOCACLMETA = 'docaclmeta'
#ECHR_ORIGINALPATH = 'originalpath'
#ECHR_EDITOROWSUSER = 'editorowsuser'
#ECHR_DISPLAYAUTHOR = 'displayauthor'
#ECHR_RESULTTYPEIDLIST = 'resulttypeidlist'
#ECHR_PARTITIONID = 'partitionid'
#ECHR_URLZONE = 'urlzone'
#ECHR_AAMENABLEDMANAGEDPROPERTIES = 'aamenabledmanagedproperties'
#ECHR_RESULTTYPEID = 'resulttypeid'
#ECHR_RENDERTEMPLATEID = 'rendertemplateid'
