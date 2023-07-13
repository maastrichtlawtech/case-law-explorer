# `Storage` Reference

The `Storage` API is the script that handles the storage of extracted files. It defines global directory paths and the terminology used throughout all data processing steps.

In both storage locations, the data directory follows the structure of:
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
