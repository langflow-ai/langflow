import type { IntegrationCapabilityRead } from "@/controllers/API/queries/connections";
import manifest from "../../../../../../../bundles/servicenow/src/lfx_servicenow/components/servicenow/capabilities.v1.json";
import scenarios from "../../../../../../../bundles/servicenow/tests/fixtures/consent-scopes.json";
import {
  defaultScopesForNewConnection,
  scopeRequirements,
  scopesForRegistration,
  uniqueScopes,
} from "../helpers/scopes";

it.each(scenarios)(
  "requests usable servicenow consent under $policy policy",
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
    // This operator registration permits both instance scopes; the manifest's
    // default profile intentionally starts with read access only.
    const { requestable, unavailable } = scopesForRegistration(
      "servicenow",
      componentScopes,
      ["langflow_table_read", "langflow_table_write"],
    );
    expect(unavailable).toEqual([]);
    expect(
      defaultScopesForNewConnection(
        "servicenow",
        componentScopes,
        requestable,
      ).sort(),
    ).toEqual(scopes);
  },
);
