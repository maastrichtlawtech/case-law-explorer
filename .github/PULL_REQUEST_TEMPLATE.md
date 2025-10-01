# Pull Request

## Description
<!-- Provide a brief description of the changes in this PR -->

## Type of Change
<!-- Mark the relevant option with an "x" -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] CI/CD improvement

## Related Issues
<!-- Link to related issues using #issue_number -->

Fixes #
Related to #

## Changes Made
<!-- List the main changes made in this PR -->

- 
- 
- 

## Testing
<!-- Describe the tests you ran and how to reproduce them -->

### Test Configuration:
- **Python Version**: 
- **Airflow Version**: 
- **OS**: 

### Tests Run:
- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing
- [ ] DAG validation

### Test Results:
<!-- Paste relevant test results or screenshots -->

```
# Test output here
```

## Checklist
<!-- Mark completed items with an "x" -->

### Code Quality
- [ ] My code follows the project's coding standards
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings or errors
- [ ] No merge conflicts exist

### Testing
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] I have tested this locally with Docker

### Documentation
- [ ] I have updated the README.md (if needed)
- [ ] I have updated ARCHITECTURE.md (if architecture changed)
- [ ] I have updated TROUBLESHOOTING.md (if adding new error scenarios)
- [ ] I have updated GLOSSARY.md (if adding new terms)
- [ ] Docstrings have been added/updated for new functions

### Dependencies
- [ ] I have added/updated dependencies in requirements.txt
- [ ] I have verified all dependencies are compatible
- [ ] No security vulnerabilities in new dependencies

### Data & Configuration
- [ ] I have updated .env.example (if new env vars added)
- [ ] No sensitive data (credentials, keys) is committed
- [ ] Database schema changes are backward compatible (if applicable)

### Airflow Specific (if DAG changes)
- [ ] DAGs can be parsed without errors
- [ ] DAG names follow naming conventions
- [ ] Task IDs are descriptive and follow conventions
- [ ] Proper error handling is implemented
- [ ] Retry logic is configured appropriately
- [ ] Logging is implemented

## Screenshots (if applicable)
<!-- Add screenshots to demonstrate UI changes or results -->

## Additional Notes
<!-- Any additional information that reviewers should know -->

## Reviewer Notes
<!-- For reviewers - what should they focus on? -->

### Areas of Focus:
- 
- 

### Questions for Reviewers:
- 
- 

---

## Deployment Notes
<!-- Information needed for deployment -->

### Pre-deployment:
- [ ] Database migrations needed
- [ ] New environment variables to set
- [ ] Configuration changes required

### Post-deployment:
- [ ] Monitoring to watch
- [ ] Expected behavior changes
- [ ] Rollback procedure documented

## Performance Impact
<!-- Describe any performance implications -->

- [ ] No significant performance impact
- [ ] Performance improvement expected
- [ ] Performance degradation possible (explain below)

**Details**: 

---

**By submitting this PR, I confirm that:**
- [ ] I have read and followed the [Contributing Guidelines](CONTRIBUTING.md)
- [ ] This PR is ready for review
- [ ] All CI checks are passing

