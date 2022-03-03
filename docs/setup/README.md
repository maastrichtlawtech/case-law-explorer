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

Setup the `Storage` object and the paths for the files to be stored. Read the full documentation of the [`Storage` reference](/api/storage). 

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

> [!WARNING]
> **This sections is not complete!** It misses important information about the definitions **??? @Maxine :((( help**

Before running the transformation scripts, be sure you map the fields of your data with the definitions described in the [`Attribute` reference](/api/attribute). 

For example, for our scripts we defined **??? @Maxine :((( help**.

Import the file paths of your data into `data_transformer.py`. At the moment, the script holds the input and the output paths for Rechtspraak and Legal Intelligence as it follows:

```python
input_paths = [get_path_raw(CSV_RS_CASES), get_path_raw(CSV_RS_OPINIONS), get_path_raw(CSV_LI_CASES)]
output_paths = [get_path_processed(CSV_RS_CASES), get_path_processed(CSV_RS_OPINIONS), get_path_processed(CSV_LI_CASES)]
```

The script will process and transform the raw data in each file in `input_paths` and outputs the clean data in the respective files in `output_paths`. The transformation follows the rules defined in the `definitions/` director, as **??? @Maxine :((( help**. 

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

> [!WARNING]
> **This section is not complete!** It does **not** cover the usage of `DynamoDBClient` `OpenSearchClient` `DynamoDBRowProcessor` `OpenSearchRowProcessor`. I am not sure if it's worth describing it, but maybe you wanna cover it??**??? @Maxine :((( help** 

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

