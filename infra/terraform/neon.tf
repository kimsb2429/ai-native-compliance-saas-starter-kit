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
    role_name     = "app"
  }

  primary_compute {
    autoscaling_limit_min_cu = 0.25
    autoscaling_limit_max_cu = 1
    suspend_timeout_seconds  = 300
  }
}

locals {
  # neon_project.connection_uri does not reliably include sslmode; append it
  # if missing so the agent always connects over TLS.
  database_url = can(regex("sslmode=", neon_project.this.connection_uri)) ? neon_project.this.connection_uri : format(
    "%s%ssslmode=require",
    neon_project.this.connection_uri,
    strcontains(neon_project.this.connection_uri, "?") ? "&" : "?"
  )
}
