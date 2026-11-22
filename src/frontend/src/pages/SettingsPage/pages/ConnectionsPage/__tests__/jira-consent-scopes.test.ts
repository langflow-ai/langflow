import type { IntegrationCapabilityRead } from "@/controllers/API/queries/connections";
import manifest from "../../../../../../../bundles/jira/src/lfx_jira/components/jira/capabilities.v1.json";
import scenarios from "../../../../../../../bundles/jira/tests/fixtures/consent-scopes.json";
import {
  defaultScopesForNewConnection,
  scopeRequirements,
  scopesForRegistration,
  uniqueScopes,
} from "../helpers/scopes";

it.each(scenarios)(
  "requests usable jira consent under $policy policy",
  ({ policy, scopes }) => {
    const capabilities = manifest.capabilities
      .filter((capability) => policy === "all" || capability.risk === policy)
      .map((capability) => ({
        ...capability,
        allowed: true,
      })) as IntegrationCapabilityRead[];
    const componentScopes = uniqueScopes(
      scopeRequirements(capabilities, undefined),
    );
    const { requestable, unavailable } = scopesForRegistration(
      "jira",
      componentScopes,
      manifest.auth_profiles[0].default_scopes,
    );
    expect(unavailable).toEqual([]);
    expect(
      defaultScopesForNewConnection(
        "jira",
        componentScopes,
        requestable,
      ).sort(),
    ).toEqual(scopes);
  },
);
