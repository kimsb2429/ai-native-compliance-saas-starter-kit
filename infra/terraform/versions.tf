# Pins Terraform core and the three providers this stack needs: AWS (Bedrock
# AgentCore, Cognito, ECR, IAM, Budgets, SSM), Neon (managed Postgres), and
# random (per-user demo passwords). The Neon provider reads NEON_API_KEY from
# the environment - it is never written into this repo.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
    neon = {
      source  = "kislerdm/neon"
      version = "~> 0.11"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "aws" {
  region = var.region
}

# Reads the Neon API key from the NEON_API_KEY environment variable.
provider "neon" {}
