import type { UniqueInputsComponents } from "../types";
import {
  CHAT_INPUT_COMPONENT,
  CRON_TRIGGER_COMPONENT,
  EXCLUSIVITY_RULES,
  WEBHOOK_COMPONENT,
} from "./constants";

export const disableItem = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  // Check if component already exists
  if (SBItemName === CHAT_INPUT_COMPONENT && uniqueInputsComponents.chatInput) {
    return true;
  }
  if (SBItemName === WEBHOOK_COMPONENT && uniqueInputsComponents.webhookInput) {
    return true;
  }
  if (
    SBItemName === CRON_TRIGGER_COMPONENT &&
    uniqueInputsComponents.cronTrigger
  ) {
    return true;
  }

  // Check exclusivity rules
  const exclusiveComponents = EXCLUSIVITY_RULES[SBItemName];
  if (exclusiveComponents) {
    for (const exclusiveComponent of exclusiveComponents) {
      if (
        exclusiveComponent === CHAT_INPUT_COMPONENT &&
        uniqueInputsComponents.chatInput
      ) {
        return true;
      }
      if (
        exclusiveComponent === WEBHOOK_COMPONENT &&
        uniqueInputsComponents.webhookInput
      ) {
        return true;
      }
    }
  }

  return false;
};
