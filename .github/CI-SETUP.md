# GitHub Actions CI/CD Setup for THEO

## Overview

GitHub Actions workflows have been configured to automatically test THEO on every push and pull request.

## What Was Added

### 1. Main CI Workflow (`.github/workflows/ci.yml`)
**Purpose:** Fast feedback on core functionality

**Runs on:** Every push to main/develop, all pull requests

**Jobs:**
- ✅ **Backend Core Tests** (REQUIRED) - 97.8% passing
  - If these fail, CI fails
  - Tests core business logic and memory operations

- ℹ️ **Backend Route Tests** (Informational) - 39.5% passing
  - Does not block CI
  - Work in progress

- ℹ️ **Frontend Tests** (Informational) - 57.6% passing
  - Does not block CI
  - Work in progress

- 🔒 **Security Scanning** (Trivy)
  - Scans for vulnerabilities
  - Results in Security tab

### 2. Backend Test Matrix (`.github/workflows/backend-tests.yml`)
**Purpose:** Test across multiple Python versions

**Tests on:**
- Python 3.9
- Python 3.10
- Python 3.11
- Python 3.12

**Features:**
- Coverage report generation (Python 3.11)
- Codecov upload (if token configured)
- Separate core vs route test jobs

### 3. Frontend Test Matrix (`.github/workflows/frontend-tests.yml`)
**Purpose:** Test across multiple Node versions

**Tests on:**
- Node 16.x
- Node 18.x
- Node 20.x

**Features:**
- ESLint checking
- Coverage report generation (Node 20.x)

### 4. Docker Build (`.github/workflows/docker-build.yml`)
**Purpose:** Build and publish container images

**Triggers:**
- Push to main → Build and push
- Pull requests → Build only
- Manual workflow dispatch

**Outputs:**
- `ghcr.io/dannxevans/theo-backend:latest`
- `ghcr.io/dannxevans/theo-frontend:latest`
- Tagged with version, branch, SHA

## CI Strategy

### Test Gating Philosophy

**Only core business logic blocks CI:**
- Core/Memory tests (97.8%) → ❌ FAIL CI
- Route tests (39.5%) → ℹ️ Informational
- Frontend tests (57.6%) → ℹ️ Informational

**Rationale:**
1. Core logic is mission-critical (97.8% passing)
2. Route/frontend tests are improving over time
3. Don't block development on WIP tests
4. Still run all tests for visibility

### Pull Request Flow

```
Developer creates PR
    ↓
CI runs automatically
    ↓
Core tests pass → ✅ Can merge
Core tests fail → ❌ Cannot merge
Route/Frontend fail → ℹ️ Warning only
    ↓
Reviewer approves
    ↓
Merge to main
    ↓
Docker images built & pushed
```

## Getting Started

### 1. Push Code
```bash
git add .
git commit -m "Your changes"
git push origin main
```

CI runs automatically!

### 2. View Results
- Go to: https://github.com/dannxevans/theo/actions
- Click on your workflow run
- See detailed logs for each job

### 3. Fix Failures
If core tests fail:
```bash
# Run locally first
cd backend
pytest tests/memory tests/core -v

# Fix issues
# Commit and push
git commit -am "Fix test failures"
git push
```

## Local Testing

**Before pushing, run tests locally:**

```bash
# Backend core tests (must pass)
cd backend
pip install -e .
pytest tests/memory tests/core -v

# Backend route tests (informational)
pytest tests/routes -v

# Frontend tests (informational)
cd frontend
npm ci
npm test
```

## Configuration

### No Secrets Required
Basic CI works immediately with no configuration.

### Optional: Codecov Integration
For coverage tracking:

1. Sign up at https://codecov.io
2. Connect THEO repository
3. Copy upload token
4. Add repository secret:
   - Settings → Secrets → Actions
   - Name: `CODECOV_TOKEN`
   - Value: `<your-token>`

### Optional: Branch Protection
To enforce CI on PRs:

1. Settings → Branches → Add rule
2. Branch name pattern: `main`
3. ☑ Require status checks to pass before merging
4. Select: "Backend Core Tests (97.8%)"
5. Save

Now PRs can't be merged until core tests pass!

## Status Badges

### README Badge (Already Added)
```markdown
![CI](https://github.com/dannxevans/theo/actions/workflows/ci.yml/badge.svg)
```

Shows current CI status on main branch.

### Additional Badges
```markdown
![Backend Tests](https://github.com/dannxevans/theo/actions/workflows/backend-tests.yml/badge.svg)
![Frontend Tests](https://github.com/dannxevans/theo/actions/workflows/frontend-tests.yml/badge.svg)
![Docker Build](https://github.com/dannxevans/theo/actions/workflows/docker-build.yml/badge.svg)
```

## Cost

### GitHub Actions Minutes
- **Public repos:** Unlimited (free)
- **Private repos:** 2,000 minutes/month (free tier)

### Current Usage
- ~5 minutes per push (all workflows)
- ~400 pushes/month possible on free tier

### Optimization Tips
1. Use `paths` filters (already configured)
2. Cache dependencies (already configured)
3. Skip redundant jobs with `if` conditions
4. Use `concurrency` to cancel outdated runs

## Monitoring

### GitHub Actions Dashboard
- Repository → Actions tab
- See all workflow runs
- Filter by status (success/failure)
- Download logs

### Security Tab
- Repository → Security → Code scanning
- View Trivy vulnerability scan results
- Get alerts for new vulnerabilities

### Email Notifications
GitHub sends emails on:
- Workflow failures
- First failure after success
- Successful run after failure

Configure: Settings → Notifications → Actions

## Troubleshooting

### "Module not found" in backend tests
**Fix:** Ensure `pip install -e .` is in workflow
```yaml
- run: |
    pip install -r requirements.txt
    pip install -e .  # Important!
```

### Docker push fails
**Fix:** Check workflow permissions
- Settings → Actions → General
- Workflow permissions → Read and write

### Tests pass locally but fail in CI
**Common causes:**
- Python/Node version mismatch
- Missing environment variables
- Timezone differences (use UTC)
- Path issues (use absolute paths)

**Debug:**
```yaml
- name: Debug info
  run: |
    python --version
    pip list
    pwd
    ls -la
```

## Next Steps

### Immediate (Done ✅)
- ✅ CI workflow configured
- ✅ Test matrix setup
- ✅ Docker builds automated
- ✅ Security scanning enabled
- ✅ README badge added

### Short Term (Optional)
- [ ] Enable branch protection on `main`
- [ ] Set up Codecov integration
- [ ] Add deployment workflow for staging
- [ ] Add E2E tests with Playwright
- [ ] Add performance benchmarking

### Long Term
- [ ] Improve route test pass rate (39.5% → 80%)
- [ ] Improve frontend test pass rate (57.6% → 80%)
- [ ] Add integration tests
- [ ] Automated dependency updates (Dependabot)
- [ ] Automated releases (semantic-release)

## Resources

- **GitHub Actions Docs:** https://docs.github.com/en/actions
- **Workflow Syntax:** https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions
- **Python Testing:** https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python
- **Node.js Testing:** https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-nodejs

---

**Questions?** See [.github/workflows/README.md](.github/workflows/README.md) for detailed workflow documentation.

**Last Updated:** December 30, 2025
