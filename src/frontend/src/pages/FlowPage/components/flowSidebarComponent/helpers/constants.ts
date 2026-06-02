import {
  CHAT_INPUT_COMPONENT,
  MUTUALLY_EXCLUSIVE_COMPONENTS,
  WEBHOOK_COMPONENT,
} from "@/constants/constants";

// Component name constants (re-exported from the shared source of truth).
export { CHAT_INPUT_COMPONENT, WEBHOOK_COMPONENT };

// Exclusivity rules: components that cannot coexist. Aliased to the shared
// constant so the sidebar and the canvas paste flow stay in sync.
export const EXCLUSIVITY_RULES = MUTUALLY_EXCLUSIVE_COMPONENTS;

// Tooltip messages
export const TOOLTIP_MESSAGES = {
  CHAT_INPUT_ALREADY_ADDED: "Chat input already added",
  WEBHOOK_ALREADY_ADDED: "Webhook already added",
  CANNOT_ADD_CHAT_INPUT_WITH_WEBHOOK:
    "Cannot add Chat Input when Webhook is present",
  CANNOT_ADD_WEBHOOK_WITH_CHAT_INPUT:
    "Cannot add Webhook when Chat Input is present",
} as const;
