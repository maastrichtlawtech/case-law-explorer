# Troubleshooting Guide

A comprehensive guide to common issues and their solutions when working with the Case Law Explorer project.

## Table of Contents

- [Setup & Installation Issues](#setup--installation-issues)
- [Docker & Container Issues](#docker--container-issues)
- [Airflow Issues](#airflow-issues)
- [Extraction Issues](#extraction-issues)
- [Transformation Issues](#transformation-issues)
- [Loading Issues](#loading-issues)
- [AWS & Cloud Issues](#aws--cloud-issues)
- [Performance Issues](#performance-issues)
- [Data Quality Issues](#data-quality-issues)

---

## Setup & Installation Issues

### Issue: Cannot find `.env` file

**Error Message**: 
```
FileNotFoundError: .env file not found
```

**Cause**: The `.env` file hasn't been created or is in the wrong location.

**Solution**:
1. Copy the example file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your credentials
3. Ensure `.env` is in the project root directory
4. Verify it's not committed to git (should be in `.gitignore`)

**Prevention**: Always create `.env` file before starting the application.

---

### Issue: Missing Python dependencies

**Error Message**:
```
ModuleNotFoundError: No module named 'rechtspraak_extractor'
```

**Cause**: Required Python packages not installed.

**Solution**:
1. Ensure you're in the correct directory
2. Install requirements:
   ```bash
   pip install -r airflow/requirements.txt
   ```
3. If using Docker, rebuild containers:
   ```bash
   docker-compose build
   ```

**Prevention**: Always run `pip install -r requirements.txt` after pulling changes.

---

## Docker & Container Issues

### Issue: Airflow containers won't start

**Error Message**:
```
Error response from daemon: Conflict. Container name already exists
```

**Cause**: Old containers are still running or exist.

**Solution**:
1. Stop all containers:
   ```bash
   docker-compose down
   ```
2. Remove old containers:
   ```bash
   docker-compose down -v
   ```
3. Start fresh:
   ```bash
   docker-compose up -d
   ```

**Prevention**: Always use `docker-compose down` before `docker-compose up`.

---

### Issue: Port 8080 already in use

**Error Message**:
```
Error starting userland proxy: Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Cause**: Another application is using port 8080.

**Solution**:

**Option 1** - Stop the other application:
```bash
# Find what's using port 8080
lsof -i :8080
# Kill the process
kill -9 <PID>
```

**Option 2** - Change Airflow port:
1. Edit `docker-compose.yaml`
2. Find the webserver ports section:
   ```yaml
   ports:
     - "8081:8080"  # Change 8080 to 8081
   ```
3. Restart containers

---

### Issue: Permission denied errors in Docker

**Error Message**:
```
PermissionError: [Errno 13] Permission denied: '/opt/airflow/logs'
```

**Cause**: Wrong user permissions in Docker.

**Solution**:
1. Set correct AIRFLOW_UID in `.env`:
   ```bash
   echo "AIRFLOW_UID=$(id -u)" >> .env
   ```
2. Fix directory permissions:
   ```bash
   sudo chown -R $(id -u):$(id -g) airflow/logs airflow/data
   ```
3. Restart containers:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

---

### Issue: Docker containers running out of memory

**Error Message**:
```
WARNING!!!: Not enough memory available for Docker
```

**Cause**: Insufficient memory allocated to Docker.

**Solution**:
1. Increase Docker memory:
   - **Mac**: Docker Desktop → Preferences → Resources → Memory (set to 8GB+)
   - **Windows**: Docker Desktop → Settings → Resources → Memory
2. Reduce concurrent tasks in Airflow:
   - Edit `docker-compose.yaml`
   - Add environment variable:
     ```yaml
     AIRFLOW__CORE__PARALLELISM: 4
     AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG: 2
     ```

---

## Airflow Issues

### Issue: Airflow webserver won't start

**Error Message**:
```
airflow.exceptions.AirflowConfigException: error: cannot use sqlite with the CeleryExecutor
```

**Cause**: Configuration mismatch between executor and database.

**Solution**:
1. Check `docker-compose.yaml` has PostgreSQL configured
2. Verify environment variables:
   ```yaml
   AIRFLOW__CORE__EXECUTOR: CeleryExecutor
   AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@postgres/airflow
   ```
3. Initialize database:
   ```bash
   docker-compose run airflow-webserver airflow db init
   ```

---

### Issue: DAG not showing up in Airflow UI

**Cause**: Multiple possible causes:
1. Python syntax error in DAG file
2. Import error
3. DAG file not in correct directory
4. Scheduler hasn't picked it up yet

**Solution**:
1. Check DAG file for syntax errors:
   ```bash
   python airflow/dags/your_dag.py
   ```
2. Check Airflow logs:
   ```bash
   docker-compose logs airflow-scheduler | grep ERROR
   ```
3. Verify DAG is in `airflow/dags/` directory
4. Wait 30 seconds for scheduler to detect changes
5. Force refresh in UI (Admin → Pools → reload)

---

### Issue: Task stuck in "running" state

**Cause**: Task process crashed without reporting status.

**Solution**:
1. Check task logs in Airflow UI
2. Mark task as failed:
   - Click on task → Clear → Confirm
3. Check worker logs:
   ```bash
   docker-compose logs airflow-worker
   ```
4. Restart worker if necessary:
   ```bash
   docker-compose restart airflow-worker
   ```

---

### Issue: "Variable not found" error

**Error Message**:
```
KeyError: 'Variable RS_START_DATE does not exist'
```

**Cause**: Required Airflow variables not set.

**Solution**:
1. Set variables via Airflow UI:
   - Admin → Variables → Add Record
   - Key: `RS_START_DATE`
   - Value: `"2023-01-01"`

2. Or via CLI:
   ```bash
   docker-compose run airflow-webserver airflow variables set RS_START_DATE "2023-01-01"
   docker-compose run airflow-webserver airflow variables set RS_END_DATE "2023-12-31"
   docker-compose run airflow-webserver airflow variables set RS_AMOUNT_TO_EXTRACT "1000"
   docker-compose run airflow-webserver airflow variables set DATA_PATH "/opt/airflow/data"
   ```

**Required Variables**:
- `RS_START_DATE`
- `RS_END_DATE`
- `RS_AMOUNT_TO_EXTRACT`
- `CELLAR_START_DATE`
- `CELLAR_END_DATE`
- `CELLAR_AMOUNT_TO_EXTRACT`
- `DATA_PATH`

---

## Extraction Issues

### Issue: HTTP 403 Forbidden errors during extraction

**Error Message**:
```
requests.exceptions.HTTPError: 403 Client Error: Forbidden
```

**Cause**: 
1. Invalid credentials
2. Rate limiting
3. IP blocked
4. API access revoked

**Solution**:

**For LIDO API**:
1. Verify credentials in `.env`:
   ```bash
   LIDO_USERNAME=your-username
   LIDO_PASSWORD=your-password
   ```
2. Contact LIDO support for new credentials
3. Add retry logic with exponential backoff

**For EUR-Lex**:
1. Check EURLEX_WEBSERVICE_USERNAME and PASSWORD
2. Verify account is active
3. Implement rate limiting (max 10 requests/second)

**For Rechtspraak**:
1. Check if API endpoint changed
2. Verify user agent in requests
3. Add delay between requests (recommended: 1 second)

---

### Issue: SSL certificate verification failed

**Error Message**:
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Cause**: SSL certificate issues with source APIs.

**Current Workaround** (in code):
```python
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

**Better Solution** (recommended):
1. Update certificates:
   ```bash
   # Mac
   pip install --upgrade certifi
   
   # Ubuntu
   sudo apt-get update
   sudo apt-get install ca-certificates
   ```

2. Add certificate bundle to requests:
   ```python
   import requests
   response = requests.get(url, verify='/path/to/certfile')
   ```

**Security Note**: Disabling SSL verification is a security risk. Only use for testing.

---

### Issue: Extraction returns zero results

**Cause**: 
1. Wrong date range
2. No data available for period
3. API parameters incorrect

**Solution**:
1. Verify date range in Airflow variables
2. Check if date range is valid:
   - ECHR: Data from 1959 onwards
   - CJEU: Data from 1954 onwards
   - Rechtspraak: Data from 2000 onwards (limited before)
3. Check API endpoint in logs
4. Try smaller date range or amount
5. Verify credentials are working

---

### Issue: "ECLI not found in DynamoDB" during update

**Cause**: Case hasn't been loaded to database yet.

**Solution**:
1. Run base extraction first:
   ```bash
   # Trigger appropriate ETL DAG
   docker-compose run airflow-webserver airflow dags trigger rechtspraak_etl
   ```
2. Wait for extraction to complete
3. Run update DAG
4. Check `data/eclis_not_found.csv` for missing cases

---

## Transformation Issues

### Issue: Column mapping errors

**Error Message**:
```
KeyError: 'creator'
```

**Cause**: Source data format changed or column doesn't exist.

**Solution**:
1. Check raw data file for actual column names
2. Update field mapping in `definitions/mappings/attribute_name_maps.py`
3. Add error handling for missing columns:
   ```python
   if col in field_map and col in row:
       row_clean[field_map[col]] = row[col]
   ```

---

### Issue: Data type conversion errors

**Error Message**:
```
ValueError: invalid literal for int() with base 10: 'N/A'
```

**Cause**: Unexpected data values.

**Solution**:
1. Add data validation before conversion:
   ```python
   def safe_int_conversion(value):
       try:
           return int(value) if value and value != 'N/A' else None
       except ValueError:
           logging.warning(f"Could not convert {value} to int")
           return None
   ```
2. Update transformation functions in `data_transformation/utils.py`

---

### Issue: XML parsing errors

**Error Message**:
```
xml.etree.ElementTree.ParseError: mismatched tag
```

**Cause**: Malformed XML in source data.

**Solution**:
1. Add try-catch around XML parsing:
   ```python
   try:
       tree = ET.fromstring(xml_string)
   except ET.ParseError as e:
       logging.error(f"XML parse error: {e}")
       return None
   ```
2. Use lxml for more robust parsing:
   ```python
   from lxml import etree
   parser = etree.XMLParser(recover=True)
   tree = etree.fromstring(xml_string, parser)
   ```

---

## Loading Issues

### Issue: DynamoDB write errors

**Error Message**:
```
botocore.exceptions.ClientError: An error occurred (ValidationException)
```

**Cause**: 
1. Item size exceeds 400KB limit
2. Invalid attribute values
3. Wrong table schema

**Solution**:

**For item size issues**:
1. Move large text to S3
2. Store S3 reference in DynamoDB
3. Compress data before storing

**For validation errors**:
1. Check data types match schema
2. Ensure required attributes present
3. Validate ECLI format before insertion

**Debug**:
```python
import json
print(json.dumps(item, default=str))  # Check item structure
print(len(json.dumps(item)))  # Check size
```

---

### Issue: AWS credentials not found

**Error Message**:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Cause**: AWS credentials not configured properly.

**Solution**:
1. Check `.env` file has credentials:
   ```bash
   AWS_ACCESS_KEY_ID=your-key
   AWS_SECRET_ACCESS_KEY=your-secret
   AWS_REGION=eu-central-1
   ```

2. Verify Docker mounts `.env`:
   ```yaml
   volumes:
     - .env:/opt/airflow/.env
   ```

3. Test credentials:
   ```python
   import boto3
   client = boto3.client('dynamodb')
   print(client.list_tables())
   ```

---

### Issue: S3 bucket not found

**Error Message**:
```
botocore.exceptions.ClientError: The specified bucket does not exist
```

**Cause**: Bucket doesn't exist or wrong bucket name.

**Solution**:
1. Create bucket:
   ```python
   import boto3
   s3 = boto3.client('s3')
   s3.create_bucket(
       Bucket='your-bucket-name',
       CreateBucketConfiguration={'LocationConstraint': 'eu-central-1'}
   )
   ```

2. Verify bucket name in `.env` matches actual bucket
3. Check AWS region is correct

---

## AWS & Cloud Issues

### Issue: DynamoDB table doesn't exist

**Error Message**:
```
botocore.exceptions.ClientError: Requested resource not found
```

**Cause**: Table not created yet.

**Solution**:
1. Tables should be created automatically by the loader
2. Or create manually via AWS Console:
   - Service: DynamoDB
   - Create Table
   - Table name: from `.env` (e.g., `caselawexplorer-test`)
   - Partition key: `ecli` (String)
3. Verify table name in `.env` matches AWS

---

### Issue: AWS permissions errors

**Error Message**:
```
botocore.exceptions.ClientError: AccessDeniedException
```

**Cause**: IAM user lacks required permissions.

**Solution**:
1. Update IAM policy to include:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "dynamodb:*",
           "s3:*",
           "appsync:*"
         ],
         "Resource": "*"
       }
     ]
   }
   ```
2. Attach policy to IAM user
3. Wait 5 minutes for propagation

**Recommended**: Create specific policies for production (principle of least privilege).

---

## Performance Issues

### Issue: Extraction is very slow

**Cause**: 
1. Large date range
2. Rate limiting
3. Network latency
4. Sequential processing

**Solution**:
1. Reduce `AMOUNT_TO_EXTRACT` in Airflow variables
2. Split into smaller date ranges
3. Enable parallel month processing (already implemented)
4. Increase number of Airflow workers:
   ```yaml
   # docker-compose.yaml
   airflow-worker:
     deploy:
       replicas: 3
   ```

---

### Issue: Transformation takes too long

**Cause**: Large files, complex transformations.

**Solution**:
1. Process in chunks:
   ```python
   chunk_size = 1000
   for chunk in pd.read_csv(file, chunksize=chunk_size):
       process_chunk(chunk)
   ```
2. Use faster XML parser (lxml)
3. Optimize transformation functions
4. Profile code to find bottlenecks:
   ```python
   import cProfile
   cProfile.run('transform_data()')
   ```

---

### Issue: High memory usage

**Cause**: Loading entire files into memory.

**Solution**:
1. Use chunked reading:
   ```python
   for chunk in pd.read_csv(file, chunksize=10000):
       process(chunk)
   ```
2. Delete dataframes after use:
   ```python
   del large_df
   import gc
   gc.collect()
   ```
3. Increase Docker memory allocation
4. Process smaller date ranges

---

## Data Quality Issues

### Issue: Duplicate cases in database

**Cause**: Re-running extraction without cleanup.

**Solution**:
1. Use `skip_if_exists=True` in extraction functions
2. Implement upsert logic in loader:
   ```python
   table.put_item(
       Item=item,
       ConditionExpression='attribute_not_exists(ecli)'
   )
   ```
3. Query before insert to check existence

---

### Issue: Missing citation data

**Cause**: 
1. LIDO API errors
2. Cases too new
3. No citations exist

**Solution**:
1. Check LIDO credentials
2. Verify case is in LIDO database (may take months for new cases)
3. Check `citations_outgoing` field - empty set `{}` is valid
4. Re-run citation extraction:
   ```bash
   docker-compose run airflow-webserver airflow dags trigger update_citation_details
   ```

---

### Issue: Invalid ECLI format

**Cause**: Malformed ECLI in source data.

**Solution**:
1. Add validation:
   ```python
   def validate_ecli(ecli):
       pattern = r'^ECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:\w+$'
       return re.match(pattern, ecli) is not None
   ```
2. Log invalid ECLIs for manual review
3. Skip invalid records or attempt to fix:
   ```python
   if not validate_ecli(ecli):
       logging.warning(f"Invalid ECLI: {ecli}")
       continue
   ```

---

## Getting More Help

### Check Logs

**Airflow logs**:
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs airflow-scheduler
docker-compose logs airflow-worker

# Follow logs
docker-compose logs -f airflow-worker
```

**Task logs**:
- Airflow UI → DAGs → Click on DAG → Graph → Click on task → Logs

**Container logs**:
```bash
docker logs <container-id>
```

---

### Debug Mode

Enable debug logging in DAGs:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Community Support

- **GitHub Issues**: [github.com/maastrichtlawtech/case-law-explorer/issues](https://github.com/maastrichtlawtech/case-law-explorer/issues)
- **Check existing issues**: Someone may have had the same problem
- **Create new issue**: Include:
  - Error message
  - Steps to reproduce
  - Environment details (OS, Python version, Docker version)
  - Relevant logs

---

### Useful Commands

**Check Docker status**:
```bash
docker-compose ps
docker-compose top
```

**Restart specific service**:
```bash
docker-compose restart airflow-scheduler
```

**Rebuild after code changes**:
```bash
docker-compose build
docker-compose up -d
```

**Access Airflow shell**:
```bash
docker-compose run airflow-webserver bash
```

**Check Airflow configuration**:
```bash
docker-compose run airflow-webserver airflow config list
```

**Run Airflow commands**:
```bash
docker-compose run airflow-webserver airflow dags list
docker-compose run airflow-webserver airflow tasks list rechtspraak_etl
```

---

*Last Updated: October 2025*

**Still having issues?** Check [ARCHITECTURE.md](ARCHITECTURE.md) for system overview or [GLOSSARY.md](GLOSSARY.md) for term definitions.


