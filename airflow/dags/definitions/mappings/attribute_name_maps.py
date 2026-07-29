from definitions.terminology.attribute_names import *

# maps to rename original field names of raw data to terminology defined in definitions.py
# (no need to change: changes automatically if definitions.py changes):
MAP_RS = {
    "ecli": RS_IDENTIFIER,
    # originally: 'identifier'. ECLI (European Case Law Identifier) -- unique identifier for court decisions in Europe
    "issued": RS_ISSUED,  # date of document publication (on Rechtspraak.nl)
    "language": RS_LANGUAGE,  # language of jurisdiction to which case belongs
    "creator": RS_CREATOR,  # name of instance (court)
    "date_decision": RS_DATE,  # originally: 'date'. Date of court decision
    "zaaknummer": RS_ZAAKNUMMER,
    # case number, for iternal use by courts -- main identifier prior to introduction of ECLI
    "type": RS_TYPE,  # 'uitspraak' (decision) or 'conclusie' (opinion)
    "procedure": RS_PROCEDURE,  # procedure type (e.g. summary proceedings)
    "spatial": RS_SPATIAL,  # court location (municipality)
    "subject": RS_SUBJECT,  # domain (area of the law) applicable to case
    "relation": RS_RELATION,
    # predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc)
    "references": RS_REFERENCES,  # title of applicable legislation
    "hasVersion": RS_HASVERSION,  # alternative publishing institutions
    "link": RS_IDENTIFIER2,
    # URL (deeplink) to case as published on Rechtspraak.nl (original tag name: 'identifier' -- section 2)
    "title": RS_TITLE,  # title of case
    "inhoudsindicatie": RS_INHOUDSINDICATIE,  # case summary
    "info": RS_INFO,
    # information about case, often not systematic or already captured in other fields (original tag name: either 'uitspraak.info or 'conclusie.info')
    "full_text": RS_FULL_TEXT,  # full text of case (original tag name: either 'uitspraak' or 'conclusie')
    JURISDICTION_COUNTRY: JURISDICTION_COUNTRY,  # not in original data, added through script
    SOURCE: SOURCE,  # not in original data, added through script
    "citations_incoming": RS_CITED_BY,  # cases citing current case
    "citations_outgoing": RS_CITING,  # cases cited in current case
    "legislations_cited": RS_LEGISLATIONS,  # legislations cited in current case
    "summary": RS_SUMMARY,
    "bwb_id": RS_BWB_ID,
}
MAP_CELLAR = {
    # cellar-extractor 2.x emits its canonical schema directly, so this is a
    # selection rather than a rename: the keys are the columns the extractor
    # produces and the values are what the rest of this pipeline calls them.
    #
    # Until 2.0 the keys were the raw CDM predicate labels the SPARQL query
    # returned ("CELEX IDENTIFIER", "WORK HAS RESOURCE TYPE", and so on). The
    # transformer only copies a column when its name is a key here, so against
    # 2.x not one of them matched and every output row came out with the right
    # headers and no values. It failed as an empty load rather than as an error,
    # which is the reason to be exact about this map rather than approximately
    # right.
    "commented_by_agent": CELLAR_COMMENTED_AGENT,  # which Member States submitted information
    "directory_codes": CELLAR_DIRECTORY_CODES,  # directory classification codes for case
    "eurovoc": CELLAR_EUROVOC,  # eurovoc classification codes for case
    "keywords": CELLAR_KEYWORDS,  # keywords of case
    "summary": CELLAR_SUMMARY,  # summary of case
    # 2.x reports the two directions separately; there is no combined column.
    "citing": CELLAR_CITING,  # works this work cites
    "cited_by": CELLAR_CITED_BY,  # works citing this work
    "delivered_by_court_formation": CELLAR_DELIVERED_COURT,  # court (chamber) that delivered the judgment
    "judicial_procedure_type": CELLAR_JUDICIAL_TYPE,  # type of procedure
    "type_procedure": CELLAR_TYPE_PROCEDURE,  # type of procedure with more info
    "conclusions": CELLAR_CONCLUSIONS,  # opinion of the Advocate-General
    "legal_resource": CELLAR_LEGAL_RESOURCE,  # the source that the case interprets
    "origin_country": CELLAR_COUNTRY,  # country of judgment
    "origin_country_or_role_qualifier": CELLAR_COUNTRY_OR_ROLE,  # country of origin with more information
    "celex": CELLAR_CELEX,  # celex identifier
    "date_publication": CELLAR_DATE_OF_DOCUMENT,  # date of document
    "date_of_request": CELLAR_REQUEST_DATE,  # date of request for an opinion of the Advocate-General
    "ecli": ECLI,  # European Case Law Identifier
    "date_of_creation": CELLAR_CREATION_OF_WORK,  # date of latest modification in dataset
    "based_on_treaty": CELLAR_BASED_ON_TREATY,  # treaty on which judgment is based
    "subject_matter": CELLAR_SUBJECT_MATTER,  # subject matter
    "national_judgement": CELLAR_NATIONAL_JUDGMENT,  # source of national case
    "references_journals": CELLAR_JOURNAL_ARTICLES,  # references to journal articles
    "sector": CELLAR_SECTOR,  # indicates type of source
    "resource_type": CELLAR_RESOURCE_TYPE,  # document type
    "year_of_resource": CELLAR_YEAR_OF_RESOURCE,  # judgment year
    "language_procedure": CELLAR_LANGUAGE,  # language of procedure
    "advocate_general": CELLAR_ADV_GENERAL,  # Advocate General of the case
    "judge_rapporteur": CELLAR_JUDGE_RAPPORTEUR,  # Judge Rapporteur of the case
    "affecting_ids": CELLAR_AFFECTING_ID,  # cellar ids of the case affecting
    # Singular in 2.x; it was affecting_strings before.
    "affecting_string": CELLAR_AFFECTING_STRING,  # strings with more detail about case affecting
    "citations_extra_info": CELLAR_CITATIONS_EXTRA_INFO,  # citations with exact paragraphs cited
}

