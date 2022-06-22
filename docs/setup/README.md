# Setup new data source

This walkthrough covers the steps needed to add a new data source to the infrastructure. It follows the extract, transform, and load steps accordingly. 

## Extract

Import an extraction script for the new data source. Make sure you have the right methods to extract data, and be able to store it in a digital format (*e.g.* JSON, XML, CSV). 

For example, our [Legal Intelligence extraction script](/datasets/?id=legal-intelligence-api) uses `requests` library to retrieve data from the API and temporarily stores the JSON responses in a `documents` variable.

```python
# Build the Legal Intelligence URL with queries and filters
link = f'{LI_ENDPOINT}/search?q={query}&fq={filters}'

# Request and save data from the LI_ENDPOINT
response = requests.get(link, headers=headers, params=params)
documents += response.json()['Documents']
```

Setup the `Storage` object and the paths for the files to be stored. Read the full documentation of the [`Storage` reference](/reference/storage). 

For example, for the [Legal Intelligence extraction script](/datasets/?id=legal-intelligence-api) we do the following:

- Setup the paths for the Legal Intelligence files in `storage_handler.py`:
  ```python
  CSV_LI_CASES = 'LI_cases.csv'  # file to store Legal Intelligence data
  ```
  And import them later in the extraction script `legal_intelligence_extractor.py`:
  ```python
  from definitions.storage_handler import CSV_LI_CASES, get_path_raw
  output_path = get_path_raw(CSV_LI_CASES)
  ```
- Initialize the `Storage` object with the `location` argument passed from the `ArgumentParser`:
  ```python
  # Add `storage` to ArgumentParser
  parser = argparse.ArgumentParser()
  parser.add_argument('storage', choices=['local', 'aws'], help='location to take input data from and   save output data to')
  args = parser.parse_args()
  
  # Setup storage
  storage = Storage(location=args.storage)
  ```
- Setup the `Storage` object with the `output_paths` argument imported from `storage_handler.py` :
  ```python   
  # Import CSV_LI_CASES from storage_handler.py
  output_path = get_path_raw(CSV_LI_CASES)
  
  # Setup storage
  storage.setup_pipeline(output_paths=[output_path])
  ```

Once you have the raw extracted data, use the `Storage` object to store it on your disk and/or AWS. 

For example, our [Legal Intelligence extraction script](/datasets/?id=legal-intelligence-api) handles the extracted data as follows:

- After it stores the data from the API in a `DataFrame`, it exports it locally to the `output_path`:
  ```python
  # Save CSV file
  df.to_csv(output_path, mode='a', index=False, header=header)
  ```
- Uses the `Storage` object to upload the file at the `output_path` to AWS:
  ```python
  # Finish storage by uploading to AWS (if aws is selected)
  storage.finish_pipeline()
  ```

## Transform

Before running the transformation scripts, be sure you map the fields of your data with the definitions described in the [`Attribute` reference](/reference/attribute).

Import the file paths of your data into `data_transformer.py`. At the moment, the script holds the input and the output paths for Rechtspraak and Legal Intelligence as it follows:

```python
input_paths = [get_path_raw(CSV_RS_CASES), get_path_raw(CSV_RS_OPINIONS), get_path_raw(CSV_LI_CASES)]
output_paths = [get_path_processed(CSV_RS_CASES), get_path_processed(CSV_RS_OPINIONS), get_path_processed(CSV_LI_CASES)]
```

The script will process and transform the raw data in each file in `input_paths` and outputs the clean data in the respective files in `output_paths`.
For this, field maps and tool maps need to be defined in the [data transformer](https://github.com/maastrichtlawtech/case-law-explorer/blob/76d4dc02012139418eaa0b584656b852d8d93db9/data_transformation/data_transformer.py) 
for each new input file and its respective data fields. 

The field maps create a mapping between the original attribute names of the new data source and the global attribute names
(see [`attribute` reference](reference/attribtue) > Attribute Names).

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

After its transformation and cleaning, your data is ready to be loaded into DynamoDB and OpenSearch domains. The `data_loader.py` script will initialize instances for `DynamoDBClient` and `OpenSearchClient` with the right environmental variables, as described in the [GraphQL API walkthrough](graphql/?id=setup). 

Add your **processed** file paths to the `input_paths` in the `data_loader.py` script:

```python
input_paths = [
  get_path_processed(CSV_RS_CASES),
  get_path_processed(CSV_RS_OPINIONS),
  get_path_processed(CSV_LI_CASES),
  get_path_raw(CSV_CASE_CITATIONS),
  get_path_raw(CSV_LEGISLATION_CITATIONS)
]
```

The `data_loader.py` script will process each row of each file in the `input_paths` as follows:

- Store the data on the row in the DynamoDB table.
- Upload the data on the row in the OpenSearch domain.

Both for the DynamoDB table and the OpenSearch index, items are created from the input data to match the respective schema 
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


