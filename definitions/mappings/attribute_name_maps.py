from definitions.terminology.attribute_names import *

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

MAP_ECHR = {
    'itemid': ECHR_DOCUMENT_ID,  # unique document identifier
#   'applicability': ECHR_APPLICABLE_ARTICLES,  # which articles are applicable
    'appno': ECHR_APPLICANTS,  # applicant numbers (could be of use)
    'article': ECHR_ARTICLES,  # alleged violated articles
    'conclusion': ECHR_CONCLUSION,  # violated/Non-violated articles
    'docname': ECHR_TITLE,  # name of the case
    'doctype': ECHR_DOCUMENT_TYPE,  # type of document
    'doctypebranch': ECHR_BRANCH,  # branch of court
    'ecli': ECHR_ECLI,  # European Case Law Identifier
    'importance': ECHR_IMPORTANCE,  # case importance from 1 (least) to 4 (most)
    'judgementdate': ECHR_JUDGEMENT_DATE,  # date and time of judgement
    'languageisocode': ECHR_LANGUAGE,  # language of document
    'originatingbody': ECHR_DIVISION,  # division of court
    'violation': ECHR_VIOLATIONS,  # violated articles
    'nonviolation': ECHR_NON_VIOLATIONS,  # articles which were found not to have been violated
    'extractedappno': ECHR_PARTICIPANTS,  # applicant numbers of all applicants mentioned in the case
    'scl': ECHR_CITATIONS,  # Strasburg case law citations
#   'publishedby': ECHR_PUBLISHED_BY,  # publications which contain the case
#   'representedby': ECHR_REPRESENTATION,  # representation of the case (could be of use)
#   'respondent': ECHR_RESPONDENT,  # defender of the case (could be of use)
#   'separateopinion': ECHR_SEPARATE_OPINION,  # presence of concurring or dissenting opinions (could be of use)
#   'sharepointid': ECHR_SHAREPOINT_ID,  # identifier for microsoft sharepoint (could be of use)
#   'externalsources': ECHR_SOURCES,  # relevent international acts or previous outcomes (could be of use)
#   'issue': ECHR_ISSUES,  # domestic laws in questions
#   'referencedate': ECHR_REFERENCE_DATE,  # date and time that the case was referred to the ECHR (could be of use)
#   'rulesofcourt': ECHR_RULES_OF_COURT,  # rules of court which needed to be invoked (could be of use)
#   'DocId': ECHR_DOCID,
#   'WorkId': ECHR_WORKID,
#   'Rank': ECHR_RANK,
#   'Author': ECHR_AUTHOR,
#   'Size': ECHR_SIZE,
#   'Path': ECHR_PATH, 
#   'Description': ECHR_DESCRIPTION,
#   'Write': ECHR_WRITE,
#   'CollapsingStatus': ECHR_COLLAPSINGSTATUS,
#   'HighlightedSummary': ECHR_HIGHLIGHTEDSUMMARY,
#   'HighlightedProperties': ECHR_HIGHLIGHTEDPROPERTIES,
#   'contentclass': ECHR_CONTENTCLASS,
#   'PictureThumbnailURL': ECHR_PICTURETHUMBNAIL,
#   'ServerRedirectedURL': ECHR_SERVERREDIRECTEDURL,
#   'ServerRedirectedEmbedURL': ECHR_SERVERREDIRECTEDEMBEDURL,
#   'ServerRedirectedPreviewURL': ECHR_SERVERREDIRECTEDPREVIEWURL,
#   'FileExtension': ECHR_FILEEXTENSION,
#   'ContentTypeId': ECHR_CONTENTTYPEID,
#   'ParentLink': ECHR_PARENTLINK,
#   'ViewsLifeTime': ECHR_VIEWSLIFETIME,
#   'ViewsRecent': ECHR_VIEWSRECENT,
#   'SectionNames': ECHR_SECTIONNAMES,
#   'SectionIndexes': ECHR_SECTIONINDEXES,
#   'SiteLogo': ECHR_SITELOGO,
#   'SiteDescription': ECHR_SITEDESCRIPTION,
#   'deeplinks': ECHR_DEEPLINKS,
#   'SiteName': ECHR_SITENAME,
#   'IsDocument': ECHR_ISDOCUMENT,
#   'LastModifiedTime': ECHR_LASTMODIFIEDTIME, 
#   'FileType': ECHR_FILETYPE, 
#   'IsContainer': ECHR_ISCONTAINER,
#   'WebTemplate': ECHR_WEBTEMPLATE,
#   'SecondaryFileExtension': ECHR_SECONDARYFILEEXTENSION,
#   'docaclmeta': ECHR_DOCACLMETA,
#   'OriginalPath': ECHR_ORIGINALPATH,
#   'EditorOWSUSER': ECHR_EDITOROWSUSER,
#   'DisplayAuthor': ECHR_DISPLAYAUTHOR,
#   'ResultTypeIdList': ECHR_RESULTTYPEIDLIST,
#   'PartitionId': ECHR_PARTITIONID,
#   'UrlZone': ECHR_URLZONE,
#   'AAMEnabledManagedProperties': ECHR_AAMENABLEDMANAGEDPROPERTIES,
#   'ResultTypeId': ECHR_RESULTTYPEID,
#   'rendertemplateid': ECHR_RENDERTEMPLATEID
}
