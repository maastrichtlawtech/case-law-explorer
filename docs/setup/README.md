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

> [!important] Postgres, not DynamoDB (issue #42)
> As of issue #42, `data_loader.py` loads into the `cle_v2` Postgres schema instead of DynamoDB + S3. The DynamoDB key-schema tables that used to live in this section are gone -- see `db/schema.sql` (DDL) and `db/README.md` for the current schema.

After its transformation and cleaning, your data is ready to be loaded. `data_loader.py` initializes a single `PostgresCLEClient` (`data_loading/clients/postgres.py`), which wraps the `pg_cle` Airflow connection.

**One-time setup**:

```bash
airflow connections add pg_cle \
  --conn-type postgres \
  --conn-host <host> \
  --conn-schema cle_v2 \
  --conn-login <user> \
  --conn-password <password> \
  --conn-port 5432
```

For local development, `docker-compose.yaml` includes a `cle-postgres` service (pgvector image, initialized from `db/schema.sql`) -- point `pg_cle` at `cle-postgres:5432` / `localhost:5433` from outside the compose network.

Add your **processed** file paths to the `input_paths` in the `data_loader.py` script and your **full-text** file paths to the `full_text_paths`, same as before:

```python
input_paths = [
        get_path_processed(CSV_RS_CASES),
        get_path_processed(CSV_ECHR_CASES),
        get_path_processed(CSV_CELLAR_CASES)
    ]
    full_text_paths = [
        JSON_FULL_TEXT_CELLAR,
        JSON_FULL_TEXT_ECHR
    ]
```

`data_loader.py` processes each row of each file in `input_paths` by:

- Upserting into `cases` (keyed on whichever of `ecli` / `celex_id` / `item_id` the row has) to get a `case_id`.
- Upserting the source-specific detail row (`rs_document` / `cjeu_document` / `echr_document`) keyed on that `case_id`.
- Upserting full text (where available inline, e.g. Rechtspraak) into `case_text`.

Define how each new data source's row maps to columns in the respective [row processor](https://github.com/maastrichtlawtech/case-law-explorer/tree/master/airflow/dags/data_loading/row_processors) (`row_processors/postgres.py`) -- one class per source (`PostgresRSProcessor`, `PostgresCelexProcessor`, `PostgresItemIdProcessor`), each calling `PostgresCLEClient.upsert_case()` + `.upsert()` for its detail table. Full text and citation-graph edges arriving as separate files (Cellar/ECHR) are loaded afterwards by `case_text_loader.py` and `citation_graph_loader.py` respectively, resolving `case_id` by `celex`/`item_id`/`ecli` via `PostgresCLEClient.resolve_case_id()`.

