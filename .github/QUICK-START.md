# CI/CD Quick Start

## TL;DR
Feature branch → PR to `stage` → CI runs → Core tests pass → Merge to `release` → Merge to `main`

## View CI Status
🔗 https://github.com/dannxevans/theo/actions

## What Gets Tested

| Test Suite | Pass Rate | CI Status |
|------------|-----------|-----------|
| Backend Core/Memory | 97.8% | ✅ BLOCKS merge |
| Backend Routes | 39.5% | ℹ️ Informational |
| Frontend | 57.6% | ℹ️ Informational |

## Run Tests Locally

### Backend (Required)
```bash
cd backend
pip install -e .
pytest tests/memory tests/core -v
```

### Frontend (Optional)
```bash
cd frontend
npm ci
npm test
```

## Fix CI Failures

1. Click the red ❌ in your PR
2. Click "Details" next to failed check
3. Read the error logs
4. Fix locally and push again

## Branching Strategy

```
feature/* → stage → release → main
  (dev)     (test)  (pre-prod) (prod)
```

**CI triggers:**
- PRs to `stage` → Tests run (required)
- Push to `release`, `main` → Docker builds only (tests already passed on stage)

**See:** [BRANCHING.md](BRANCHING.md) for full workflow

## Enable Branch Protection

**Settings → Branches → Add rule:**
- Pattern: `stage` (test environment)
  - ☑ Require status checks: "Backend Core Tests"
- Pattern: `release` (pre-production)
  - ☑ Require status checks: "Backend Core Tests"
  - ☑ Require review: 1 approval
- Pattern: `main` (production)
  - ☑ Require status checks: "Backend Core Tests"
  - ☑ Require review: 1 approval

## Common Issues

**Module not found:**
- Check `pip install -e .` is in requirements

**Tests timeout:**
- Increase timeout in workflow (default: 10 min)

**Docker push fails:**
- Settings → Actions → General → Read/write permissions

## Files Added

```
.github/
├── workflows/
│   ├── ci.yml              # Main CI (stage/release/main)
│   ├── backend-tests.yml   # Python matrix
│   ├── frontend-tests.yml  # Node matrix
│   ├── docker-build.yml    # Container builds (release/main)
│   └── README.md           # Detailed docs
├── BRANCHING.md            # Branching strategy guide
├── CI-SETUP.md             # Full setup guide
└── QUICK-START.md          # This file
```

## Badge in README

```markdown
![CI](https://github.com/dannxevans/theo/actions/workflows/ci.yml/badge.svg)
```

Already added! ✅

---

**Need help?** See [CI-SETUP.md](CI-SETUP.md) for full documentation.
