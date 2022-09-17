from airflow_folder.dags.definitions.terminology.attribute_names import *

# maps to rename original field names of raw data to terminology defined in definitions.py
# (no need to change: changes automatically if definitions.py changes):
MAP_RS = {
    'ecli': RS_IDENTIFIER,  # originally: 'identifier'. ECLI (European Case Law Identifier) -- unique identifier for court decisions in Europe
    'issued': RS_ISSUED,  # date of document publication (on Rechtspraak.nl)
    'language': RS_LANGUAGE,  # language of jurisdiction to which case belongs
    'creator': RS_CREATOR,  # name of instance (court)
    'date_decision': RS_DATE,  # originally: 'date'. Date of court decision
    'zaaknummer': RS_ZAAKNUMMER,  # case number, for iternal use by courts -- main identifier prior to introduction of ECLI
    'type': RS_TYPE,  # 'uitspraak' (decision) or 'conclusie' (opinion)
    'procedure': RS_PROCEDURE,  # procedure type (e.g. summary proceedings)
    'spatial': RS_SPATIAL,  # court location (municipality)
    'subject': RS_SUBJECT,  # domain (area of the law) applicable to case
    'relation': RS_RELATION,  # predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc)
    'references': RS_REFERENCES,  # title of applicable legislation
    'hasVersion': RS_HASVERSION,  # alternative publishing institutions
    'identifier2': RS_IDENTIFIER2,  # URL (deeplink) to case as published on Rechtspraak.nl (original tag name: 'identifier' -- section 2)
    'title': RS_TITLE,  # title of case
    'inhoudsindicatie': RS_INHOUDSINDICATIE,  # case summary
    'info': RS_INFO,  # information about case, often not systematic or already captured in other fields (original tag name: either 'uitspraak.info or 'conclusie.info')
    'full_text': RS_FULL_TEXT,  # full text of case (original tag name: either 'uitspraak' or 'conclusie')
    JURISDICTION_COUNTRY: JURISDICTION_COUNTRY,  # not in original data, added through script
    SOURCE: SOURCE  # not in original data, added through script
}
MAP_CELLAR = {
    'CASE LAW COMMENTED BY AGENT': CELLAR_COMMENTED_AGENT,  # which Member States submitted information
    'celex_directory_codes': CELLAR_DIRECTORY_CODES,  # directory classification codes for case
    'celex_subject_matter': CELLAR_SUBJECT_MATTER,  # subject matter
    'celex_eurovoc': CELLAR_EUROVOC,  # eurovoc classification codes for case
    'celex_keywords': CELLAR_KEYWORDS,  # keywords of case
    'celex_summary': CELLAR_SUMMARY,  # summary of case
    'WORK CITES WORK. CI / CJ':   CELLAR_CITATIONS,    # works cites by this work, works this work cites
    'CASE LAW DELIVERED BY COURT FORMATION': CELLAR_DELIVERED_COURT,  # court (chamber) that delivered the judgment
    'CASE LAW HAS A JUDICIAL PROCEDURE TYPE': CELLAR_JUDICIAL_TYPE ,  # type of procedure
    'CASE LAW HAS A TYPE OF PROCEDURE': CELLAR_TYPE_PROCEDURE,  # type of procedure with more info
    'CASE LAW HAS CONCLUSIONS': CELLAR_CONCLUSIONS,  # opinion of the Advocate-General
    'CASE LAW INTERPRETS LEGAL RESOURCE': CELLAR_LEGAL_RESOURCE,  # the source that the case interprets
    'CASE LAW ORIGINATES IN COUNTRY': CELLAR_COUNTRY,  # country of judgment
    'CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER': CELLAR_COUNTRY_OR_ROLE,  # country of origin with more information
    'CELEX IDENTIFIER': CELLAR_CELEX,   # celex identifier
    'DATE OF DOCUMENT': CELLAR_DATE_OF_DOCUMENT,  # date of document
    'DATE OF REQUEST FOR AN OPINION': CELLAR_REQUEST_DATE,  #date of request for on opinion of the Advocate-General
    'ECLI': ECLI,  # European Case Law Identifier
    'LEGACY DATE OF CREATION OF WORK': CELLAR_CREATION_OF_WORK,  # date of latest modification in dataset
    'LEGAL RESOURCE BASED ON TREATY CONCEPT': CELLAR_BASED_ON_TREATY,  # treaty on which judgment is based
    'LEGAL RESOURCE IS ABOUT SUBJECT MATTER': CELLAR_SUBJECT_MATTER,  # subject matter
    'NATIONAL JUDGEMENT': CELLAR_NATIONAL_JUDGMENT,  #source of national case
    'RELATED JOURNAL ARTICLE': CELLAR_JOURNAL_ARTICLES,  # references to journal articles
    'SECTOR IDENTIFIER': CELLAR_SECTOR,  # indicates type of source
    'WORK HAS RESOURCE TYPE': CELLAR_RESOURCE_TYPE,  # document type
    'YEAR OF THE LEGAL RESOURCE': CELLAR_YEAR_OF_RESOURCE,  # judgment year
    'CASE LAW USES LANGUAGE OF PROCEDURE' : CELLAR_LANGUAGE  # language of procedure

}
MAP_RS_OPINION = MAP_RS.copy()
MAP_RS_OPINION[ECLI_DECISION] = ECLI_DECISION  # not in original data, added through script

# Legal Intelligence provides additional information to cases.
# It contains a collection of (all/multiple) versions of a case from different publishers.
# original field names of LI can be found here: https://www.legalintelligence.com/files/li-search-endpoint.pdf
MAP_LI = {
    ECLI: ECLI,  # not in original data, added through script
    'Id': LI_ID,  # internal document id in LI
    'Title': LI_TITLE,  # title of original document
    'DisplayTitle': LI_DISPLAY_TITLE,  # title of document entry in LI
    'DisplaySubtitle': LI_DISPLAY_SUBTITLE,  # subtitle of document entry in LI
    'Summary': LI_SUMMARY,  # case summary
    'Url': LI_URL,  # URL to LI entry of document
    'OriginalUrl': LI_ORIGINAL_URL,  # URL to original document by publisher
    'Jurisdiction': LI_JURISDICTION,  # country of jurisdiction
    'DocumentType': LI_DOCUMENT_TYPE,  # source of case (here: always 'Rechtspraak')
    'LawArea': LI_LAW_AREA,  # domain(s) (area(s) of the law) applicable to case
    'IssuingInstitution': LI_ISSUING_INSTITUTION,  # name of instance (court)
    'CaseNumber': LI_CASE_NUMBER,  # unique case identifier (ECLI or previous format)
    'PublicationNumber': LI_PUBLICATION_NUMBER,  # internal document id of publisher
    'IssueNumber': LI_ISSUE_NUMBER,  # collection id of publisher
    'PublicationDate': LI_PUBLICATION_DATE,  # date of document publication (by publisher)
    'EnactmentDate': LI_ENACTMENT_DATE,  # date of court decision
    'DateAdded': LI_DATE_ADDED,  # date of document added to the LI platform
    'Sources': LI_SOURCES,  # alternative publishing institutions
    'SearchNumbers': LI_SEARCH_NUMBERS  # @ TODO: what is this?
}
