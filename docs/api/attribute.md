# `Attribute` API Reference

Since each data source uses different data attribute labels and different terminology to refer to equivalent content 
(such as court names), we defined classes to map attribute names and values to global constants that can be accessed 
by different scripts throughout the ETL pipeline.

When adding a new data source to the pipeline, new definitions need to be made to define attribute name and value mappings.

### Attribute Naming
The following table comprises an overview of the attributes that are being extracted from the different data sources, 
their global label, and how they correspond to each other.

| Global reference    | Rechtspraak         | Legal Intelligence  | LiDO                | ECHR                | CJEU                || Meaning             |
|---------------------|---------------------|---------------------|---------------------|---------------------|---------------------||---------------------|
| ecli                | identifier          | CaseNumber          | _check_             | ECHR_ecli           | CJEU_ecli           || _do we need this?_  |
| instance            | creator             | IssuingInstitution  | -                   | ECHR_court          | CJEU_court          || _do we need this?_  |
| domains             | subject             | LawArea             | -                   |                     |                     || _do we need this?_  |
| ...                 |                     |                     |                     |                     |                     || _do we need this?_  |

### Attribute Value Naming
In order to be able to filter the data of the different sources by the keywords, certain categorical attributes 
require consistent value namings. This includes the attributes 'domains', 'instance', 'jurisdiction', 'source'.
Besides, for the DynamoDB table schema, new composite keys were created to facilitate filtering (DataSource, DocType, ItemType).