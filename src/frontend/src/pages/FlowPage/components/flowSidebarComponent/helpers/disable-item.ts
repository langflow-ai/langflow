import type { UniqueInputsComponents } from "../types";

export const disableItem = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  if (SBItemName === "ChatInput" && uniqueInputsComponents.chatInput) {
    return true;
  }
  if (SBItemName === "Webhook" && uniqueInputsComponents.webhookInput) {
    return true;
  }
  return false;
};
