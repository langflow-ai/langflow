import i18n from "@/i18n";
import type { UniqueInputsComponents } from "../types";

export const getDisabledTooltip = (
  SBItemName: string,
  uniqueInputsComponents: UniqueInputsComponents,
) => {
  if (SBItemName === "ChatInput" && uniqueInputsComponents.chatInput) {
    return i18n.t("sidebar.chatInputAdded");
  }
  if (SBItemName === "Webhook" && uniqueInputsComponents.webhookInput) {
    return i18n.t("sidebar.webhookAdded");
  }
  return "";
};
