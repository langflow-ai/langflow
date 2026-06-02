// Tooltip messages shown when a sidebar item is disabled by a placement
// constraint. Keyed by the violation case (see get-disabled-tooltip); the
// constraint logic itself lives in `@/utils/componentConstraints`.
export const TOOLTIP_MESSAGES = {
  CHAT_INPUT_ALREADY_ADDED: "Chat input already added",
  WEBHOOK_ALREADY_ADDED: "Webhook already added",
  CANNOT_ADD_CHAT_INPUT_WITH_WEBHOOK:
    "Cannot add Chat Input when Webhook is present",
  CANNOT_ADD_WEBHOOK_WITH_CHAT_INPUT:
    "Cannot add Webhook when Chat Input is present",
} as const;
