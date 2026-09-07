"""Process settings, read once at import.

Local runs set DATABASE_URL directly. On AgentCore the Terraform module passes
DATABASE_URL_PARAM (an SSM SecureString name) instead, so the connection string
never appears in the runtime's environment or in Terraform-rendered config.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

MODEL_SMALL = os.getenv("MODEL_SMALL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
MODEL_MEDIUM = os.getenv("MODEL_MEDIUM", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
MODEL_SIZE_MAP = {"small": MODEL_SMALL, "medium": MODEL_MEDIUM}

GUARDRAIL_ID = os.getenv("GUARDRAIL_ID") or None
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "DRAFT")

JWT_JWKS_URL = os.getenv("JWT_JWKS_URL") or None
JWT_ISSUER = os.getenv("JWT_ISSUER") or None
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE") or None
JWT_ORG_CLAIM = os.getenv("JWT_ORG_CLAIM", "custom:org_id")

PROMPT_CACHE_TTL_SECONDS = int(os.getenv("PROMPT_CACHE_TTL_SECONDS", "60"))
ENVIRONMENT = os.getenv("AGENT_ENVIRONMENT", "prod")


def database_url() -> str:
    """Resolve the connection string: env first, then the SSM parameter."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    param = os.getenv("DATABASE_URL_PARAM")
    if not param:
        raise RuntimeError("Set DATABASE_URL (local) or DATABASE_URL_PARAM (AgentCore).")
    import boto3  # imported here so local runs never need AWS credentials

    ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return ssm.get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]
