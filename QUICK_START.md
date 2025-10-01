# Quick Start Guide

Get the Case Law Explorer running in 5 minutes! ⚡

## Prerequisites

- ✅ Docker Desktop installed ([Download](https://www.docker.com/products/docker-desktop))
- ✅ Git installed
- ✅ 8GB+ RAM available
- ✅ 10GB+ free disk space

## Step 1: Clone Repository

```bash
git clone https://github.com/maastrichtlawtech/case-law-explorer.git
cd case-law-explorer
```

## Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your credentials (required fields marked in file)
nano .env
# or use your favorite editor: code .env, vim .env, etc.
```

### Minimal Configuration (for local testing)

If you just want to test locally without AWS:

```bash
# Required for Docker
AIRFLOW_UID=50000

# Required for Airflow
DATA_PATH=/opt/airflow/data

# Add dummy values for AWS (if not using cloud)
AWS_REGION=eu-central-1
DDB_TABLE_NAME=local-test
```

## Step 3: Start Services

```bash
# Start all services
docker-compose up -d

# Wait for services to initialize (~2 minutes)
# Check status
docker-compose ps
```

## Step 4: Access Airflow

1. Open browser: http://localhost:8080
2. Login:
   - **Username**: `airflow`
   - **Password**: `airflow`

## Step 5: Configure Airflow Variables

In Airflow UI:
1. Go to **Admin** → **Variables**
2. Add these variables:

| Key | Value | Description |
|-----|-------|-------------|
| `RS_START_DATE` | `"2023-01-01"` | Start date for Rechtspraak extraction |
| `RS_END_DATE` | `"2023-01-31"` | End date for Rechtspraak extraction |
| `RS_AMOUNT_TO_EXTRACT` | `"100"` | Number of cases to extract |
| `DATA_PATH` | `"/opt/airflow/data"` | Data storage path |

## Step 6: Run Your First DAG

1. In Airflow UI, go to **DAGs**
2. Find `rechtspraak_etl`
3. Click the **play button** (▶) to trigger
4. Watch the progress in the **Graph** view

## Troubleshooting Common Issues

### Port 8080 Already in Use

```bash
# Find and kill the process
lsof -i :8080
kill -9 <PID>
```

### Permission Errors

```bash
# Fix permissions
echo "AIRFLOW_UID=$(id -u)" >> .env
sudo chown -R $(id -u):$(id -g) airflow/logs airflow/data
docker-compose down
docker-compose up -d
```

### Containers Won't Start

```bash
# Clean restart
docker-compose down -v
docker-compose up -d
```

## What's Next?

### Learn More
- 📖 [Architecture Overview](ARCHITECTURE.md)
- 📚 [Technical Glossary](GLOSSARY.md)
- 🔧 [Troubleshooting Guide](TROUBLESHOOTING.md)
- 🚀 [Full ETL Documentation](docs/etl/README.md)

### Development Setup

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run checks
pre-commit run --all-files
```

### Extract Real Data

1. Get API credentials:
   - **LIDO**: Register at [linkeddata.overheid.nl](https://linkeddata.overheid.nl/)
   - **EUR-Lex**: Contact EUR-Lex for webservice access
   - **AWS** (optional): Create account at [aws.amazon.com](https://aws.amazon.com/)

2. Update `.env` with real credentials

3. Configure date ranges in Airflow variables

4. Run appropriate DAG:
   - `rechtspraak_etl` - Dutch case law
   - `echr_etl` - European Court of Human Rights
   - `cellar_etl` - Court of Justice of the European Union

## Useful Commands

### Docker

```bash
# View logs
docker-compose logs -f airflow-scheduler

# Restart a service
docker-compose restart airflow-webserver

# Stop everything
docker-compose down

# Remove everything including volumes
docker-compose down -v
```

### Airflow CLI

```bash
# List DAGs
docker-compose run airflow-webserver airflow dags list

# Test a task
docker-compose run airflow-webserver airflow tasks test rechtspraak_etl task_id 2023-01-01

# Set a variable
docker-compose run airflow-webserver airflow variables set KEY "VALUE"
```

## Data Locations

After running DAGs, data will be in:

```
airflow/data/
├── raw/              # Extracted data by date
│   └── 2023-01-01/
│       ├── RS_cases.csv
│       └── ...
├── processed/        # Transformed data
│   └── RS_cases_clean.csv
└── full_text/        # Full text documents
    └── *.json
```

## Health Checks

### Services Running?

```bash
docker-compose ps
```

All services should show "Up" status.

### Airflow Working?

- Webserver: http://localhost:8080
- Scheduler logs: `docker-compose logs airflow-scheduler`

### Database Connected?

```bash
docker-compose exec postgres psql -U airflow -d airflow -c "SELECT 1;"
```

Should return: `1`

## Getting Help

1. **Check Logs**: `docker-compose logs <service-name>`
2. **Read Documentation**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. **Search Issues**: [GitHub Issues](https://github.com/maastrichtlawtech/case-law-explorer/issues)
4. **Create Issue**: Use bug report template

## Common Workflows

### Daily Development

```bash
# Start
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Testing Changes

```bash
# Edit DAG file
nano airflow/dags/my_dag.py

# Validate syntax
python airflow/dags/my_dag.py

# Restart scheduler (picks up changes)
docker-compose restart airflow-scheduler

# Trigger DAG in UI
```

### Updating Code

```bash
# Pull latest changes
git pull

# Rebuild containers
docker-compose build

# Restart
docker-compose down
docker-compose up -d
```

## Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] Never commit real credentials
- [ ] Use strong passwords for Airflow UI
- [ ] Restrict AWS IAM permissions
- [ ] Keep dependencies updated

## Performance Tips

- **Limit extraction amount** when testing (e.g., 100 cases)
- **Use smaller date ranges** for faster processing
- **Increase Docker memory** to 8GB+ for better performance
- **Monitor disk space** - ETL can generate large files

## Success Indicators

✅ You're ready when:
- Airflow UI loads at http://localhost:8080
- All Docker containers are "Up"
- You can trigger a DAG
- Data appears in `airflow/data/` directory

---

**Need more help?** Check the full documentation in the `docs/` folder or create an issue!



