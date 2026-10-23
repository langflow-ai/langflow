import type { TriggerRead } from "@/controllers/API/queries/triggers";

/**
 * States an owner turned on that nothing has told to stop. Mirrors
 * `ARMED_TRIGGER_STATES` in the trigger schemas.
 */
const ARMED_STATES = new Set(["active", "error", "needs_reconnect"]);

/**
 * Whether the node's Enabled switch reads as on. `pending` is ambiguous on
 * the wire (a fresh canvas save and a push source still subscribing look the
 * same), so a switch the user just turned on stays on through `pending`
 * until the state settles.
 */
export const isTriggerEnabled = (
  trigger: Pick<TriggerRead, "state">,
  enableRequested: boolean,
): boolean =>
  ARMED_STATES.has(trigger.state) ||
  (enableRequested && trigger.state === "pending");
