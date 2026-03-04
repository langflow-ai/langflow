import type { UniqueInputsComponents } from "../types";

export const getDisabledTooltip = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  if (SBItemName === "ChatInput" && uniqueInputsComponents.chatInput) {
    return "Chat input already added";
  }
  if (SBItemName === "ChatInput" && uniqueInputsComponents.webhookInput) {
    return "Cannot add Chat Input when Webhook is present";
  }
  if (SBItemName === "Webhook" && uniqueInputsComponents.webhookInput) {
    return "Webhook already added";
  }
  if (SBItemName === "Webhook" && uniqueInputsComponents.chatInput) {
    return "Cannot add Webhook when Chat Input is present";
  }
  return "";
};
