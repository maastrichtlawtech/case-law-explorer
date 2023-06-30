`# `Attribute` Reference

Since each data source uses different data attribute labels and different terminology to refer to equivalent content 
(such as court names), we defined classes to map attribute names and values to global constants that can be accessed 
by different scripts throughout the ETL pipeline.

When adding a new data source to the pipeline, new definitions need to be made to declare attribute name and value mappings.

### Attribute Names
The following table comprises an overview of the attributes that are being extracted from the different data sources, 
their global label, and how they correspond to each other.

The table corresponds to the logic defined in the following scripts: 
- [`definitions/terminology/attributes_names.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/definitions/terminology/attribute_names.py)
- [`definitions/mappings/attribute_name_maps.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/definitions/mappings/attribute_name_maps.py)

More information on the meaning of the different attributes can be found in the [datasets](/datasets/) description.

**Cases:**

| Global reference              | Rechtspraak               | Legal Intelligence        | ECHR                      | CJEU                      |
|-------------------------------|---------------------------|---------------------------|---------------------------|---------------------------|
| **alternative_publications**  | hasVersion                | Sources                   |                           |                           |
| **case_number**               | zaaknummer                | CaseNumber                |                           |                           |
| **date_added**                | -                         | DateAdded                 |                           |                           |
| **date_decision**             | date                      | EnactmentDate             |                           |                           |
| **date_publication**          | issued                    | PublicationDate           |                           |                           |
| **display_subtitle**          | -                         | DisplaySubtitle           |                           |                           |
| **display_title**             | -                         | DisplayTitle              |                           |                           |
| **document_id**               | -                         | Id                        |                           |                           |
| **document_type**             | type                      | -                         |                           |                           |
| **domains**                   | subject                   | LawArea                   |                           |                           |
| **ecli**                      | identifier                | CaseNumber                | ecli                      | ECLI                      |
| **ecli_decision**             | ecli_decision *(generated)*| -                        |                           |                           |
| **ecli_opinion**              | ecli_opinion *(generated)*| -                         |                           |                           |
| **full_text**                 | full_text *(generated)*   | -                         |                           |                           |
| **info**                      | info                      | -                         |                           |                           |
| **instance**                  | creator                   | IssuingInstitution        |                           |                           |
| **issue_number**              | -                         | IssueNumber               |                           |                           |
| **jurisdiction_city**         | spatial                   | -                         |                           |                           |
| **jurisdiction_country**      | jurisdiction_country *(generated)*| Jurisdiction      |                           |                           |
| **language**                  | language                  | -                         |                           |                           |
| **predecessor_successor_cases**| relation                 | -                         |                           |                           |
| **procedure_type**            | procedure                 | -                         |                           |                           |
| **publication_number**        | -                         | PublicationNumber         |                           |                           |
| **referenced_legislation_titles**| references             | -                         |                           |                           |
| **search_numbers**            | -                         | SearchNumbers             |                           |                           |
| **source**                    | source *(generated)*      | DocumentType              |                           |                           |
| **summary**                   | inhoudsindicatie          | Summary                   |                           |                           |
| **title**                     | title                     | Title                     |                           |                           |
| **url_entry**                 | -                         | Url                       |                           |                           |
| **url_publication**           | identifier2               | OriginalUrl               |                           |                           |

**Citations:**

| Global reference          | LiDO                      |
|---------------------------|---------------------------|
| target_ecli               | Jurisprudentie            |
| label                     | label                     |
| type                      | type                      |
| legal_provision_url       | Artikel                   |
| legal_provision           | Artikel title             |
| legal_provision_url_lido  | Wet                       |

### Attribute Values
In order to be able to filter the data of the different sources by the keywords, certain categorical attributes 
require consistent value namings. This includes the attributes `domains`, `instance`, `jurisdiction`, `source`.
Besides, for the DynamoDB table schema, new composite keys were created to facilitate filtering (`DataSource`, `DocType`, `ItemType`).

The attribute value terminology and mappings are defined in the following scripts:
- [`definitions/terminology/attribute_values.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/definitions/terminology/attribute_values.py)
- [`definitions/mappings/attribute_value_maps.py`](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/definitions/mappings/attribute_value_maps.py)