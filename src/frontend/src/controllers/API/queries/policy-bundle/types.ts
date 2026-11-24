/**
 * The policy bundle as `GET /api/v1/policy-bundle` returns it, and the body
 * `PUT` expects. The PUT replaces every list at once, which is why updates go
 * through `buildPolicyBundleUpdate` rather than being assembled per caller.
 */
export interface PolicyBundleRead {
  revision: number;
  initialized: boolean;
  source: string;
  approved_provider_ids: string[];
  blocked_component_keys: string[];
  blocked_template_keys: string[];
  blocked_model_keys: string[];
  approved_integration_provider_ids: string[];
  blocked_integration_action_keys: string[];
  content_hash: string;
  created_at: string;
  created_by: string | null;
  reason: string | null;
  rollback_of_revision: number | null;
  managed_externally: boolean;
}

/** Every list the backend replaces, plus the revision the write is guarded by. */
export interface PolicyBundleWrite {
  expected_revision: number;
  approved_provider_ids: string[];
  blocked_component_keys: string[];
  blocked_template_keys: string[];
  blocked_model_keys: string[];
  approved_integration_provider_ids: string[];
  blocked_integration_action_keys: string[];
  reason?: string | null;
}

/** The lists a caller means to change; everything else is carried through. */
export type PolicyBundleChanges = Partial<
  Omit<PolicyBundleWrite, "expected_revision">
>;
