# CI/CD Documentation

This directory contains the Continuous Integration and Continuous Deployment (CI/CD) configuration for the Case Law Explorer project.

## Overview

Our CI/CD pipeline is built using **GitHub Actions** and provides automated testing, linting, security scanning, and deployment capabilities.

## Workflows

### 1. CI Pipeline (`ci.yml`)

**Trigger**: Push to `main` or `develop`, Pull Requests

**Jobs**:

#### Lint
- Runs code formatting checks with Black
- Checks import sorting with isort
- Validates Python code style with Flake8
- Ensures code quality standards

#### Test
- Runs unit tests with pytest
- Generates code coverage reports
- Uploads coverage to Codecov

#### Validate DAGs
- Checks Airflow DAG syntax
- Ensures all DAGs can be parsed
- Validates DAG structure

#### Docker Build
- Tests Docker image building
- Verifies image can run successfully
- Caches Docker layers for faster builds

#### Security Scan
- Scans dependencies for known vulnerabilities (Safety)
- Runs security linting (Bandit)
- Generates security reports

#### Check Merge Conflicts
- Detects merge conflict markers
- Prevents merging conflicted code

#### Documentation
- Verifies required documentation files exist
- Checks for broken links in markdown files

#### Summary
- Aggregates all job results
- Provides clear pass/fail status
- Blocks merge on critical failures

**Status Badge**: Add to README
```markdown
![CI Pipeline](https://github.com/maastrichtlawtech/case-law-explorer/workflows/CI%20Pipeline/badge.svg)
```

---

### 2. Docker Image Publishing (`docker-publish.yml`)

**Trigger**: Git tags (e.g., `v1.0.0`), Releases

**Purpose**: Automatically builds and publishes Docker images to GitHub Container Registry

**Steps**:
1. Builds Docker image from `airflow/Dockerfile`
2. Tags image with version number
3. Pushes to `ghcr.io/maastrichtlawtech/case-law-explorer`
4. Generates build attestation for security

**Usage**:
```bash
# Pull published image
docker pull ghcr.io/maastrichtlawtech/case-law-explorer:v1.0.0

# Use in docker-compose
image: ghcr.io/maastrichtlawtech/case-law-explorer:latest
```

---

### 3. Dependency Review (`dependency-review.yml`)

**Trigger**: Pull Requests to `main` or `develop`

**Purpose**: Automatically reviews dependency changes for security and licensing issues

**Features**:
- Detects vulnerable dependencies
- Flags GPL-3.0 and AGPL-3.0 licenses
- Fails on moderate or higher severity issues

---

## Pre-commit Hooks

Configuration file: `.pre-commit-config.yaml`

### Installation

```bash
# Install pre-commit
pip install pre-commit

# Set up git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### Hooks Enabled

1. **General Checks**
   - Remove trailing whitespace
   - Fix end of file
   - Check YAML syntax
   - Detect large files (>1MB)
   - Detect private keys

2. **Python**
   - Black (code formatter)
   - isort (import sorter)
   - Flake8 (style checker)
   - pydocstyle (docstring checker)
   - Bandit (security)

3. **Docker**
   - hadolint (Dockerfile linter)

4. **Documentation**
   - Markdown linter
   - YAML formatter

5. **Security**
   - Secret detection

### Bypassing Hooks

```bash
# Skip hooks for a specific commit (not recommended)
git commit --no-verify -m "message"
```

---

## GitHub Templates

### Pull Request Template

Location: `.github/PULL_REQUEST_TEMPLATE.md`

**Sections**:
- Description of changes
- Type of change
- Related issues
- Testing performed
- Checklist for code quality, testing, documentation
- Deployment notes

**Usage**: Automatically loaded when creating a PR

---

### Issue Templates

#### Bug Report (`bug_report.md`)

**Use when**: Reporting a bug or error

**Includes**:
- Bug description
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Error messages and logs

#### Feature Request (`feature_request.md`)

**Use when**: Proposing new functionality

**Includes**:
- Feature description
- Problem statement
- Proposed solution
- Use cases
- Implementation considerations

---

## Configuration Files

### `.bandit.yml`

Bandit security scanner configuration

**Key Settings**:
- Excludes test directories
- Skips overly strict tests (e.g., asserts)
- Medium severity and confidence levels

### `.pre-commit-config.yaml`

Pre-commit hooks configuration

**Key Settings**:
- Python 3.11 as target version
- Line length: 100 characters
- Black profile for isort
- Google convention for docstrings

---

## CI/CD Best Practices

### For Contributors

1. **Before Committing**
   ```bash
   # Run pre-commit checks
   pre-commit run --all-files
   
   # Run tests locally
   pytest tests/
   
   # Validate DAGs
   python airflow/dags/your_dag.py
   ```

2. **Creating Pull Requests**
   - Fill out PR template completely
   - Ensure all CI checks pass
   - Request review from maintainers
   - Address review comments promptly

3. **Resolving CI Failures**
   - Check workflow logs in GitHub Actions
   - Fix issues locally and push updates
   - Re-run failed jobs if transient failure

### For Maintainers

1. **Merging Pull Requests**
   - Require all checks to pass
   - Use "Squash and merge" for clean history
   - Delete branch after merge

2. **Creating Releases**
   ```bash
   # Create and push tag
   git tag -a v1.0.0 -m "Release version 1.0.0"
   git push origin v1.0.0
   
   # This triggers docker-publish workflow
   ```

3. **Monitoring CI/CD**
   - Check GitHub Actions regularly
   - Review security scan results
   - Update dependencies periodically

---

## Troubleshooting CI/CD

### Issue: Workflow not triggering

**Cause**: Workflow file syntax error or wrong branch

**Solution**:
1. Validate YAML syntax
2. Check branch filters in `on:` section
3. Ensure workflow is on correct branch

---

### Issue: Docker build fails

**Cause**: Dockerfile errors or dependency issues

**Solution**:
1. Check Dockerfile syntax
2. Verify requirements.txt has compatible versions
3. Test build locally:
   ```bash
   cd airflow
   docker build -t test .
   ```

---

### Issue: Pre-commit hooks too slow

**Cause**: Running on large codebase

**Solution**:
1. Use `--files` flag for specific files
2. Skip hooks for large files
3. Configure hook to run on changed files only

---

### Issue: Flake8 errors

**Common Errors**:
- E501: Line too long (max 100 chars)
- E203: Whitespace before ':'
- W503: Line break before binary operator

**Solution**:
```bash
# Auto-fix with black
black airflow/dags/

# Check remaining issues
flake8 airflow/dags/
```

---

## Future Improvements

### Planned Enhancements

1. **Testing**
   - Add comprehensive unit tests
   - Implement integration tests
   - Add E2E tests for DAGs

2. **Deployment**
   - Add staging environment
   - Implement blue-green deployment
   - Add rollback automation

3. **Monitoring**
   - Integrate with monitoring tools
   - Add performance benchmarks
   - Track deployment metrics

4. **Security**
   - Add SAST (Static Application Security Testing)
   - Implement secret scanning
   - Add container scanning

---

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Black Code Formatter](https://black.readthedocs.io/)
- [Flake8 Style Guide](https://flake8.pycqa.org/)
- [Bandit Security](https://bandit.readthedocs.io/)

---

## Support

For issues with CI/CD:
1. Check workflow logs in GitHub Actions
2. Review this documentation
3. Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md)
4. Create an issue using the bug report template

---

*Last Updated: October 2025*


