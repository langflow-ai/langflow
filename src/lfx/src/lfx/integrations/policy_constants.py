"""Reserved identities used by the integration policy storage contract."""

# A nonempty allowlist also denies real providers on older replicas, whose
# empty allowlist means unrestricted. This identity cannot name an integration.
INTEGRATION_POLICY_DENY_ALL_PROVIDER_ID = "langflow-reserved.integration-policy.deny-all"
