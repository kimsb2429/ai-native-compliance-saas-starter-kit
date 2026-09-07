# Stores the runtime's connection string (kit_app role, NOBYPASSRLS) as a
# SecureString SSM parameter. The agent container reads the parameter name
# (not the secret) from its environment at boot and fetches the value via
# ssm:GetParameter, so the URL never sits in an environment variable.

resource "aws_ssm_parameter" "database_url" {
  name        = "/${var.project}/database_url"
  description = "Runtime (kit_app) Postgres connection string for ${var.project}."
  type        = "SecureString"
  # Write-only: the secret is sent to SSM but never persisted in Terraform state.
  value_wo         = local.app_database_url
  value_wo_version = 1
}
