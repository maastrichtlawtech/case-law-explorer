# Datasets

The Case Law Explorer holds two types of data: 

- **Case decisions and opinions**: The full text and meta information of a case, identified by its ECLI number.
- **Case citations**: The link between a case and the cases cited in its decision, identified by the ECLI numbers of the source case and the target case.

Currently, the Case Law Explorer comprises the case law of the Netherlands and that of two European courts. We plan to extend the data to other international courts.

## Dutch courts

The Dutch case law is collected from different sources.

### Rechtspraak archive

[De Rechtspraak](https://www.rechtspraak.nl/) is a public platform which provides the full texts and meta information of all published Dutch cases. Each case is represented in XML format and the whole collection can be downloaded as a `.zip` archive.

#### Access
Access to the platform and the archive is open.

#### Sources

- Website: https://www.rechtspraak.nl/
- Documentation: https://www.rechtspraak.nl/Uitspraken/paginas/open-data.aspx
- Original archive: http://static.rechtspraak.nl/PI/OpenDataUitspraken.zip ~5GB
- Sample (~1k cases): https://surfdrive.surf.nl/files/index.php/s/zvrWcsriC5PU9xx ~2MB

#### Data format

The following tags are currently extracted from the XML files:

| Name                          | Format                             | Definition                                                                                |
|:------------------------------|:-----------------------------------|:------------------------------------------------------------------------------------------|
| ECLI                          | String                             | ECLI (European Case Law Identifier): unique identifier for court decisions in Europe      |
| date_publication              | String / yyyy-mm-dd                | Date of document publication                                                              |
| language                      | String / "nl"                      | Language of jurisdiction to which case belongs                                            |
| instance                      | String                             | Name of instance (court)                                                                  |
| jurisdiction_city             | String                             | Court location (municipality)                                                             |
| date_decision                 | String / yyyy-mm-dd                | Date of court decision                                                                    |
| case_number                   | String                             | Case number, for internal use by courts (main identifier prior to introduction of ECLI)   |
| document_type                 | String / "uitspraak" / "conclusie" | Document type: decision/opinion                                                           |
| procedure_type                | String[]                           | Procedure type (e.g. summary proceedings)                                                 |
| domains                       | String / "domain; subdomain"       | Domain (area of the law) applicable to case                                               |
| referenced_legislation_titles | String[]                           | Title of applicable legislation                                                           |
| alternative_publications      | String[]                           | References to other publications                                                          |
| title                         | String                             | Title of case                                                                             |                                                                        |
| full_text                     | String                             | Full text of case decision/opinion                                                        |
| summary                       | String                             | Summary of case                                                                           |
| citing                        | String                             | Cases cited by the case                                                                   |
| cited_by                      | String                             | Cases citing the case                                                                     |
| legislations_cited            | String                             | Legislations cited by case                                                                |                                                             |
| predecessor_successor_cases   | String                             | Predecessor and successor cases                                                           |
| url_publications              | URL                                | URL (deeplink) to case as published on Rechtspraak.nl                                     |
| info                          | String                             | Information                                                                               |
| source                        | String                             | Source of data                                                                            |


## European courts

We are making efforts to include in our project European and international courts as well. So far we are working to add this European courts to our codebase.

### European Court of Human Rights (ECHR)

The [ECHR](https://www.echr.coe.int/Pages/home.aspx?p=home) is dealing with cases alleging that a state has breached human rights agreed in the European Convention on Human Rights. The [HUDOC database](https://www.echr.coe.int/Pages/home.aspx?p=caselaw/HUDOC&c=) provides access to the caselaw of the ECHR.  

#### Sources

- Documentation: https://www.echr.coe.int/Documents/HUDOC_Manual_ENG.PDF
- HUDOC UI: https://hudoc.echr.coe.int/
- HUDOC Endpoint: 
 ```
 https://hudoc.echr.coe.int/app/query/results?query=(contentsitename=ECHR) AND (documentcollectionid2:"JUDGMENTS" OR documentcollectionid2:"COMMUNICATEDCASES")&select=itemid,applicability,application,appno,article,conclusion,decisiondate,docname,documentcollectionid, documentcollectionid2,doctype,doctypebranch,ecli,externalsources,extractedappno,importance,introductiondate, isplaceholder,issue,judgementdate,kpdate,kpdateAsText,kpthesaurus,languageisocode,meetingnumber, originatingbody,publishedby,Rank,referencedate,reportdate,representedby,resolutiondate, resolutionnumber,respondent,respondentOrderEng,rulesofcourt,separateopinion,scl,sharepointid,typedescription, nonviolation,violation&sort=itemid Ascending&start=0&length=2
 ```

#### Data format

The following fileds are expected to be found in the CSV files storing ECHR data:

| Name                          | Format  | Definition                                             |
|:------------------------------|:--------|:-------------------------------------------------------|
| document_id                   | String  | Unique identifier                                      |
| referenced_legislation_titles | String  | Titles of referenced legislations                      |
| applicants                    | String  |                                                        |
| domains                       | String  |                                                        |
| summary                       | String  | Summary of case                                        |
| title                         | String  | Title of case                                          |
| source                        | String  | Source of data of case (e.g. HEJUD)                    |
| document_type                 | String  | Type of document (e.g. CHAMBER/COMMITTEE/GRANDCHAMBER) |
| date_decision                 | String  | Date of the decision                                   |
| ECLI                          | String  | European Case Law Identifier                           |
| importance                    | Number  | Importance of case (1-4)                               |
| language                      | String  | Language of case                                       |
| instance                      | Number  | Number of instance                                     |
| representation                | Date    | Representation in the case                             |
| alternative_publications      | String  |                                                        |
| sources                       | String  | Source of the case                                     |
| extractedappno                | String  |                                                        |
| citations                     | String  | Cases cited in case                                    |
| docid                         | String  | Document id                                            |
| workid                        | String  | Work id                                                |
| respondent                    | String  | Defender of the case                                   |
| separateopinion               | Boolean |                                                        |
| sharepointid                  | Number  | Internal identifier                                    |
| author                        | Number  |                                                        |
| violation                     | String  | Violated articles                                      |
| typedescription               | Number  |                                                        |
| nonviolation                  | String  |                                                        |
| path                          | String  |                                                        |
| description                   | String  |                                                        |

### Court of Justice of the European Union (CJEU)

The [CJEU](https://european-union.europa.eu/institutions-law-budget/institutions-and-bodies/institutions-and-bodies-profiles/court-justice-european-union-cjeu_en) is an European court that makes sure the law is applied in the same way in all EU countries. CJEU cases' metadata and content can be retrieved from [CELLAR](https://data.europa.eu/data/datasets/sparql-cellar-of-the-publications-office?locale=en), an European service that provides data through a SPARQL API. 

#### Sources

- API Endpoint: https://publications.europa.eu/webapi/rdf/sparql
- Documentation: https://op.europa.eu/documents/10530/676542/ao10463_annex_17_cellar_dissemination_interface_en.pdf

#### Data format

These fields are expected to be found in the CSV files that store the CJEU data: 

| Name                             | Format                    | Definition                                                        |
|:---------------------------------|:--------------------------|:------------------------------------------------------------------|
| commented_by_agent               | String                    | Provides information on which Member States submitted information |
| delivered_by_court_formation     | String                    | Court (Chamber) that delivered the judgment                       | 
| judicial_procedure_type          | String                    | Type of procedure (eg reference, annulment)                       |
| type_procedure                   | String                    | Type of procedure with more information                           |
| conclusions                      | String                    | Opinion of the Advocate-General                                   |
| legal_resource                   | URL                       | The source (eg law, legal provision) the case interprets          |                                                                   
| origin_country                   | String                    | Country of  judgement                                             |
| origin_country_or_role_qualifier | String                    | Country in which the case originated with more information        |
| language_procedure               | String                    | Language of procedure                                             |
| celex                            | String                    | Celex identifier                                                  |
| date_publication                 | Date                      | Document date                                                     |
| date_of_request                  | Date                      | Date of request for an Opinion of the Advocate-General            |
| ECLI                             | String                    | European Case Law Identifier                                      |
| date_of_creation                 | Date                      | Date of latest modification in dataset                            |
| based_on_treaty                  | String                    | Treaty on which judgment is based                                 |
| subject_matter                   | String                    | Subject matter                                                    |
| national_judgement               | RDF                       | Source of national case                                           |
| references_journals              | RDF                       | References to journal articles                                    |
| sector                           | Number                    | Indicates the type of source                                      |                                                     
| resource_type                    | String                    | Document type (judgment, opinion, order)                          |
| directory_codes                  | String                    | Directory classification codes for case                           |
| eurovoc                          | String                    | Eurovoc classification codes for case                             |
| keywords                         | String                    | Keywords of case                                                  |
| summary                          | String                    | Summary of case                                                   |
| citing                           | Celex id list             | Cases cited by case                                               |
| cited_by                         | Celex id list             | Cases citing the case                                             |
| advocate_general                 | String                    | Advocate General of the case                                      |
| judge_rapporteur                 | String                    | Judge Rapporteur of the case                                      |
| affecting_ids                    | Celex id list             | Cellar id's of case affecting                                     |
| affecting_string                 | String                    | List of entire strings with more details about case affecting     |
| citations_extra_info             | String                    | Citations with exact paragraphs cited                             |


 

