# Setup new data source

This walkthrough covers the steps needed to add a new data source to the infrastructure. It follows the extract, transform, and load steps accordingly. 

## Extract

Import an extraction script for the new data source. Make sure you have the right methods to extract data, and be able to store it in a digital format (*e.g.* JSON, XML, CSV). 

For example, our [CELLAR extraction](/datasets/?id=court-of-justice-of-the-european-union-cjeu) uses our `cellar-extractor` library to retrieve data from a SPARQL endpoint and temporarily stores the JSON and CSV responses.

```python
# Extract the CELLAR data
df, json_file = cell.get_cellar_extra(save_file='n', max_ecli=amount, sd=last_updated, ed=today_date,
                                             threads=15,
                                              username=WEBSERVICE_USERNAME, password=WEBSERVICE_PASSWORD)
```

Setup the `Storage` object and the paths for the files to be stored. Read the full documentation of the [`Storage` reference](/reference/storage). 

For example, for the [CELLAR extraction](/datasets/?id=court-of-justice-of-the-european-union-cjeu) we do the following:

- Setup the paths for the Legal Intelligence files in `storage_handler.py`:
  ```python
  CSV_CELLAR_CASES = 'cellar_csv_data.csv'  # Metadata of CELLAR cases
  ```
  And import them later in the extraction script `legal_intelligence_extractor.py`:
  ```python
  from definitions.storage_handler import CSV_CELLAR_CASES, get_path_raw
  output_path = get_path_raw(CSV_CELLAR_CASES)
  ```
- Initialize the `Storage` object:
  ```python
  # Setup storage
  storage = Storage()
  ```
- Setup the `Storage` object with the `output_paths` argument imported from `storage_handler.py` :
  ```python   
  # Import CSV_CELLAR_CASES from storage_handler.py
  output_path = get_path_raw(CSV_CELLAR_CASES)
  
  # Setup storage
  storage.setup_pipeline(output_paths=[output_path])
  ```

Once you have the raw extracted data, use the `Storage` object to store it on your disk. 

For example, our [CELLAR extraction](/datasets/?id=court-of-justice-of-the-european-union-cjeu) handles the extracted data as follows:

- After it stores the data from the API in a `DataFrame`, it exports it locally to the `output_path`:
  ```python
  # Save CSV file
  df.to_csv(output_path, index=False)

## Transform

Before running the transformation scripts, be sure you map the fields of your data with the definitions described in the [`Attribute` reference](/reference/attribute).

Import the file paths of your data into `data_transformer.py`.

```python
input_paths = [
        get_path_raw(CSV_RS_CASES),
        get_path_raw(CSV_RS_OPINIONS),
        get_path_raw(CSV_CELLAR_CASES),
        get_path_raw(CSV_ECHR_CASES)
    ]
```

The script will process and transform the raw data in each file in `input_paths` and outputs the clean data in the respective files in `output_paths`.
For this, field maps and tool maps need to be defined in the [data transformer](https://github.com/maastrichtlawtech/case-law-explorer/blob/76d4dc02012139418eaa0b584656b852d8d93db9/data_transformation/data_transformer.py) 
for each new input file and its respective data fields. 

The field maps create a mapping between the original attribute names of the new data source and the global attribute names
(see [`attribute` reference](reference/attribute) > Attribute Names).

The tool maps create a mapping between the source's attribute names and the corresponding transformation/cleaning function, as defined in [utils.py](https://github.com/maastrichtlawtech/case-law-explorer/blob/master/data_transformation/utils.py).

```python
# process input file by row
for row in reader:
  row_clean = dict.fromkeys(field_map.values())
  for col, value in row.items():
    if value:
      if col in tool_map:
        row_clean[field_map[col]] = tool_map[col](value.strip())
      else:
        row_clean[field_map[col]] = value.strip()
```

At the end, the `data_transformer.py` script, similarly to the extraction scripts, will store the clean data on the disk and/or AWS.

# Load

After its transformation and cleaning, your data is ready to be loaded into DynamoDB domains. The `data_loader.py` script will initialize instances for `DynamoDBClient` with the right environmental variables, as described in the [GraphQL API walkthrough](graphql/?id=setup). 

Add your **processed** file paths to the `input_paths` in the `data_loader.py` script and your **full-text** file paths to the `full_text_paths`:

```python
input_paths = [
        get_path_processed(CSV_RS_CASES),
        get_path_processed(CSV_RS_OPINIONS),
        get_path_processed(CSV_ECHR_CASES),
        get_path_processed(CSV_CELLAR_CASES)
    ]
    full_text_paths = [
        JSON_FULL_TEXT_CELLAR,
        JSON_FULL_TEXT_ECHR
    ]
```

The `data_loader.py` script will process each row of each file in the `input_paths` as follows:

- Store the data on the row in the DynamoDB table.

For the DynamoDB table, items are created from the input data to match the respective schema 
and to determine, whether a new item should be loaded or an existing item should be updated. Define in the respective [row processor](https://github.com/maastrichtlawtech/case-law-explorer/tree/master/data_loading/row_processors) script,
how each row of the new data source should be turned into items.

The DynamoDB table contains a number of secondary indexes with the following key schema. For new data to be loaded successfully,
row processors need to be defined that turn each input row to DynamoDB items following the below key schema (see [`data_loading/row_processors` reference](reference/row-processors)):

**Primary table:**

|                   | Name      | Type   | Values                                | Example                                         |
|:------------------|:----------|:-------|:--------------------------------------|-------------------------------------------------|
| **Partition key** | ecli      | String |                                       | ECLI&colon;NL&colon;RBLIM&colon;2014&colon;2011 |
| **Sort key**      | ItemType  | String | {DATA, DOM_*domain*, DOM-LI_*domain*} | DOM_Civiel recht                                |


**GSI-ItemType:**

|                   | Name          | Type   | Values                                                                | Example           |
|:------------------|:--------------|:-------|:----------------------------------------------------------------------|-------------------|
| **Partition key** | ItemType      | String | {DATA, DOM_*domain*, DOM-LI_*domain*}                                 | DOM_Civiel recht  |
| **Sort key**      | SourceDocDate | String | Source: {RS, ECHR, EURLEX} <br/>Doc: {DEC, OPI} <br/>Date: yyyy-mm-dd | RS_DEC_2006-10-30 |

**GSI-instance:**

|                   | Name          | Type   | Values                                                                | Example           |
|:------------------|:--------------|:-------|:----------------------------------------------------------------------|-------------------|
| **Partition key** | instance      | String |                                                                       | Hoge Raad         |
| **Sort key**      | SourceDocDate | String | Source: {RS, ECHR, EURLEX} <br/>Doc: {DEC, OPI} <br/>Date: yyyy-mm-dd | RS_DEC_2006-10-30 |


**GSI-instance_li:**

|                   | Name          | Type   | Values                                                                | Example           |
|:------------------|:--------------|:-------|:----------------------------------------------------------------------|-------------------|
| **Partition key** | instance_li   | String |                                                                       | Hoge Raad         |
| **Sort key**      | SourceDocDate | String | Source: {RS, ECHR, EURLEX} <br/>Doc: {DEC, OPI} <br/>Date: yyyy-mm-dd | RS_DEC_2006-10-30 |


