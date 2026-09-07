# The AgentCore Runtime itself: a containerized agent (decision A3 - agents
# defined as Postgres rows, built into a live Agent per invoke) fronted by
# Cognito JWT auth. The container reads its model IDs, guardrail, JWT
# verification material, and database parameter name from environment
# variables set here; the actual secret (the database URL) stays in SSM,
# fetched at boot via the role in iam.tf.

resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = "${replace(var.project, "-", "_")}_agent"
  description        = "Agentic compliance management SaaS platform starter kit."
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.this.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.this.id}/.well-known/openid-configuration"
      allowed_audience = [aws_cognito_user_pool_client.this.id]
    }
  }

  request_header_configuration {
    request_header_allowlist = ["Authorization"]
  }

  environment_variables = {
    DATABASE_URL_PARAM = aws_ssm_parameter.database_url.name
    JWT_JWKS_URL       = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.this.id}/.well-known/jwks.json"
    JWT_ISSUER         = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.this.id}"
    JWT_AUDIENCE       = aws_cognito_user_pool_client.this.id
    JWT_ORG_CLAIM      = "custom:org_id"
    GUARDRAIL_ID       = aws_bedrock_guardrail.this.guardrail_id
    GUARDRAIL_VERSION  = aws_bedrock_guardrail_version.this.version
    MODEL_SMALL        = var.model_small
    MODEL_MEDIUM       = var.model_medium
    LOG_LEVEL          = "INFO"
  }
}
