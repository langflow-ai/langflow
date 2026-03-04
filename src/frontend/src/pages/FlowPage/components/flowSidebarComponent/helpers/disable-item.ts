import type { UniqueInputsComponents } from "../types";
import { CHAT_INPUT_COMPONENT, WEBHOOK_COMPONENT } from "./constants";

export const disableItem = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  if (SBItemName === CHAT_INPUT_COMPONENT && uniqueInputsComponents.chatInput) {
    return true;
  }
  if (
    SBItemName === CHAT_INPUT_COMPONENT &&
    uniqueInputsComponents.webhookInput
  ) {
    return true;
  }
  if (SBItemName === WEBHOOK_COMPONENT && uniqueInputsComponents.webhookInput) {
    return true;
  }
  if (SBItemName === WEBHOOK_COMPONENT && uniqueInputsComponents.chatInput) {
    return true;
  }
  return false;
};
