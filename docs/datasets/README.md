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

| Name                | Format                             | Definition                                                                                |
|:--------------------|:-----------------------------------|:------------------------------------------------------------------------------------------|
| identifier          | String                             | ECLI (European Case Law Identifier): unique identifier for court decisions in Europe      |
| identifier          | String                             | URL to original document by publisher                                                     |
| issued              | String / yyyy-mm-dd                | Date of document publication                                                              |
| language            | String / "nl"                      | Language of jurisdiction to which case belongs                                            |
| creator             | String                             | Name of instance (court)                                                                  |
| spatial             | String                             | Court location (municipality)                                                             |
| date                | String / yyyy-mm-dd                | Date of court decision                                                                    |
| zaaknummer          | String                             | Case number, for internal use by courts (main identifier prior to introduction of ECLI)   |
| type                | String / "uitspraak" / "conclusie" | Document type: decision/opinion                                                           |
| procedure           | String[]                           | Procedure type (e.g. summary proceedings)                                                 |
| subject             | String / "domain; subdomain"       | Domain (area of the law) applicable to case                                               |
| relation            | String[]                           | Predecessor and successor cases (in case of appeal, cassation, preliminary decisions etc) |
| references          | String[]                           | Title of applicable legislation                                                           |
| hasVersion          | String[]                           | References to other publications                                                          |
| title               | String                             | Title of case                                                                             |
| inhoudsindicatie    | XML                                | Case summary                                                                              |
| uitspraak/conclusie | XML                                | Full text of case decision/opinion                                                        |

### Legal Intelligence API

