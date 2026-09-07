# Everything needed to invoke the deployed agent, log in as either demo
# tenant, and inspect the surrounding infra: region/account, the runtime's
# ARN/ID and a ready-to-curl invoke URL, Cognito pool/client ids and demo
# user credentials, the database connection string, and the ECR/guardrail
# identifiers used above.

output "region" {
  description = "AWS region this stack was deployed into."
  value       = data.aws_region.current.region
}

output "account_id" {
  description = "AWS account ID this stack was deployed into."
  value       = data.aws_caller_identity.current.account_id
}

output "runtime_arn" {
  description = "ARN of the AgentCore Runtime."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn
}

output "runtime_id" {
  description = "ID of the AgentCore Runtime."
  value       = aws_bedrockagentcore_agent_runtime.this.agent_runtime_id
}

output "runtime_invoke_url" {
  description = "HTTPS endpoint to invoke the AgentCore Runtime."
  value       = "https://bedrock-agentcore.${data.aws_region.current.region}.amazonaws.com/runtimes/${urlencode(aws_bedrockagentcore_agent_runtime.this.agent_runtime_arn)}/invocations?qualifier=DEFAULT"
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID."
  value       = aws_cognito_user_pool.this.id
}

output "cognito_client_id" {
  description = "Cognito app client ID."
  value       = aws_cognito_user_pool_client.this.id
}

output "cognito_users" {
  description = "Demo user credentials, keyed by username."
  value = {
    for username, org in local.demo_orgs : username => {
      org_id   = org.org_id
      password = random_password.user[username].result
    }
  }
  sensitive = true
}

output "database_url" {
  description = "Neon Postgres connection string."
  value       = local.database_url
  sensitive   = true
}

output "database_url_param_name" {
  description = "SSM parameter name holding the database URL."
  value       = aws_ssm_parameter.database_url.name
}

output "ecr_repository_url" {
  description = "ECR repository URL for the agent container image."
  value       = aws_ecr_repository.this.repository_url
}

output "guardrail_id" {
  description = "Bedrock Guardrail ID."
  value       = aws_bedrock_guardrail.this.guardrail_id
}

output "guardrail_version" {
  description = "Bedrock Guardrail version."
  value       = aws_bedrock_guardrail_version.this.version
}
