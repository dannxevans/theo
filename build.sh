#!/bin/bash
# Build script for THEO Docker images
# Usage: ./build.sh [version]
#
# Examples:
#   ./build.sh              # Auto-detect PR number or use commit SHA
#   ./build.sh pr-242       # Build with specific PR tag
#   ./build.sh latest       # Build with 'latest' tag

set -e

# Configuration
REGISTRY="ghcr.io"
OWNER="dannxevans"
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Try to extract PR number from latest merge commit
PR_NUMBER=$(git log -1 --pretty=%B | grep -oP 'Merge pull request #\K\d+' || echo "")

# Determine deploy tag
if [[ -n "$PR_NUMBER" ]]; then
  DEPLOY_TAG="pr-${PR_NUMBER}"
  echo "🔍 Detected PR merge: #${PR_NUMBER}"
else
  DEPLOY_TAG="git-${GIT_SHA}"
  echo "🔍 Using commit SHA: ${GIT_SHA}"
fi

# If version argument provided, use it; otherwise use deploy tag
VERSION="${1:-$DEPLOY_TAG}"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          THEO Docker Image Build Script                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Registry:     $REGISTRY/$OWNER"
echo "Deploy Tag:   $DEPLOY_TAG"
echo "Version:      $VERSION"
echo "Git SHA:      git-$GIT_SHA"
echo ""

# Build Backend
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Building Backend Image..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker build \
  -t theo-backend:latest \
  -t theo-backend:$VERSION \
  -t theo-backend:git-$GIT_SHA \
  -t $REGISTRY/$OWNER/theo-backend:latest \
  -t $REGISTRY/$OWNER/theo-backend:$VERSION \
  -t $REGISTRY/$OWNER/theo-backend:git-$GIT_SHA \
  -f backend/Dockerfile \
  backend

echo "✅ Backend image built successfully"
echo ""

# Build Frontend
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Building Frontend Image..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker build \
  -t theo-frontend:latest \
  -t theo-frontend:$VERSION \
  -t theo-frontend:git-$GIT_SHA \
  -t $REGISTRY/$OWNER/theo-frontend:latest \
  -t $REGISTRY/$OWNER/theo-frontend:$VERSION \
  -t $REGISTRY/$OWNER/theo-frontend:git-$GIT_SHA \
  -f frontend/Dockerfile \
  frontend

echo "✅ Frontend image built successfully"
echo ""

# Summary
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Build Complete!                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📦 Built images with tags:"
echo ""
echo "Backend:"
echo "  • theo-backend:latest"
echo "  • theo-backend:$VERSION"
echo "  • theo-backend:git-$GIT_SHA"
echo "  • $REGISTRY/$OWNER/theo-backend:latest"
echo "  • $REGISTRY/$OWNER/theo-backend:$VERSION"
echo "  • $REGISTRY/$OWNER/theo-backend:git-$GIT_SHA"
echo ""
echo "Frontend:"
echo "  • theo-frontend:latest"
echo "  • theo-frontend:$VERSION"
echo "  • theo-frontend:git-$GIT_SHA"
echo "  • $REGISTRY/$OWNER/theo-frontend:latest"
echo "  • $REGISTRY/$OWNER/theo-frontend:$VERSION"
echo "  • $REGISTRY/$OWNER/theo-frontend:git-$GIT_SHA"
echo ""
echo "🚀 To run locally:"
echo "   docker-compose up -d"
echo ""
echo "📤 To push to registry:"
echo "   docker push $REGISTRY/$OWNER/theo-backend:$VERSION"
echo "   docker push $REGISTRY/$OWNER/theo-frontend:$VERSION"
echo ""
