import type { UniqueInputsComponents } from "../types";

export const getDisabledTooltip = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  if (SBItemName === "ChatInput" && uniqueInputsComponents.chatInput) {
    return "Chat input already added";
  }
  if (SBItemName === "Webhook" && uniqueInputsComponents.webhookInput) {
    return "Webhook already added";
  }
  return "";
};
