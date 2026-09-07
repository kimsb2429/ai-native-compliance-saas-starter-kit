# AI-native compliance management saas platform starter kit

This is a minimal, deployable, multi-tenant agent platform on Amazon Bedrock AgentCore Runtime, generic for permits, regulations, and policies. It is a case study of an engagement I built, reconstructed in my own words with no code from the engagement. It keeps three decisions from that engagement, each modernized, and proves each with a runnable payload.

## How it fits together

```mermaid
flowchart LR
    C["Client<br/>scripts/invoke.py"] -->|"1 sign in"| COG["Amazon Cognito<br/>user pool · custom:org_id"]
    COG -->|"ID token"| C
    C -->|"2 POST /invocations<br/>Bearer token + session id"| AC["Bedrock AgentCore Runtime<br/>JWT authorizer · microVM per session"]
    AC -->|"3 verified token"| APP["agent/main.py<br/>tenant → ContextVar"]
    APP --> B["agent/builder.py<br/>row → Strands Agent"]
    B -->|"agent_definitions<br/>prompt_revisions"| PG[("Neon Postgres 17<br/>one pool · RLS · kit_app role")]
    B --> M["Amazon Bedrock<br/>Nova Pro / Nova 2 Lite"]
    M --- G["Bedrock Guardrail<br/>PII · denied topic · filters"]
    B -->|"tools, bound to the tenant"| T["list_obligations<br/>get_document"]
    T -->|"set_config(app.org_id) per txn"| PG
    APP -->|"4 SSE or JSON"| C
    SSM["SSM SecureString<br/>database_url"] -.->|"read at boot"| APP
```

Every box is created by `infra/terraform`. Tenant identity travels only as the verified `custom:org_id` claim; the request body never names a tenant. The three spine decisions live in the three middle boxes: the agent row (A3), the prompt revision (A26), and the one pool behind row-level security (B14).

## What you get

You get one runtime, one container image, one Postgres instance, two seeded tenants (Acme Fabrication with an air quality operating permit, Blue Harbor Logistics with an industrial stormwater permit), two agents seeded (compliance-assistant, obligation-extractor), and a third added live in flow 06 (gap-checker). The kit includes six runnable flows, 22 tests that run against a local Postgres in Docker without AWS, and costs about $0 per month when idle.

## Quickstart

You need AWS credentials for an account with Amazon Bedrock enabled in us-east-1 (the defaults use Amazon Nova Pro and Nova 2 Lite, which need no extra approval; Claude models work once the account has submitted the Anthropic use-case form, by setting the two model variables), a Neon API key stored in `NEON_API_KEY`, Terraform >= 1.6, Docker with buildx, uv, and Python 3.12. Run these commands:

```bash
make deploy
make seed
make demo FLOW=02
make destroy
```

`make deploy` runs Terraform init, creates the ECR repository, builds and pushes the arm64 image, and applies the full stack. `make seed` runs scripts to set up the schema, RLS policies, prompt registry, agent rows, the two documents, and the runtime's non-privileged database role. To run tests locally, start a Postgres container: `docker run -d --name kit-pg -e POSTGRES_PASSWORD=kit -e POSTGRES_USER=kit -e POSTGRES_DB=compliance -p 127.0.0.1:5439:5432 postgres:17-alpine`, then run `TEST_DATABASE_URL=postgresql://kit:kit@localhost:5439/compliance make test`.

## The three decisions that define it

Everything else in the system follows from these three decisions.

- **A3: agents as database rows**: In the kit, agents are rows in Postgres built into a live Strands Agent per invoke. One container image serves every agent. Adding an agent requires only an INSERT into agent_definitions. I kept this because it decouples deployment from agent creation. See [docs/decisions/A3.md](docs/decisions/A3.md).
- **A26: prompt registry by slug with revisions**: The kit uses a prompt registry where prompts are retrieved by slug and carry immutable revisions that include the model ID. Prompts are read through a short in-process TTL cache. In the engagement, this was a central HTTP service serving multiple languages, authors, and model providers. For the kit, I scoped it down to local registry access and moved guardrails out of instruction text into an enforced Bedrock Guardrail. See [docs/decisions/A26.md](docs/decisions/A26.md).
- **B14: pooled multi-tenancy with tenant context**: The kit uses one runtime and one connection pool. The tenant is derived from a verified Cognito JWT claim and stored in a ContextVar. Postgres enforces isolation via row-level security with a transaction-local setting. The runtime uses a non-privileged database role. In the engagement, the tenant came from the request body and isolation was in application code. I moved to JWT verification and RLS for stronger guarantees. See [docs/decisions/B14.md](docs/decisions/B14.md).

## Six flows, each proves one claim

| Flow | Payload | Outcome | Proves |
|------|-------|--------|-------|
| 01 intake | examples/payloads/01-intake-extract-obligations.json | obligations rows written and returned as JSON | A3 (a row with a structured-output schema builds the extractor) |
| 02 ask | 02-ask-quarterly-obligations.json | an answer from Acme's rows only | B14 (verified JWT tenant plus RLS) |
| 03 cross-tenant | 03-cross-tenant-same-question.json | Blue Harbor names Acme's permit and gets nothing of Acme's | B14 isolation |
| 04 prompt revision | 04-prompt-revision-then-ask.json | the answer format changes with no redeploy and the response carries the revision number | A26 |
| 05 guardrail | 05-guardrail-pii-and-evasion.json | the guardrail intervenes on PII and a regulatory-evasion request | enforced control |
| 06 new agent | 06-new-agent-row-gap-checker.json | one INSERT adds gap-checker and it answers with the image untouched | A3 |

Recorded outcomes live in examples/expected/ and each flow has a page under docs/flows/. Run one with `make demo FLOW=nn`.

## What is stubbed, and the lever for each

OCR is stubbed; documents are seeded as text; the lever is a Textract job on upload with cached text. Evaluations are stubbed; the lever is versioned case tables and an LLM judge on the same runtime. Per-tenant usage metering is not implemented. Session persistence is stubbed; the lever is a session repository in Postgres. Per-request scoped AWS credentials via STS session tags is the phase-2 tenancy lever. VPC network mode is not used. There is no user interface.

## What it costs

See docs/COST.md: about $0.05 per month idle, about $0.59 for a month with 100 invocations on the Nova defaults, with model tokens making up about two thirds of the cost.

## About the engagement

I built an agentic compliance management saas platform for a client as a consultant. This repository names no client, no firm, no person, and contains none of their code. What it carries is the decisions, the trade-offs, and the parts I would do differently now, written so a reader can check every claim against the code in this repo.

## Layout

```
agent/            runtime: main.py (entrypoint), builder.py (row to Agent), prompts.py
                  (registry read), tenant.py (JWT to ContextVar), db.py (one pool,
                  set_config per transaction), tools.py, extract.py, models.py
db/               schema.sql (tables, RLS policies, kit_app role), seed.sql, flows/*.sql
infra/terraform/  Neon project, Cognito, ECR, IAM role, Bedrock Guardrail, SSM,
                  AgentCore runtime with JWT authorizer, optional budget
examples/         payloads/ (the six flows), documents/ (two permits), expected/ (recorded)
docs/             decisions/ (A3, A26, B14), flows/ (one page per flow), COST.md
scripts/          seed.py, invoke.py, demo.py, build_image.sh
tests/            22 tests against a local Postgres; no AWS needed
ARCHITECTURE.md   the request path, every component and why, what is not here
```
