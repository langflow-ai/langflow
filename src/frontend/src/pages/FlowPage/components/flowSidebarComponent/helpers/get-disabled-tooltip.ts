import type { UniqueInputsComponents } from "../types";
import {
  CHAT_INPUT_COMPONENT,
  TOOLTIP_MESSAGES,
  WEBHOOK_COMPONENT,
} from "./constants";

export const getDisabledTooltip = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  if (SBItemName === CHAT_INPUT_COMPONENT && uniqueInputsComponents.chatInput) {
    return TOOLTIP_MESSAGES.CHAT_INPUT_ALREADY_ADDED;
  }
  if (
    SBItemName === CHAT_INPUT_COMPONENT &&
    uniqueInputsComponents.webhookInput
  ) {
    return TOOLTIP_MESSAGES.CANNOT_ADD_CHAT_INPUT_WITH_WEBHOOK;
  }
  if (SBItemName === WEBHOOK_COMPONENT && uniqueInputsComponents.webhookInput) {
    return TOOLTIP_MESSAGES.WEBHOOK_ALREADY_ADDED;
  }
  if (SBItemName === WEBHOOK_COMPONENT && uniqueInputsComponents.chatInput) {
    return TOOLTIP_MESSAGES.CANNOT_ADD_WEBHOOK_WITH_CHAT_INPUT;
  }
  return "";
};
