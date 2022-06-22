# `Storage` Reference

The `Storage` API is the script that handles the storage of extracted files. It defines global directory paths and the terminology used throughout all data processing steps.

In both storage locations, the data directory follows the structure of:
<pre>
 
└── data
    ├── OpenDataUitspraken <i># data parsed from the OpenDataUitspraken.zip archive</i>
    ├── processed <i># data processed as result of the transformation scripts</i>
    └── raw <i># raw data extracted as result of the extractions scripts</i>
     
</pre>

### Usage 

```python
storage = Storage(location='local')
```

#### Parameters 

- `location`: Storage location must be either `'local'` or `'aws'`. **Default**: `'local'`.

#### Objects

The following instance objects are defined in `__init__`:

- `s3_bucket_name`: The name of the AWS S3 bucket to be used for storage, as defined in the `.env` file
- `s3_bucket`: The S3 bucket object
- `s3_client`: The S3 client
- `pipeline_input_path`: The path to the input file of the pipeline step in which the storage object is initiated
- `pipeline_output_paths`:  The paths to the output files of the respective pipeline step
- `pipeline_last_updated`: The last date of update, determined from input and output files

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