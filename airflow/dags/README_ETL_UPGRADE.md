# ETL DAGs Upgrade Documentation

## Overview

The case law extraction system now uses robust, parallel-safe ETL DAGs for Rechtspraak, ECHR, and Cellar. Extraction logic is centralized in parameterized functions, and all code follows best practices for modularity and maintainability.

## New ETL DAGs

### 1. Rechtspraak ETL (`rechtspraak_etl.py`)
- **DAG ID**: `rechtspraak_etl`
- **Description**: Monthly task groups for Rechtspraak data extraction, transformation, and loading
- **Features**: 
  - Calls the centralized, parameterized `rechtspraak_extract` function for each month
  - Passes a unique output directory for each month, ensuring parallel safety
  - Receives output file paths from extraction, then transforms and loads
  - All imports are at the top of the file, following best practices

### 2. ECHR ETL (`echr_etl.py`)
- **DAG ID**: `echr_etl`
- **Description**: Monthly task groups for ECHR data extraction, transformation, and loading
- **Features**:
  - Uses a similar pattern: parameterized extraction, then transform, then load
  - Parallel-safe and modular

### 3. Cellar ETL (`cellar_etl.py`)
- **DAG ID**: `cellar_etl`
- **Description**: Monthly task groups for Cellar data extraction, transformation, and loading
- **Features**:
  - Uses a similar pattern: parameterized extraction, then transform, then load
  - Parallel-safe and modular

## Centralized Extraction Logic

### `rechtspraak_extract` (in `rechtspraak_extraction.py`)
- Accepts `starting_date`, `ending_date`, `amount`, `output_dir`, and `skip_if_exists`.
- Writes all outputs (base, metadata, citations) to the specified `output_dir`.
- Checks for file existence and skips extraction if outputs already exist.
- Returns a dictionary with paths to the output files.
- **Parallel-safe:** Each call writes to its own directory, so multiple months can be processed in parallel.
- **All imports are at the top of the file, following PEP8 best practices.**

#### Example Usage in a DAG
```python
from data_extraction.caselaw.rechtspraak.rechtspraak_extraction import rechtspraak_extract

def rechtspraak_etl(**kwargs):
    start_date = kwargs["start_date"]
    end_date = kwargs["end_date"]
    month_dir = os.path.join(_raw_data_path, start_date.strftime("%Y-%m-%d"))
    result_paths = rechtspraak_extract(
        starting_date=start_date.strftime("%Y-%m-%d"),
        ending_date=end_date.strftime("%Y-%m-%d"),
        amount=eval(Variable.get('RS_AMOUNT_TO_EXTRACT')),
        output_dir=month_dir,
        skip_if_exists=True
    )
    # result_paths['citations'], result_paths['metadata'], result_paths['base']
    # ... proceed with transformation and loading ...
```

## Required Airflow Variables

### For Rechtspraak ETL:
```bash
RS_START_DATE: "2023-01-01"
RS_END_DATE: "2023-12-31"
RS_AMOUNT_TO_EXTRACT: "1000"
DATA_PATH: "/path/to/data"
```

### For ECHR ETL:
```bash
ECHR_START_DATE: "2023-01-01"
ECHR_END_DATE: "2023-12-31"
ECHR_AMOUNT_TO_EXTRACT: "1000"
DATA_PATH: "/path/to/data"
```

### For Cellar ETL:
```bash
CELLAR_START_DATE: "2023-01-01"
CELLAR_END_DATE: "2023-12-31"
CELLAR_AMOUNT_TO_EXTRACT: "1000"
DATA_PATH: "/path/to/data"
```

## How to Use

### 1. Setting up Airflow Variables
Set the required variables in Airflow UI or via CLI:

```bash
# Example for setting variables via CLI
airflow variables set RS_START_DATE "2023-01-01"
airflow variables set RS_END_DATE "2023-12-31"
airflow variables set RS_AMOUNT_TO_EXTRACT "1000"
airflow variables set DATA_PATH "/opt/airflow/data"
```

### 2. Running the DAGs
1. Go to Airflow UI
2. Navigate to DAGs
3. Find the appropriate ETL DAG (e.g., `rechtspraak_etl`)
4. Click "Trigger DAG" to start the full pipeline

### 3. Individual Task Retriggering
If a specific month fails:
1. Go to the DAG run in Airflow UI
2. Navigate to the failed task (e.g., `rechtspraak_etl_2023-03`)
3. Click "Clear" to mark the task as failed
4. Click "Retry" to retrigger only that specific month

## Task Structure

Each ETL DAG creates tasks in the following format:
- `{source}_etl_YYYY-MM` (e.g., `rechtspraak_etl_2023-03`)

Each task performs:
1. **Extraction**: Downloads data for the specific month using a parallel-safe, parameterized function
2. **Transformation**: Cleans and transforms the data
3. **Loading**: Uploads to DynamoDB and other storage

## Benefits of the New Structure

1. **Granular Control**: Individual months can be retriggered without affecting others
2. **Better Error Handling**: Failures are isolated to specific months
3. **Improved Monitoring**: Each month's progress can be tracked separately
4. **Resource Efficiency**: Failed months can be retried without reprocessing successful ones
5. **Parallel Processing**: Multiple months can potentially run in parallel (depending on resources)
6. **Centralized, maintainable extraction logic**

## Migration from Old DAGs

The old extraction DAGs have been deprecated:
- `echr_extraction.py` → `echr_etl.py`
- `cellar_extraction.py` → `cellar_etl.py`
- `rechtspraak_etl.py` (updated with improved structure)

The old DAGs will show deprecation notices and should not be used for new runs.

## Troubleshooting

### Common Issues:

1. **Missing Variables**: Ensure all required Airflow variables are set
2. **Date Format**: Use YYYY-MM-DD format for dates
3. **Data Path**: Ensure the DATA_PATH variable points to a valid directory
4. **Permissions**: Ensure the Airflow user has write permissions to the data directory
5. **Linter Warnings**: If you see linter warnings about missing libraries (e.g., pandas, airflow, dotenv), these are environment issues and do not indicate code errors. Make sure your environment has all required dependencies installed.

### Debugging Individual Tasks:
1. Check the task logs in Airflow UI
2. Verify the specific month's data files exist
3. Check for any file permission issues
4. Review the extraction arguments being passed

## Example Usage

```python
# Example of how the monthly tasks are created
def create_tasks():
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 12, 31)
    
    with TaskGroup("rechtspraak_etl_tasks") as task_group:
        current_date = start_date
        while current_date <= end_date:
            month_end = get_month_end(current_date)
            
            PythonOperator(
                task_id=f"rechtspraak_etl_{current_date.strftime('%Y-%m')}",
                python_callable=rechtspraak_etl,
                op_kwargs={
                    "start_date": current_date,
                    "end_date": month_end,
                    "_data_path": Variable.get("DATA_PATH"),
                }
            )
            
            current_date = month_end + timedelta(days=1)
```

**Note:** Always pass a unique output directory for each parallel extraction to avoid file conflicts.

This structure provides much better control and reliability for the case law extraction process. 