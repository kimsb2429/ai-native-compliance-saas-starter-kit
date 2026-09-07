# Top-level knobs shared across every other file: the project slug used to
# name and tag every resource, the AWS region, the model IDs the runtime
# invokes, the image tag deployed to AgentCore, and the optional monthly
# budget alert.

variable "project" {
  description = "Project slug used as a prefix/name for every resource."
  type        = string
  default     = "compliance-kit"
}

variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

# Bring your own Postgres: set this (for example from `neon link`, which writes
# DATABASE_URL_UNPOOLED to .env.local) and Terraform will not create a Neon
# project. Leave it empty and Terraform creates one using NEON_API_KEY.
variable "database_url" {
  description = "Owner connection string of an existing Postgres. Empty = create a Neon project."
  type        = string
  default     = ""
  sensitive   = true
}

variable "image_tag" {
  description = "Tag of the agent container image in ECR to run on AgentCore Runtime."
  type        = string
  default     = "latest"
}

# Defaults are Amazon Nova because a fresh account can invoke them with no
# extra approval. To use Claude, submit the Anthropic use-case form in the
# Bedrock console, then set e.g. model_small = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
# and model_medium = "us.anthropic.claude-sonnet-4-5-20250929-v1:0".
variable "model_small" {
  description = "Bedrock model ID for cheap/fast calls (extraction)."
  type        = string
  default     = "us.amazon.nova-2-lite-v1:0"
}

variable "model_medium" {
  description = "Bedrock model ID for higher-quality calls (the assistant)."
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "budget_limit_usd" {
  description = "Monthly AWS budget limit in USD."
  type        = number
  default     = 10
}

variable "budget_alert_email" {
  description = "Email to notify at 80% of the monthly budget. Leave empty to skip creating a budget."
  type        = string
  default     = ""
}
