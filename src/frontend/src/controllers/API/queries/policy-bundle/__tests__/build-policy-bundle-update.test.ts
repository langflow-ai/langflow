import {
  buildPolicyBundleUpdate,
  isPolicyBundleConflict,
} from "../build-policy-bundle-update";
import type { PolicyBundleRead } from "../types";

const bundle = (
  overrides: Partial<PolicyBundleRead> = {},
): PolicyBundleRead => ({
  revision: 7,
  initialized: true,
  source: "api",
  approved_provider_ids: ["openai"],
  blocked_component_keys: ["ChatInput"],
  blocked_template_keys: ["basic-prompting"],
  blocked_model_keys: ["openai:gpt-4o"],
  approved_integration_provider_ids: ["google"],
  blocked_integration_action_keys: ["integrations.google.gmail.send"],
  content_hash: "hash",
  created_at: "2026-09-17T10:00:00",
  created_by: null,
  reason: null,
  rollback_of_revision: null,
  managed_externally: false,
  ...overrides,
});

describe("buildPolicyBundleUpdate", () => {
  it("guards the write with the revision it read", () => {
    expect(buildPolicyBundleUpdate(bundle()).expected_revision).toBe(7);
  });

  it("carries every list through when nothing is changed", () => {
    const current = bundle();
    expect(buildPolicyBundleUpdate(current)).toEqual({
      expected_revision: 7,
      approved_provider_ids: ["openai"],
      blocked_component_keys: ["ChatInput"],
      blocked_template_keys: ["basic-prompting"],
      blocked_model_keys: ["openai:gpt-4o"],
      approved_integration_provider_ids: ["google"],
      blocked_integration_action_keys: ["integrations.google.gmail.send"],
    });
  });

  // The PUT replaces the whole bundle, so a catalog save that omitted the
  // integration lists used to clear integration policy, and vice versa.
  it("keeps integration policy when the catalog changes", () => {
    const update = buildPolicyBundleUpdate(bundle(), {
      blocked_component_keys: ["ChatInput", "ChatOutput"],
    });
    expect(update.blocked_component_keys).toEqual(["ChatInput", "ChatOutput"]);
    expect(update.approved_integration_provider_ids).toEqual(["google"]);
    expect(update.blocked_integration_action_keys).toEqual([
      "integrations.google.gmail.send",
    ]);
  });

  it("keeps catalog policy when integrations change", () => {
    const update = buildPolicyBundleUpdate(bundle(), {
      blocked_integration_action_keys: [],
    });
    expect(update.blocked_integration_action_keys).toEqual([]);
    expect(update.blocked_component_keys).toEqual(["ChatInput"]);
    expect(update.blocked_template_keys).toEqual(["basic-prompting"]);
    expect(update.blocked_model_keys).toEqual(["openai:gpt-4o"]);
    expect(update.approved_provider_ids).toEqual(["openai"]);
  });

  it("clears a list when the caller asks for an empty one", () => {
    expect(
      buildPolicyBundleUpdate(bundle(), { approved_provider_ids: [] })
        .approved_provider_ids,
    ).toEqual([]);
  });

  it("tolerates a bundle that omits the integration lists", () => {
    const legacy = bundle();
    // @ts-expect-error - an older backend answered without these fields.
    legacy.approved_integration_provider_ids = undefined;
    // @ts-expect-error - same.
    legacy.blocked_integration_action_keys = undefined;
    const update = buildPolicyBundleUpdate(legacy);
    expect(update.approved_integration_provider_ids).toEqual([]);
    expect(update.blocked_integration_action_keys).toEqual([]);
  });

  it("sends a reason only when one is given", () => {
    expect(buildPolicyBundleUpdate(bundle())).not.toHaveProperty("reason");
    expect(
      buildPolicyBundleUpdate(bundle(), { reason: "block gmail" }).reason,
    ).toBe("block gmail");
  });
});

describe("isPolicyBundleConflict", () => {
  it("recognizes the revision conflict the backend answers", () => {
    expect(
      isPolicyBundleConflict({
        response: { status: 409, data: { detail: { expected_revision: 7 } } },
      }),
    ).toBe(true);
  });

  it("ignores other failures", () => {
    expect(isPolicyBundleConflict({ response: { status: 403 } })).toBe(false);
    expect(isPolicyBundleConflict(new Error("offline"))).toBe(false);
  });
});
