# Branching Strategy & CI Workflow

## Branch Structure

THEO uses a **three-tier branching strategy** for quality gates:

```
Developer Branch → stage → release (main)
   (feature)       (test)  (production)
```

### Branches

| Branch | Purpose | CI Tests | Docker Builds | Auto-Deploy |
|--------|---------|----------|---------------|-------------|
| `feature-*` | Active development | ❌ No | ❌ No | ❌ No |
| `stage` | Integration testing | ✅ Yes | ❌ No | 🔶 Staging (future) |
| `release` | Pre-production | ❌ No* | ✅ Yes | 🔶 Staging (future) |
| `main` | Production | ❌ No* | ✅ Yes | 🔶 Production (future) |

*Tests already passed on `stage` - no need to re-run

### Workflow

```
1. Local Development
   ├─ Create feature branch: git checkout -b feature/my-feature
   ├─ Make changes and commit locally
   ├─ Test locally: pytest tests/memory tests/core
   └─ Push to GitHub: git push origin feature/my-feature

2. Stage Integration
   ├─ Create PR: feature/my-feature → stage
   ├─ CI runs automatically (tests must pass)
   ├─ Review changes in PR
   ├─ Merge to stage
   └─ Validate integration on stage branch

3. Release Preparation
   ├─ Create PR: stage → release
   ├─ CI runs + Docker images built
   ├─ Review all changes since last release
   ├─ Merge to release
   └─ Docker images pushed to GHCR

4. Production Deploy
   ├─ Create PR: release → main (optional)
   ├─ Final validation
   ├─ Merge to main
   └─ Production deployment (manual or automated)
```

## CI Behavior by Branch

### Feature Branches
**CI:** Does NOT run
- Work freely without triggering CI
- Test locally before creating PR
- CI runs when PR is opened to stage

### Stage Branch
**On Push/PR:**
- ✅ Backend core tests (must pass)
- ✅ Backend route tests (informational)
- ✅ Frontend tests (informational)
- ✅ Security scan
- ❌ Docker builds (not needed yet)

**Use Case:** Integration testing and validation - **ONLY branch where tests run**

### Release Branch
**On Push/PR:**
- ❌ Tests (already passed on stage)
- ✅ Docker images built and pushed
  - `theo-backend:release`
  - `theo-frontend:release`

**Use Case:** Pre-production validation with deployable artifacts

### Main Branch (Production)
**On Push/PR:**
- ❌ Tests (already passed on stage)
- ✅ Docker images built and pushed
  - `theo-backend:latest`
  - `theo-frontend:latest`
  - `theo-backend:v1.2.3` (if tagged)

**Use Case:** Production deployments

## Pull Request Flow

### 1. Feature → Stage
```bash
# On GitHub:
1. Go to Pull Requests → New
2. Base: stage ← Compare: feature/my-feature
3. Create PR
4. Wait for CI ✅
5. Review and merge
```

**CI Checks:**
- Backend Core Tests (97.8%) → MUST PASS ✅
- Backend Route Tests (39.5%) → Informational ℹ️
- Frontend Tests (57.6%) → Informational ℹ️

**Can Merge If:**
- Core tests pass
- Code reviewed (if required)

### 2. Stage → Release
```bash
# On GitHub:
1. Go to Pull Requests → New
2. Base: release ← Compare: stage
3. Create PR (includes all changes since last release)
4. Wait for Docker build ✅
5. Review and merge
```

**CI Checks:**
- ❌ Tests skipped (already passed on stage)
- ✅ Docker images built

**Docker Images Created:**
- `ghcr.io/dannxevans/theo-backend:release`
- `ghcr.io/dannxevans/theo-frontend:release`

**Can Merge If:**
- Docker builds succeed
- Manual validation in staging environment (optional)

### 3. Release → Main (Optional)
```bash
# On GitHub:
1. Go to Pull Requests → New
2. Base: main ← Compare: release
3. Create PR
4. Wait for Docker build ✅
5. Review and merge
```

**CI Checks:**
- ❌ Tests skipped (already passed on stage)
- ✅ Docker images built with `:latest` tag

**Docker Images Created:**
- `ghcr.io/dannxevans/theo-backend:latest`
- `ghcr.io/dannxevans/theo-frontend:latest`

## Example Development Cycle

### Scenario: Add new feature

```bash
# 1. Create feature branch
git checkout -b feature/add-google-calendar
git push -u origin feature/add-google-calendar

# 2. Develop locally
# ... make changes ...
pytest tests/memory tests/core  # Run tests locally
git commit -am "Add Google Calendar integration"
git push

# 3. Merge to stage (via PR)
# GitHub: Create PR feature/add-google-calendar → stage
# Wait for CI ✅
# Merge PR

# 4. Validate on stage
# Test the feature on stage branch
# If issues found, fix on feature branch and merge again

# 5. Merge to release (via PR)
# GitHub: Create PR stage → release
# Wait for CI + Docker build ✅
# Merge PR
# Docker images now available: theo-backend:release

# 6. Deploy to staging environment (manual)
docker pull ghcr.io/dannxevans/theo-backend:release
docker pull ghcr.io/dannxevans/theo-frontend:release
# Deploy and test

# 7. Merge to main (via PR)
# GitHub: Create PR release → main
# Wait for CI ✅
# Merge PR
# Docker images now available: theo-backend:latest

# 8. Deploy to production (manual)
docker pull ghcr.io/dannxevans/theo-backend:latest
docker pull ghcr.io/dannxevans/theo-frontend:latest
# Deploy to production
```

