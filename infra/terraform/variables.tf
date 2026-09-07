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

variable "image_tag" {
  description = "Tag of the agent container image in ECR to run on AgentCore Runtime."
  type        = string
  default     = "latest"
}

variable "model_small" {
  description = "Bedrock model ID used for cheap/fast agent calls."
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "model_medium" {
  description = "Bedrock model ID used for higher-quality agent calls."
  type        = string
  default     = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
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
