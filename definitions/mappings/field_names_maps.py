from definitions.terminology.field_names import *

# maps to rename original field names of raw data to terminology defined in definitions.py
# (no need to change: changes automatically if definitions.py changes):
MAP_RS = {
    'identifier': RS_IDENTIFIER,  # ECLI (European Case Law Identifier) -- unique identifier for court decisions in Europe
    'issued': RS_ISSUED,  # date of document publication (on Rechtspraak.nl)
    'language': RS_LANGUAGE,  # language of jurisdiction to which case belongs
    'creator': RS_CREATOR,  # name of instance (court)
    'date': RS_DATE,  # date of court decision
    'zaaknummer': RS_ZAAKNUMMER,  # case number, for internal use by courts -- main identifier prior to introduction of ECLI
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
    'Sources': LI_SOURCES  # alternative publishing institutions
}

MAP_CASE_CITATIONS = {
    'ecli': ECLI,  # citing case ecli
    'Jurisprudentie': LIDO_JURISPRUDENTIE,  # cited case ecli
}

MAP_LEGISLATION_CITATIONS = {
    'ecli': ECLI,  # citing case ecli
    'Wet': LIDO_WET,  # URL to cited legislation
    'Artikel': LIDO_ARTIKEL  # URL to cited legislation article
}