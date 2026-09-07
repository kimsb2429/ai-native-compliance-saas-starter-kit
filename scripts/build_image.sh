#!/usr/bin/env bash
# Builds the agent's container image for linux/arm64 (the platform AgentCore
# Runtime expects) and pushes it straight to the ECR repository Terraform
# already created. Run from the repo root, or via `make image` / `make deploy`.
set -euo pipefail

REGION="${REGION:-us-east-1}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${REPO_ROOT}/infra/terraform"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required but was not found on PATH." >&2
  exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  echo "ERROR: docker buildx is required but is not available. Install/enable the buildx plugin." >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

aws ecr get-login-password --region "${REGION}" \
  | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

REPO_URL="$(terraform -chdir="${TF_DIR}" output -raw ecr_repository_url)"

docker buildx build \
  --platform linux/arm64 \
  -t "${REPO_URL}:${IMAGE_TAG}" \
  --push \
  "${REPO_ROOT}"

echo "Pushed image: ${REPO_URL}:${IMAGE_TAG}"
