import type { IntegrationCapabilityRead } from "@/controllers/API/queries/connections";
import manifest from "../../../../../../../bundles/confluence/src/lfx_confluence/components/confluence_integrations/capabilities.v1.json";
import scenarios from "../../../../../../../bundles/confluence/tests/fixtures/consent-scopes.json";
import {
  defaultScopesForNewConnection,
  scopeRequirements,
  scopesForRegistration,
  uniqueScopes,
} from "../helpers/scopes";

it.each(scenarios)(
  "requests usable confluence consent under $policy policy",
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
      "confluence",
      componentScopes,
      manifest.auth_profiles[0].default_scopes,
    );
    expect(unavailable).toEqual([]);
    expect(
      defaultScopesForNewConnection(
        "confluence",
        componentScopes,
        requestable,
      ).sort(),
    ).toEqual(scopes);
  },
);
