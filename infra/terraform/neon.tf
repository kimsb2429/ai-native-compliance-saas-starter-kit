# Provisions the single Neon Postgres project this starter kit uses for all
# tenants (pooled multi-tenancy, decision B14): one project, one branch, one
# scale-to-zero compute. This is the entire database footprint - no RDS, no
# VPC, ~$0 idle since the compute suspends after 5 minutes of inactivity.

resource "neon_project" "this" {
  name       = var.project
  region_id  = "aws-us-east-1"
  pg_version = 17

  branch {
    name          = "main"
    database_name = "compliance"
    role_name     = "owner" # migrations and seeding; the runtime uses kit_app (below)
  }

  primary_compute {
    autoscaling_limit_min_cu = 0.25
    autoscaling_limit_max_cu = 1
    suspend_timeout_seconds  = 300
  }
}

# The runtime's database role. Two roles exist on purpose: `owner` (above)
# runs db/schema.sql and db/seed.sql; `kit_app` is a plain LOGIN role with
# NOBYPASSRLS that the AgentCore runtime connects as. Superuser-like roles
# ignore row-level security, so the runtime must never hold one. The role is
# created by db/schema.sql; scripts/seed.py sets this password on it.
resource "random_password" "app_db" {
  length           = 32
  special          = true
  override_special = "-_.~" # URL-safe: the password is embedded in a connection string
}

locals {
  # neon_project.connection_uri does not reliably include sslmode; append it
  # if missing so every connection is TLS.
  database_url = can(regex("sslmode=", neon_project.this.connection_uri)) ? neon_project.this.connection_uri : format(
    "%s%ssslmode=require",
    neon_project.this.connection_uri,
    strcontains(neon_project.this.connection_uri, "?") ? "&" : "?"
  )
  # What the runtime gets (via SSM): the same host and database, the kit_app role.
  app_database_url = "postgresql://kit_app:${random_password.app_db.result}@${neon_project.this.database_host}/${neon_project.this.database_name}?sslmode=require"
}