## Branch Protection Recommendations

### For `stage` Branch
**Settings → Branches → Add Rule:**
- Branch name pattern: `stage`
- ☑ Require pull request reviews (1 approval) - Optional
- ☑ Require status checks to pass:
  - ✅ Backend Core Tests (97.8%)
- ☑ Require branches to be up to date before merging

### For `release` Branch
**Settings → Branches → Add Rule:**
- Branch name pattern: `release`
- ☑ Require pull request reviews (1 approval) - Recommended
- ☑ Require status checks to pass:
  - ✅ **Validate Source Branch** (enforces PRs only from `stage`)
  - ✅ build-backend
  - ✅ build-frontend
- ☑ Require branches to be up to date before merging

### For `main` Branch
**Settings → Branches → Add Rule:**
- Branch name pattern: `main`
- ☑ Require pull request reviews (1 approval) - Recommended
- ☑ Require status checks to pass:
  - ✅ **Validate Source Branch** (enforces PRs only from `release`)
  - ✅ build-backend
  - ✅ build-frontend
- ☑ Require branches to be up to date before merging
- ☑ Include administrators (enforce for everyone)

## Docker Image Tags

### Automatic Tags
| Trigger | Tags Created |
|---------|--------------|
| Push to `release` | `release`, `release-<sha>` |
| Push to `main` | `latest`, `main`, `main-<sha>` |
| Tag `v1.2.3` | `v1.2.3`, `1.2`, `latest` |
| PR #123 | `pr-123` (build only, not pushed) |

### Tag Strategy
- **`:latest`** → Always points to main (production)
- **`:release`** → Always points to release branch (pre-prod)
- **`:stage`** → Not built (no Docker images for stage)
- **`:v1.2.3`** → Specific version (manual git tag)
- **`:main-abc123`** → Specific commit on main
- **`:release-def456`** → Specific commit on release

## Best Practices

### 1. Keep Feature Branches Short-Lived
- Work in small increments
- Merge to stage frequently (daily if possible)
- Delete feature branch after merge

### 2. Test Locally Before Pushing
```bash
# Backend
cd backend
pip install -e .
pytest tests/memory tests/core -v

# Frontend
cd frontend
npm ci
npm test
```

### 3. Use Descriptive Branch Names
```bash
✅ feature/add-google-calendar
✅ fix/login-timeout-bug
✅ refactor/memory-module
❌ my-changes
❌ test
❌ branch1
```

### 4. Write Clear PR Descriptions
```markdown
## What
Brief description of changes

## Why
Reason for the change

## Testing
- [ ] Core tests pass locally
- [ ] Tested feature manually
- [ ] No regressions found

## Related Issues
Closes #123
```

### 5. Sync Regularly
```bash
# Update stage from release (after hotfix)
git checkout stage
git pull origin stage
git merge release
git push origin stage

# Update release from main (after production hotfix)
git checkout release
git pull origin release
git merge main
git push origin release
```

## Hotfix Process

### Critical Production Bug

```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# 2. Fix and test locally
# ... make changes ...
pytest tests/memory tests/core

# 3. Merge to main (via PR)
# GitHub: Create PR hotfix/critical-bug → main
# Merge and deploy immediately

# 4. Backport to release
git checkout release
git merge main
git push origin release

# 5. Backport to stage
git checkout stage
git merge release
git push origin stage
```

## Rollback Strategy

### Rollback Production (main)
```bash
# Option 1: Revert commit
git checkout main
git revert <bad-commit-sha>
git push origin main

# Option 2: Reset to previous state
git checkout main
git reset --hard <good-commit-sha>
git push --force origin main  # ⚠️ Use with caution!

# Option 3: Deploy previous Docker image
docker pull ghcr.io/dannxevans/theo-backend:main-<previous-sha>
```

### Rollback Release
```bash
# Reset release to previous commit
git checkout release
git reset --hard <good-commit-sha>
git push --force origin release
```

## CI/CD Future Enhancements

### Planned
- [ ] Auto-deploy to staging on `release` merge
- [ ] Auto-deploy to production on `main` merge (with approval gate)
- [ ] Automated smoke tests after deployment
- [ ] Slack/Discord notifications on deploy
- [ ] Automated rollback on failed smoke tests

### Staging Environment Variables
```yaml
# .github/workflows/deploy-staging.yml (future)
on:
  push:
    branches: [ release ]

env:
  DEPLOY_ENV: staging
  AWS_REGION: eu-west-2
  ECS_CLUSTER: theo-staging
```

### Production Environment Variables
```yaml
# .github/workflows/deploy-production.yml (future)
on:
  push:
    branches: [ main ]

env:
  DEPLOY_ENV: production
  AWS_REGION: eu-west-2
  ECS_CLUSTER: theo-prod
```

---

**Questions?** See [CI-SETUP.md](CI-SETUP.md) for detailed CI documentation.

**Last Updated:** December 30, 2025
