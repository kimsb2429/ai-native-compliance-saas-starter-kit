# Stores the Neon connection string as a SecureString SSM parameter. The
# agent container reads the parameter name (not the secret) from its
# environment at boot and fetches the value via ssm:GetParameter, so the URL
# never sits in an environment variable on the running task.

resource "aws_ssm_parameter" "database_url" {
  name        = "/${var.project}/database_url"
  description = "Neon Postgres connection string for ${var.project}."
  type        = "SecureString"
  value       = local.database_url
}
