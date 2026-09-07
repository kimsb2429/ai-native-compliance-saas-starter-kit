# Entry points for deploying, seeding, demoing, and tearing down the
# compliance-kit starter. `make deploy` is the common path: it creates the
# ECR repo first (so an image exists to build/push), builds and pushes the
# agent image, then applies the rest of the stack.

TF_DIR := infra/terraform
REGION ?= us-east-1
IMAGE_TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)
FLOW ?= 02

.PHONY: help deploy image seed demo test local destroy cost

help:
	@echo "Targets:"
	@echo "  deploy   - terraform init, create ECR, build+push image, apply full stack"
	@echo "  image    - build and push the agent container image only"
	@echo "  seed     - load demo tenant/permit data into the database"
	@echo "  demo     - run a demo flow (FLOW=<number>, default 02)"
	@echo "  test     - run the test suite"
	@echo "  local    - run the agent locally"
	@echo "  destroy  - tear down all infrastructure"
	@echo "  cost     - show where the cost breakdown lives"

deploy:
	terraform -chdir=$(TF_DIR) init
	terraform -chdir=$(TF_DIR) apply -target=aws_ecr_repository.this -auto-approve -var image_tag=$(IMAGE_TAG) -var region=$(REGION)
	scripts/build_image.sh
	terraform -chdir=$(TF_DIR) apply -auto-approve -var image_tag=$(IMAGE_TAG) -var region=$(REGION)

image:
	scripts/build_image.sh

seed:
	uv run python scripts/seed.py

demo:
	uv run python scripts/demo.py $(FLOW)

test:
	uv run pytest -q

local:
	uv run python -m agent.main

destroy:
	terraform -chdir=$(TF_DIR) destroy -auto-approve -var image_tag=$(IMAGE_TAG) -var region=$(REGION)

cost:
	@echo "See docs/COST.md for the monthly cost breakdown."