MAP_RS_OPINION = MAP_RS.copy()
MAP_RS_OPINION[ECLI_DECISION] = ECLI_DECISION  # not in original data, added through script

MAP_ECHR = {
    "itemid": ECHR_DOCUMENT_ID,  # unique document identifier
    "applicability": ECHR_APPLICABLE_ARTICLES,  # which articles are applicable
    "appno": ECHR_APPLICANTS,  # applicant numbers (could be of use)
    "article": ECHR_ARTICLES,  # alleged violated articles
    "conclusion": ECHR_CONCLUSION,  # violated/Non-violated articles
    "docname": ECHR_TITLE,  # name of the case
    "doctype": ECHR_DOCUMENT_TYPE,  # type of document
    "doctypebranch": ECHR_BRANCH,  # branch of court
    "ecli": ECLI,  # European Case Law Identifier
    "importance": ECHR_IMPORTANCE,  # case importance from 1 (least) to 4 (most)
    "judgementdate": ECHR_JUDGMENT_DATE,  # date and time of judgement
    "languageisocode": ECHR_LANGUAGE,  # language of document
    "originatingbody": ECHR_DIVISION,  # division of court
    "representedby": ECHR_REPRESENTATION,  # representation of the case (could be of use)
    "respondent": ECHR_RESPONDENT,  # defender of the case (could be of use)
    "separateopinion": ECHR_SEPARATE_OPINION,  # presence of concurring or dissenting opinions (could be of use)
    "sharepointid": ECHR_SHAREPOINT_ID,  # identifier for microsoft sharepoint (could be of use)
    "violation": ECHR_VIOLATIONS,  # violated articles (could be of use)
    "nonviolation": ECHR_NON_VIOLATIONS,  # unsure what this is, always empty (could be of use)
    "publishedby": ECHR_PUBLISHED_BY,  # publications which contain the case
    "externalsources": ECHR_SOURCES,  # relevent international acts or previous outcomes (could be of use)
    "extractedappno": ECHR_PARTICIPANTS,  # applicant numbers of all applicants mentioned in the case (could be of use)
    # 'issue': ECHR_ISSUES,  # domestic laws in questions
    # 'referencedate': ECHR_REFERENCE_DATE,  # date and time that the case was referred to the ECHR (could be of use)
    # 'rulesofcourt': ECHR_RULES_OF_COURT,  # rules of court which needed to be invoked (could be of use)
    "scl": ECHR_CITATIONS,  # Strasburg case law citations
    "DocId": ECHR_DOCID,
    "WorkId": ECHR_WORKID,
    # 'Rank': ECHR_RANK,
    "Author": ECHR_AUTHOR,
    # 'Size': ECHR_SIZE,
    "Path": ECHR_PATH,
    "Description": ECHR_DESCRIPTION,
    # 'Write': ECHR_WRITE,
    # 'CollapsingStatus': ECHR_COLLAPSINGSTATUS,
    # 'HighlightedSummary': ECHR_HIGHLIGHTEDSUMMARY,
    # 'HighlightedProperties': ECHR_HIGHLIGHTEDPROPERTIES,
    # 'contentclass': ECHR_CONTENTCLASS,
    # 'PictureThumbnailURL': ECHR_PICTURETHUMBNAIL,
    # 'ServerRedirectedURL': ECHR_SERVERREDIRECTEDURL,
    # 'ServerRedirectedEmbedURL': ECHR_SERVERREDIRECTEDEMBEDURL,
    # 'ServerRedirectedPreviewURL': ECHR_SERVERREDIRECTEDPREVIEWURL,
    # 'FileExtension': ECHR_FILEEXTENSION,
    # 'ContentTypeId': ECHR_CONTENTTYPEID,
    # 'ParentLink': ECHR_PARENTLINK,
    # 'ViewsLifeTime': ECHR_VIEWSLIFETIME,
    # 'ViewsRecent': ECHR_VIEWSRECENT,
    # 'SectionNames': ECHR_SECTIONNAMES,
    # 'SectionIndexes': ECHR_SECTIONINDEXES,
    # 'SiteLogo': ECHR_SITELOGO,
    # 'SiteDescription': ECHR_SITEDESCRIPTION,
    # 'deeplinks': ECHR_DEEPLINKS,
    # 'SiteName': ECHR_SITENAME,
    # 'IsDocument': ECHR_ISDOCUMENT,
    # 'LastModifiedTime': ECHR_LASTMODIFIEDTIME,
    # 'FileType': ECHR_FILETYPE,
    # 'IsContainer': ECHR_ISCONTAINER,
    # 'WebTemplate': ECHR_WEBTEMPLATE,
    # 'SecondaryFileExtension': ECHR_SECONDARYFILEEXTENSION,
    # 'docaclmeta': ECHR_DOCACLMETA,
    # 'OriginalPath': ECHR_ORIGINALPATH,
    # 'EditorOWSUSER': ECHR_EDITOROWSUSER,
    # 'DisplayAuthor': ECHR_DISPLAYAUTHOR,
    # 'ResultTypeIdList': ECHR_RESULTTYPEIDLIST,
    # 'PartitionId': ECHR_PARTITIONID,
    # 'UrlZone': ECHR_URLZONE,
    # 'AAMEnabledManagedProperties': ECHR_AAMENABLEDMANAGEDPROPERTIES,
    # 'ResultTypeId': ECHR_RESULTTYPEID,
    # 'rendertemplateid': ECHR_RENDERTEMPLATEID
}
