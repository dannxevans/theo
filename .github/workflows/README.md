# GitHub Actions Workflows

This directory contains CI/CD workflows for THEO.

## Workflows

### `ci.yml` - Main CI Pipeline
**Triggers:** Push to main/develop, Pull Requests

**What it does:**
- ✅ **Backend Core Tests** (97.8% passing) - **REQUIRED TO PASS**
  - Runs core business logic and memory tests
  - Fails CI if these tests fail

- ℹ️ **Backend Route Tests** (39.5% passing) - Informational
  - Runs API route tests
  - Does not fail CI (work in progress)

- ℹ️ **Frontend Tests** (57.6% passing) - Informational
  - Runs Svelte component tests
  - Does not fail CI (work in progress)

- 🔒 **Security Scanning**
  - Trivy vulnerability scanner
  - Uploads results to GitHub Security tab

**Usage:**
```bash
# CI runs automatically on push/PR
git push origin main

# View results at:
# https://github.com/dannxevans/theo/actions
```

### `backend-tests.yml` - Backend Test Matrix
**Triggers:** Push/PR affecting backend code

**What it does:**
- Tests against Python 3.9, 3.10, 3.11, 3.12
- Runs core/memory tests (must pass)
- Runs route tests (informational)
- Generates coverage report (Python 3.11 only)
- Uploads to Codecov (if token configured)

**Configuration:**
```yaml
# Set CODECOV_TOKEN secret for coverage reports
# Settings → Secrets → Actions → New secret
# Name: CODECOV_TOKEN
# Value: <token from codecov.io>
```

### `frontend-tests.yml` - Frontend Test Matrix
**Triggers:** Push/PR affecting frontend code

**What it does:**
- Tests against Node 16.x, 18.x, 20.x
- Runs Vitest tests
- Runs ESLint (if configured)
- Generates coverage report (Node 20.x only)

### `docker-build.yml` - Container Image Building
**Triggers:**
- Push to main (builds and pushes)
- Pull requests (build only, no push)
- Manual trigger via workflow_dispatch

**What it does:**
- Builds backend Docker image
- Builds frontend Docker image
- Pushes to GitHub Container Registry (GHCR)
- Tags images with:
  - `latest` (main branch)
  - `<branch-name>` (other branches)
  - `v1.2.3` (version tags)
  - Git SHA

**Image URLs:**
- Backend: `ghcr.io/dannxevans/theo-backend:latest`
- Frontend: `ghcr.io/dannxevans/theo-frontend:latest`

**Pull images:**
```bash
docker pull ghcr.io/dannxevans/theo-backend:latest
docker pull ghcr.io/dannxevans/theo-frontend:latest
```

## CI Strategy

### Test Gating
Only **core business logic tests** (97.8% passing) are required to pass:
- ✅ Core/Memory tests → **FAIL CI if fail**
- ℹ️ Route tests → Informational only
- ℹ️ Frontend tests → Informational only

This ensures critical functionality works while allowing WIP tests to improve over time.

### Pull Request Checks
When you create a PR, GitHub will run:
1. Backend core tests (required ✅)
2. Backend route tests (optional ℹ️)
3. Frontend tests (optional ℹ️)
4. Security scan (optional 🔒)

**PR can be merged if:**
- Core/memory tests pass (182/186)
- Other checks can fail without blocking

### Branch Protection (Optional)
To enforce CI checks, enable branch protection:

**Settings → Branches → Add rule:**
```
Branch name pattern: main
☑ Require status checks to pass before merging
  ☑ Backend Core Tests (97.8%)
☐ Do not require route/frontend tests
☑ Require branches to be up to date before merging
```

## Local Testing

Run the same tests locally before pushing:

### Backend
```bash
cd backend

# Install package
pip install -e .

# Run core tests (must pass)
pytest tests/memory tests/core -v

# Run route tests (informational)
pytest tests/routes -v

# Run all with coverage
pytest --cov=core --cov=memory --cov-report=html
open htmlcov/index.html
```

### Frontend
```bash
cd frontend

# Install dependencies
npm ci

# Run tests
npm test

# Run with coverage
npm run test:coverage
```

## Viewing Results

### GitHub Actions Tab
1. Go to repository → Actions tab
2. Click on any workflow run
3. Expand job steps to see details

### Status Badges
Add to README:
```markdown
![CI](https://github.com/dannxevans/theo/actions/workflows/ci.yml/badge.svg)
![Backend Tests](https://github.com/dannxevans/theo/actions/workflows/backend-tests.yml/badge.svg)
![Docker Build](https://github.com/dannxevans/theo/actions/workflows/docker-build.yml/badge.svg)
```

### Security Tab
- Go to Security → Code scanning alerts
- View Trivy vulnerability scan results
- Filter by severity (Critical, High, Medium, Low)

## Secrets Configuration

### Required Secrets
None - basic CI works without any secrets.

### Optional Secrets
**CODECOV_TOKEN** (for coverage tracking)
1. Sign up at [codecov.io](https://codecov.io)
2. Connect your GitHub repo
3. Copy the upload token
4. Add as repository secret:
   - Settings → Secrets → Actions → New secret
   - Name: `CODECOV_TOKEN`
   - Value: `<token>`

**GITHUB_TOKEN** (automatically provided)
- Used for Docker image pushes to GHCR
- No configuration needed

## Cost
- ✅ **Free** for public repositories
- ✅ **2,000 minutes/month** free for private repos
- Current usage: ~5 minutes per push

## Troubleshooting

### CI fails with "Module not found"
**Solution:**
```yaml
# Ensure pip install -e . is run
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -e .  # ← Important!
```

### Docker build fails with permissions
**Solution:**
1. Go to Settings → Actions → General
2. Under "Workflow permissions":
   - Select "Read and write permissions"
   - ☑ Allow GitHub Actions to create and approve pull requests

### Tests pass locally but fail in CI
**Common causes:**
- Different Python/Node versions
- Missing environment variables
- Path differences (use `working-directory`)
- Timezone differences (use UTC)

### Codecov upload fails
**Solution:**
- Check CODECOV_TOKEN is set correctly
- Verify coverage.xml file is generated
- Set `fail_ci_if_error: false` to continue even if upload fails

## Future Improvements

- [ ] Add E2E tests with Playwright
- [ ] Add integration tests with real database
- [ ] Add performance benchmarking
- [ ] Add automated dependency updates (Dependabot)
- [ ] Add automated release creation
- [ ] Add deployment to staging environment
- [ ] Add smoke tests against production

---

**Last Updated:** December 30, 2025
