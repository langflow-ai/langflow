import type {
  PolicyBundleChanges,
  PolicyBundleRead,
  PolicyBundleWrite,
} from "./types";

/**
 * Builds the body for `PUT /api/v1/policy-bundle`.
 *
 * The PUT is a complete replacement: a list left out of the body is cleared, not
 * kept. Two panels edit this bundle — the catalog (components, templates,
 * models, model providers) and integrations (approved providers, blocked
 * actions) — so a partial body from either one silently discards the other's
 * decisions. Every caller goes through here: the caller names only what it
 * changes, and the six lists plus `expected_revision` are carried from the
 * bundle it read, which is also what makes the write fail closed on a conflict.
 */
export function buildPolicyBundleUpdate(
  bundle: PolicyBundleRead,
  changes: PolicyBundleChanges = {},
): PolicyBundleWrite {
  const current = <K extends keyof PolicyBundleChanges>(
    key: K,
    fallback: string[],
  ): string[] => (changes[key] as string[] | undefined) ?? fallback;

  return {
    expected_revision: bundle.revision,
    approved_provider_ids: current(
      "approved_provider_ids",
      bundle.approved_provider_ids ?? [],
    ),
    blocked_component_keys: current(
      "blocked_component_keys",
      bundle.blocked_component_keys ?? [],
    ),
    blocked_template_keys: current(
      "blocked_template_keys",
      bundle.blocked_template_keys ?? [],
    ),
    blocked_model_keys: current(
      "blocked_model_keys",
      bundle.blocked_model_keys ?? [],
    ),
    approved_integration_provider_ids: current(
      "approved_integration_provider_ids",
      bundle.approved_integration_provider_ids ?? [],
    ),
    blocked_integration_action_keys: current(
      "blocked_integration_action_keys",
      bundle.blocked_integration_action_keys ?? [],
    ),
    ...(changes.reason === undefined ? {} : { reason: changes.reason }),
  };
}

/** True for the 409 the backend answers when the bundle moved on under a writer. */
export function isPolicyBundleConflict(error: unknown): boolean {
  const response = (
    error as { response?: { status?: number; data?: { detail?: unknown } } }
  )?.response;
  if (response?.status !== 409) return false;
  const detail = response.data?.detail;
  return (
    typeof detail === "object" && detail !== null && !Array.isArray(detail)
  );
}
