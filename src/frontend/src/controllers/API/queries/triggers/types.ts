/**
 * Wire types for triggers and their event ledger.
 *
 * These mirror the backend schemas
 * (`services/database/models/trigger/schemas.py`), so field names stay
 * snake_case. The UI renders `allowed_actions`, `blocked_actions` and `reason`
 * as the server computes them and never re-derives them from `state`.
 */

export type Iso8601 = string;

export const TRIGGER_STATES = [
  "pending",
  "active",
  "paused",
  "expired",
  "needs_reconnect",
  "error",
  "dead",
] as const;
export type TriggerState = (typeof TRIGGER_STATES)[number];

/** Per-trigger operations, in the display order the server uses. */
export const TRIGGER_ACTIONS = [
  "pause",
  "resume",
  "test",
  "reconnect",
  "replay",
  "delete",
  "rotate_secret",
] as const;
export type TriggerAction = (typeof TRIGGER_ACTIONS)[number];

/** State reasons: `TriggerRead.reason`, and values in `blocked_actions`. */
export const TRIGGER_STATE_REASONS = [
  "pending",
  "config_invalid",
  "degraded",
  "paused",
  "paused_by_admin",
  "node_removed",
  "source_settings_changed",
  "error",
  "needs_reconnect",
  "consent_required",
  "expired",
  "dead",
] as const;

/** Caller reasons: only ever values in `blocked_actions`. */
export const TRIGGER_CALLER_REASONS = [
  "insufficient_permission",
  "not_connection_owner",
  "reconnect_not_needed",
] as const;

export type TriggerStateReason = (typeof TRIGGER_STATE_REASONS)[number];
export type TriggerCallerReason = (typeof TRIGGER_CALLER_REASONS)[number];
export type TriggerReason = TriggerStateReason | TriggerCallerReason;

export interface TriggerRead {
  id: string;
  flow_id: string;
  user_id: string | null;
  name: string;
  kind: string;
  provider: string | null;
  node_id: string | null;
  connection_id: string | null;
  config: Record<string, unknown>;
  state: TriggerState;
  binding_target: string;
  deployment_id: string | null;
  flow_version_id: string | null;
  session_policy: string;
  concurrency_limit: number;
  max_attempts: number;
  next_fire_at: Iso8601 | null;
  last_fired_at: Iso8601 | null;
  last_error: string | null;
  admin_paused_at?: Iso8601 | null;
  created_at: Iso8601 | null;
  updated_at: Iso8601 | null;
  reason?: TriggerStateReason | null;
  allowed_actions?: TriggerAction[];
  blocked_actions?: Partial<Record<TriggerAction, TriggerReason>>;
  /** Filled on list responses. */
  flow_name?: string | null;
  /** Operator view (`scope=all`) only. */
  owner_username?: string | null;
}

export type TriggerListScope = "mine" | "all";

export interface TriggerListParams {
  flowId?: string;
  scope?: TriggerListScope;
  provider?: string;
  state?: TriggerState;
  limit?: number;
  offset?: number;
}

export const TRIGGER_EVENT_STATES = [
  "pending",
  "claimed",
  "dispatched",
  "completed",
  "failed",
  "dead",
] as const;
export type TriggerEventState = (typeof TRIGGER_EVENT_STATES)[number];

export interface TriggerEventRead {
  id: string;
  trigger_id: string;
  dedupe_key: string;
  state: TriggerEventState;
  attempt: number;
  available_at: Iso8601 | null;
  /** Normalized payload only; the raw provider request never reaches the browser. */
  payload: Record<string, unknown>;
  session_id: string | null;
  job_id: string | null;
  replay_of_event_id: string | null;
  error: string | null;
  created_at: Iso8601 | null;
  updated_at: Iso8601 | null;
}

export interface TriggerIngressRead {
  trigger_id: string;
  public_id: string | null;
  ingress_url: string | null;
  has_signing_secret: boolean;
}

/** The one response that carries the plaintext secret; never cache it. */
export interface TriggerSigningSecretRead extends TriggerIngressRead {
  signing_secret: string;
}

export type TriggerBulkAction = "pause" | "resume";

export interface TriggerBulkRequest {
  provider?: string;
  trigger_ids?: string[];
  dry_run?: boolean;
}

export interface TriggerBulkFailure {
  trigger_id: string;
  detail: string;
}

export interface TriggerBulkResult {
  action: TriggerBulkAction;
  dry_run: boolean;
  matched: number;
  changed: string[];
  unchanged: string[];
  failed: TriggerBulkFailure[];
  owners: number;
}
