# What it costs

Prices are for US East (N. Virginia) as of 2026-09-07.

| Component | What it is billed on | List price | Idle month | Month with 100 invocations |
|---------|----------------------|------------|----------|----------------------------|
| Amazon Bedrock AgentCore Runtime | vCPU-hour and GB-hour of active compute | $0.0895 per vCPU-hour, $0.00945 per GB-hour | $0 | $0.06 |
| Amazon Bedrock model tokens (default: Amazon Nova Pro for both agents; Nova 2 Lite available as the small model) | Per million input and output tokens | Nova Pro $0.80 in / $3.20 out; Nova 2 Lite $0.33 / $2.75 (AWS Pricing API, 2026-09-07). Claude Sonnet 4.5 is $3 / $15 and Haiku 4.5 $1 / $5 if you switch the model variables after submitting the Anthropic use-case form | $0 | $0.40 |
| Amazon Bedrock Guardrails | Per 1,000 text units for content filters, denied topics, PII filters | $0.15, $0.15, $0.10 per 1,000 text units | $0 | $0.08 |
| Amazon Cognito | Monthly active users | Free for first 10,000 | $0 | $0 |
| Amazon ECR | GB-month of stored images | $0.10 per GB-month | $0.05 | $0.05 |
| AWS Systems Manager Parameter Store | Standard SecureString parameters | Free | $0 | $0 |
| Amazon CloudWatch Logs | GB ingested | $0.50 per GB, first 5 GB free | $0 | $0 |
| Neon Postgres | Compute-unit hours and GB-month storage | Free plan covers the demo (100 CU-hours, 0.5 GB); paid: $0.106 per CU-hour, $0.35 per GB-month | $0 | $0 |
| AWS Budgets | Basic budgets | Free | $0 | $0 |
| Total | | | $0.05 | $0.59 |

Model token costs dominate the bill. The 100 invocation month uses about $0.40 in tokens on Nova Pro, roughly two thirds of the total; on Claude Sonnet 4.5 the same month is about $1.65 in tokens. I kept the agent design minimal to limit token use per call, but usage scales directly with invocation count and model choice. To keep costs low, monitor token use per agent per tenant, set model invocation timeouts, and use the small model for extraction where it proves accurate enough.

Several components are not included in the bill because they are not deployed. These include NAT gateways and VPC endpoints, which would add $33 to $37 monthly. I avoided them by using Neon's public TLS endpoint and running AgentCore in PUBLIC mode. RDS, Aurora, OpenSearch, and Textract are also not used. The kit relies on serverless and managed services that scale to zero, so idle cost is negligible.

One command removes everything: make destroy.
