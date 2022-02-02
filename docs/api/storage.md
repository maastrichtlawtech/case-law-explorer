# `Storage` API Reference

The `Storage` API is the script that handles the storage of extracted files. It defines global directory paths and the terminology used throughout all data processing steps.

### Usage 

```python
storage = Storage(location='local')
```

#### Parameters 

- `location`: Storage location must be either `'local'` or `'aws'`. **Default**: `'local'`.

#### Objects

I feel like we should address some of the instance objects defined in `__init__`. Such as:

- `s3_bucket_name`: Lorem ipsum yess
- `s3_bucket`: Lorem ipsum mooo
- `s3_client`: Lorem ipsum yeasss
- `pipeline_input_path`: Lorem ipsum helloo
- `pipeline_output_paths`: Lorem ipsum hey
- `pipeline_last_updated`: Lorem ipsum bye

### Methods

- [`fetch_data`](#fetch_data): Fetch data from local/aws files
- [`fetch_last_updated`](#fetch_last_updated): Fetch the date of the last updated row in a file
- [`upload_data`](#upload_data): Upload files to AWS or write files on the disk
- [`setup_pipeline`](#setup_pipeline): Setup the storage pipeline
- [`finish_pipeline`](#finish_pipeline): Finish the storage pipeline

#### `fetch_data`

Fetch data from local/remote files. Makes sure the files are existing and ready to be fetched. If locally, it reads data from the disk. If on aws, it downloads files from the S3 bucket and writes them on the disk.

##### Parameters

- 'paths': The file paths to be fetched

#### `fetch_last_updated`

Fetch data from local/remote existent files and return the last date the has been stored. 

##### Parameters

- 'paths': The file paths to be fetched

#### `upload_data`

Uploads the files to the S3 bucket. If locally, it writes the data into the files on the disk.

##### Parameters

- 'paths': The file paths to be uploaded

#### `setup_pipeline`

Setup the paths for the files that need to be fetched in the pipeline. Uses [`fetch_data`](#fetch_data) and [`fetch_last_updated`](#fetch_last_updated) to make sure the local files or S3 buckets are available to be fetched.   

##### Parameters

- 'output_paths': List of paths of output data
- 'input_path': List of paths to fetch input data

#### `finish_pipeline`

Finish the storage pipeline. Uses [`upload_data`](#upload_data) to upload the data to the consequent output paths (if any). 

### Errors

- [`BucketAlreadyOwnedByYou`](#BucketAlreadyOwnedByYou): Very bad error
- [`BucketAlreadyExists`](#BucketAlreadyExists): Super bad error

#### `BucketAlreadyOwnedByYou`

Very bad error

#### `BucketAlreadyExists`

Super bad error