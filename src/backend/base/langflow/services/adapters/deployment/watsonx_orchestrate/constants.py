"""Constants, enums, and configuration values for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import re
from enum import Enum

from lfx.services.adapters.deployment.schema import DeploymentType

SUPPORTED_ADAPTER_DEPLOYMENT_TYPES: frozenset[DeploymentType] = frozenset({DeploymentType.AGENT})
CREATE_MAX_RETRIES = 3
UPDATE_MAX_RETRIES = 3
ROLLBACK_MAX_RETRIES = 5
RETRY_INITIAL_DELAY_SECONDS = 0.5
PROVIDER_SPEC_RESOURCE_NAME_PREFIX_KEY = "resource_name_prefix"
DEFAULT_WXO_AGENT_LLM = "groq/openai/gpt-oss-120b"

WXO_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_]")
WXO_TRANSLATE = str.maketrans({" ": "_", "-": "_"})

ERROR_PREFIX = "An error occurred while"
ERROR_SUFFIX_IN = "in Watsonx Orchestrate."


class WxOAuthURL(str, Enum):
    MCSP = "https://iam.platform.saas.ibm.com"
    IBM_IAM = "https://iam.cloud.ibm.com"


class ErrorPrefix(str, Enum):
    CREATE = f"{ERROR_PREFIX} creating a deployment {ERROR_SUFFIX_IN}"
    LIST = f"{ERROR_PREFIX} listing deployments {ERROR_SUFFIX_IN}"
    GET = f"{ERROR_PREFIX} getting a deployment {ERROR_SUFFIX_IN}"
    UPDATE = f"{ERROR_PREFIX} updating a deployment {ERROR_SUFFIX_IN}"
    REDEPLOY = f"{ERROR_PREFIX} redeploying a deployment {ERROR_SUFFIX_IN}"
    CLONE = f"{ERROR_PREFIX} cloning a deployment {ERROR_SUFFIX_IN}"
    DELETE = f"{ERROR_PREFIX} deleting a deployment {ERROR_SUFFIX_IN}"
    HEALTH = f"{ERROR_PREFIX} getting a deployment health {ERROR_SUFFIX_IN}"
    CREATE_CONFIG = f"{ERROR_PREFIX} creating a deployment config {ERROR_SUFFIX_IN}"
    LIST_CONFIGS = f"{ERROR_PREFIX} listing deployment configs {ERROR_SUFFIX_IN}"
    GET_CONFIG = f"{ERROR_PREFIX} getting a deployment config {ERROR_SUFFIX_IN}"
    UPDATE_CONFIG = f"{ERROR_PREFIX} updating a deployment config {ERROR_SUFFIX_IN}"
    DELETE_CONFIG = f"{ERROR_PREFIX} deleting a deployment config {ERROR_SUFFIX_IN}"
    CREATE_EXECUTION = f"{ERROR_PREFIX} creating a deployment execution {ERROR_SUFFIX_IN}"
    GET_EXECUTION = f"{ERROR_PREFIX} getting a deployment execution {ERROR_SUFFIX_IN}"


# NOTE: this key must match the value of the provider_key column
# in the deployment_provider_account table.
WATSONX_ORCHESTRATE_DEPLOYMENT_ADAPTER_KEY = "watsonx-orchestrate"
