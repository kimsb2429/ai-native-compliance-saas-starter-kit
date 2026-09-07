# Auth for the demo: a Cognito user pool with a custom `org_id` attribute
# (decision B14's tenant claim), a public app client for password-grant
# login, and two seeded users - one per demo tenant. AgentCore Runtime
# verifies the resulting JWT directly (see runtime.tf); the app never trusts
# a client-asserted tenant id.

locals {
  # Fixed by contract: seed data (db/) references these two org ids.
  demo_orgs = {
    "acme-user" = {
      email  = "acme-user@example.com"
      org_id = "11111111-1111-4111-8111-111111111111"
    }
    "blueharbor-user" = {
      email  = "blueharbor-user@example.com"
      org_id = "22222222-2222-4222-8222-222222222222"
    }
  }
}

resource "aws_cognito_user_pool" "this" {
  name = "${var.project}-users"

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  schema {
    name                     = "org_id"
    attribute_data_type      = "String"
    mutable                  = true
    developer_only_attribute = false
    required                 = false

    string_attribute_constraints {
      min_length = 1
      max_length = 64
    }
  }
}

resource "aws_cognito_user_pool_client" "this" {
  name         = "${var.project}-client"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  id_token_validity = 1
  token_validity_units {
    id_token = "hours"
  }

  read_attributes = ["email", "custom:org_id"]
}

resource "random_password" "user" {
  for_each = local.demo_orgs

  length           = 20
  special          = true
  override_special = "!@#%^*-_"
}

resource "aws_cognito_user" "demo" {
  for_each = local.demo_orgs

  user_pool_id   = aws_cognito_user_pool.this.id
  username       = each.key
  password       = random_password.user[each.key].result
  message_action = "SUPPRESS"
  enabled        = true

  attributes = {
    email           = each.value.email
    email_verified  = true
    "custom:org_id" = each.value.org_id
  }

  # The provider stores custom attributes in state without the "custom:" prefix,
  # sees a perpetual diff, and its update path strips the attribute from the
  # user. Create sets it correctly, so ignore drift after creation.
  lifecycle {
    ignore_changes = [attributes]
  }
}
