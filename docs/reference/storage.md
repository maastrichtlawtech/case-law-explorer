# `Storage` Reference

The `Storage` API is the script that handles the storage of extracted files. It defines global directory paths and the terminology used throughout all data processing steps.

> [!important] Full text and citations now target Postgres (issue #42)
> Full text and the citation graph used to be uploaded to S3 (`full-text-data` and `cellar-nodes-edges-bucket`) as an intermediate step after landing here as local files. Both buckets are gone: `data_loading/case_text_loader.py` and `data_loading/citation_graph_loader.py` read these same local files and upsert directly into the `cle_v2` Postgres schema (`case_text`, `case_citation`) instead. See `db/README.md`.

The local staging directory still follows the same structure below -- only what happens to `full_text/` and the node/edge txt files under `raw/` after extraction has changed.
<pre>
 
└── data
    ├── full_text <i># full-text data for cases from ECHR and CELLAR </i>
    ├── processed <i># data processed as result of the transformation scripts</i>
    └── raw <i># raw data extracted as result of the extractions scripts</i>
     
</pre>

### Usage 

```python
storage = Storage()
```

### Methods

- [`setup_pipeline`](#setup_pipeline): Setup the storage pipeline


#### `setup_pipeline`

Setup the paths for the files that need to be fetched in the pipeline. Ensures that the input files exist and throws an exception if the output paths already exist to ensure no data is overwritten and lost.  

##### Parameters

- 'output_paths': List of paths of output data
- 'input_path': List of paths to fetch input data