[Legal Intelligence](https://www.legalintelligence.com) is a legal search engine of a private provider which integrates data from different publishers and thus enhances the data available at rechtspraak.nl, especially for cases before the year 2000. 

#### Access
The platform can be accessed via institutional login, or by [requesting access](https://www.legalintelligence.com/nl/proef-abonnement/). Once access is granted, the data can also be received through the Legal Intelligence API in JSON (or XML) format.

#### Sources

- Website: https://www.legalintelligence.com/
- API endpoint: https://api.legalintelligence.com/
- Documentation: https://www.legalintelligence.com/handleidingen/api-technical-information/

#### Data format

The following fields are currently extracted from the JSON objects:  

| Name                         | Format                 | Definition                                                                              |
|:-----------------------------|:-----------------------|:----------------------------------------------------------------------------------------|
| Id                           | String                 | Internal document ID                                                                    |
| Title                        | String                 | Title of case                                                                           |
| DisplayTitle                 | String                 | Internal title of document entry                                                        |
| DisplaySubtitle              | String                 | Internal subtitle of document entry                                                     |
| Summary                      | String                 | Case summary                                                                            |
| Url                          | String                 | URL to document entry in Legal Intelligence                                             |
| OriginalUrl                  | String                 | URL to original document by publisher                                                   |
| Jurisdiction                 | String / "Nederland"   | Country of jurisdiction                                                                 |
| DocumentType                 | String / "Rechtspraak" | Source of case                                                                          |
| LawArea                      | String[]               | Domains (area of the law) applicable to case                                            |
| IssuingInstitution           | String                 | Name of instance (court)                                                                |
| CaseNumber                   | String                 | Case number, for internal use by courts (main identifier prior to introduction of ECLI) |
| PublicationNumber            | String                 | Internal document id of publisher                                                       |
| IssueNumber                  | String                 | References to other publications                                                        |
| PublicationDate              | Int / yyyyMMdd         | Date of document publication                                                            |
| EnactmentDate                | Int / yyyyMMdd         | Date of court decision                                                                  |
| DateAdded                    | Int / yyyyMMdd         | Date document added to Legal Intelligence                                               |
| Sources                      | String[]               | References to other publications                                                        |
| SearchNumbers                | String[]               |                                                                                         |
| ecli *(generated by script)* | String                 | European Case Law Identifier                                                            |

### Linked Data Overheid (LiDO)

[Linked Data Overheid](https://linkeddata.overheid.nl/) is a public database provided by the Dutch government that contains the links between Dutch and European cases and legislation.

#### Access
Access to the platform is open. To access the API, one can request a username and password by sending an email to linkeddata@koop.overheid.nl, as per their service documentation.

#### Sources

- Website: https://linkeddata.overheid.nl/
- API Endpoint: http://linkeddata.overheid.nl/service/get-links
- Documentation: https://linkeddata.overheid.nl/front/portal/services

#### Data format

The following fields are extracted with the LiDO API:

**Caselaw citations:**

| Name                          | Format | Definition                                                           |
|:------------------------------|:-------|:---------------------------------------------------------------------|
| target_ecli                   | String | ECLI of the case that is being cited                                 |
| label                         | String | Descriptive type of citation (conclusie, appeal, cassatie, ...)      |
| type                          | String | Type id of citation as given in the linktype URL                     |
| keep1 *(generated by script)* | String | whether or not *type* equals *'lx-referentie'*                       |
| keep2 *(generated by script)* | String | whether or not *target_ecli* is not in *predecessor_successor_cases* |

**Legislation citations:**

| Name                     | Format | Definition                              |
|:-------------------------|:-------|:----------------------------------------|
| legal_provision          | String | Title of cited legislation              |
| legal_provision_url      | String | URL to cited legislation (on wetten.nl) |
| legal_provision_url_lido | String | URL to LiDO entry of cited legislation  |


## European courts

We are making efforts to include in our project European and international courts as well. So far we are working to add this European courts to our codebase.

### European Court of Human Rights (ECHR)

> [!ATTENTION|label:WORK IN PROGRESS]
> The ECHR extraction, transformation, and loading script are still **work in progress**! This is an overview of the current data format.

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

| Name                | Format   | Definition                                       |
|:--------------------|:---------|:-------------------------------------------------|
| itemid              | String   | Unique identifier                                |
| applicability       | String   |                                                  |
| application         | String   |                                                  |
| appno               | String   | Application number                               |
| article             | String   | Alleged violated articles                        |
| conclusion          | String   | Violated/Non-violated articles                   |
| docname             | String   | Name of the case                                 |
| doctype             | String   | Type of document                                 |
| doctypebranch       | String   |                                                  |
| ecli                | String   | European Case Law Identifier                     |
| importance          | Number   |                                                  |
| isplaceholder       | Boolean  |                                                  |
| judgementdate       | Date     | Date of judgement                                |
| kpdate              | Date     | Date of judgement in 12-hours format             |
| kpdateAsText        | String   | Date of judgement as string                      |
| kpthesaurus         | String   |                                                  |
| languageisocode     | String   | Language of case                                 |
| originatingbody     | Number   |                                                  |
| Rank                | Number   |                                                  |
| representedby       | String   | Representation of the case                       |
| respondent          | String   | Defender of the case                             |
| respondentOrderEng  | Number   | Defender unique identifier                       |
| separateopinion     | Boolean  |                                                  |
| sharepointid        | Number   | Internal identifier                              |
| typedescription     | Number   |                                                  |
| violation           | String   | Violated articles                                |
| typedescription     | Number   |                                                  |
| violation           | String   |                                                  |

### Court of Justice of the European Union (CJEU)

> [!ATTENTION|label:WORK IN PROGRESS]
> The CJEU extraction, transformation, and loading script are still **work in progress**! This is an overview of the current data format.

The [CJEU](https://european-union.europa.eu/institutions-law-budget/institutions-and-bodies/institutions-and-bodies-profiles/court-justice-european-union-cjeu_en) is an European court that makes sure the law is applied in the same way in all EU countries. CJEU cases' metadata and content can be retrieved from [CELLAR](https://data.europa.eu/data/datasets/sparql-cellar-of-the-publications-office?locale=en), an European service that provides data through a SPARQL API. 

#### Sources

- API Endpoint: https://publications.europa.eu/webapi/rdf/sparql
- Documentation: https://op.europa.eu/documents/10530/676542/ao10463_annex_17_cellar_dissemination_interface_en.pdf

#### Data format

These fields are expected to be found in the CSV files that store the CJEU data: 

| Name                                                    | Format | Definition                                                         |
|:--------------------------------------------------------|:-------|:-------------------------------------------------------------------|
| CASE LAW COMMENTED BY AGENT                             | String | Provides information on which Member States submitted information  |
| CASE LAW DELIVERED BY COURT FORMATION                   | String | Court (Chamber) that delivered the judgment                        | 
| CASE LAW HAS A JUDICIAL PROCEDURE TYPE                  | String | Type of procedure (eg reference, annulment)                        |
| CASE LAW HAS TYPE OF PROCEDURE                          | String | Type of procedure with more information                            |
| CASE LAW HAS CONCLUSIONS                                | String | Opinion of the Advocate-General                                    |
| CASE LAW INTERPRETS LEGAL RESOURCE                      | URL    | The source (eg law, legal provision) the case interprets           |                                                                   |
| CASE LAW ORIGINATES IN COUNTRY                          | String | Country of  judgement                                              |
| CASE LAW ORIGINATES IN COUNTRY OR USES A ROLE QUALIFIER | String | Country in which the case originated with more information         |
| CASE LAW USES LANGUAGE OF PROCEDURE                     | String | Language of procedure                                              |
| CELEX IDENTIFIER                                        | String | Celex identifier                                                   |
| DATE OF DOCUMENT                                        | Date   | Document date                                                      |
| DATE OF REQUEST FOR AN OPINION                          | Date   | Date of request for an Opinion of the Advocate-General             |
| ECLI                                                    | String | European Case Law Identifier                                       |
| LEGACY DATE OF CREATION OF WORK                         | Date   | Date of latest modification in dataset.                            |
| LEGAL RESOURCE BASED ON TREATY CONCEPT                  | String | Treaty on which judgment is based                                  |
| LEGAL RESOURCE IS ABOUT SUBJECT MATTER                  | String | Subject matter                                                     |
| NATIONAL JUDGEMENT                                      | RDF    | Source of national case                                            |
| RELATED JOURNAL ARTICLE                                 | RDF    | References to journal articles                                     |
| SECTOR IDENTIFIER                                       | Number | Indicates the type of source                                       |
| WORK CITES WORK. CI / CJ                                | URL    | Works cited                                                        |
| WORK HAS RESOURCE TYPE                                  | String | Document type (judgment, opinion, order)                           |
| YEAR OF THE LEGAL RESOURCE                              | Date   | Judgement Year                                                     |

