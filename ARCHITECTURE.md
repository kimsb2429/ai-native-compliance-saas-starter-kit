# Architecture

A one-picture version of this page is the diagram at the top of [README.md](README.md#how-it-fits-together).

## The request path

1. A client signs in to Cognito and receives an ID token containing custom:org_id.
2. It POSTs to the AgentCore Runtime invoke URL with the token and a session ID header.
3. AgentCore validates the token via its custom JWT authorizer against Cognito's OpenID configuration.
4. AgentCore routes the request to a microVM dedicated to that session.
5. agent/main.py re-verifies the token against the JWKS, extracts custom:org_id, and sets the tenant ContextVar.
6. agent/builder.py loads the active agent_definition, resolves the prompt slug with caching and fallback, binds tenant-scoped tools, and constructs a Strands Agent with the guardrail.
7. The agent streams events; the runtime reduces them to a minimal wire format and returns SSE or JSON.
8. Tools use a shared psycopg connection pool; each transaction sets app.org_id via set_config, enforcing RLS.
9. The extractor agent writes structured obligations into the same tenant transaction.

This path ensures tenant isolation at every layer. The session is tied to a microVM, the tenant is derived from the token and held in a ContextVar for the invoke, and all database access is filtered by RLS. The agent is built dynamically per request, allowing prompt and tool changes without redeployment.

## Components and why each is here

**AgentCore Runtime** provides managed, per-session microVM isolation, built-in SSE streaming, and a JWT authorizer at the edge. The engagement used it, and the kit retains it for consistency and isolation.

**Strands Agents** is the first-party SDK that aligns with AgentCore's streaming model and tool binding. It was used in the engagement and is kept for direct compatibility.

**Neon Postgres 17** offers full Postgres compatibility, enabling Row-Level Security. It is serverless and scales to zero, avoiding VPC complexity. Aurora DSQL was rejected due to lack of documented RLS support, and Aurora Serverless v2 would require VPC mode with costly networking.

**Cognito user pool** serves as the identity provider trusted by AgentCore’s authorizer. The custom:org_id attribute carries tenant context from auth to application.

**Bedrock Guardrail** enforces content, PII, and topic controls on every model invocation. It runs on all calls without additional integration effort.

**ECR** stores the single arm64 container image used by the runtime. It is the simplest image registry option integrated with AWS.

**One IAM role** grants the runtime permissions to pull the image, write logs, invoke models, apply the guardrail, and read the SSM parameter. Multi-role setups were unnecessary because tenant data isolation is handled in Postgres.

**SSM SecureString parameter** holds the database URL securely, avoiding plaintext secrets in environment variables.

**Terraform** manages all infrastructure as code, ensuring reproducibility and version control across deployments.

**Makefile** simplifies common workflows: deploy, seed, demo, test, and destroy, making the kit easy to run and evaluate.

## Data model

The data model supports multi-tenancy with strict isolation. Tenant-specific data is scoped to org_id and protected by RLS. Platform data (prompts, agent definitions) is shared but versioned and auditable. The schema enables dynamic agent behavior through prompt revisions and tool binding, while structured outputs ensure reliable data extraction.

- organizations(id, slug, name)
- documents(id, org_id, title, kind, body)
- obligations(id, org_id, document_id, citation, requirement, frequency, responsible_party, due_rule)
- prompts(slug, description)
- prompt_revisions(slug, revision, model_id, system_text, user_template, is_active)
- agent_definitions(agent_ref, environment, version, description, model_size, prompt_slug, tools, structured_output, is_active)

Tenant tables (documents, obligations) carry RLS policies with FORCE ROW LEVEL SECURITY; platform tables do not. Two database roles exist: owner runs migrations and seeding; kit_app is the runtime role, LOGIN with NOBYPASSRLS.

## What is deliberately not here

- OCR of uploaded files (lever: Textract job on upload with text caching)
- Evaluations (lever: versioned case table with LLM judge on same runtime)
- Per-tenant usage metering
- Session persistence across microVMs (lever: session repository in Postgres)
- Per-request scoped AWS credentials via STS session tags (lever: phase-2 tenancy)
- VPC mode
- Graph agents
- A user interface

## Security posture, stated plainly

The runtime runs in PUBLIC network mode with outbound internet access. The database is accessed over public TLS using a password-authenticated role with NOBYPASSRLS. Inbound access is restricted to JWT tokens validated by Cognito and re-verified in the application. The runtime uses a single IAM role shared across tenants, which is acceptable because tenant data is isolated in Postgres by RLS and no tenant-specific AWS resources are created. Secrets are stored in SSM, not environment variables.
