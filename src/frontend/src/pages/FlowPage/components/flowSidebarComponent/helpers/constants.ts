// Component name constants
export const CHAT_INPUT_COMPONENT = "ChatInput";
export const WEBHOOK_COMPONENT = "Webhook";

// Exclusivity rules: components that cannot coexist
export const EXCLUSIVITY_RULES = {
  [CHAT_INPUT_COMPONENT]: [WEBHOOK_COMPONENT],
  [WEBHOOK_COMPONENT]: [CHAT_INPUT_COMPONENT],
} as const;

// Tooltip messages
export const TOOLTIP_MESSAGES = {
  CHAT_INPUT_ALREADY_ADDED: "Chat input already added",
  WEBHOOK_ALREADY_ADDED: "Webhook already added",
  CANNOT_ADD_CHAT_INPUT_WITH_WEBHOOK:
    "Cannot add Chat Input when Webhook is present",
  CANNOT_ADD_WEBHOOK_WITH_CHAT_INPUT:
    "Cannot add Webhook when Chat Input is present",
} as const;
