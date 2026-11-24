import {
  CHAT_INPUT_COMPONENT,
  evaluatePlacement,
  WEBHOOK_COMPONENT,
} from "@/utils/componentConstraints";
import { TOOLTIP_MESSAGES } from "./constants";

/**
 * Tooltip explaining why a sidebar item is disabled. Derives the reason from
 * the shared constraint engine and maps it to the corresponding message, so the
 * policy is never re-encoded here.
 */
export const getDisabledTooltip = (
  SBItemName: string,
  presentTypes: ReadonlySet<string>,
): string => {
  const violation = evaluatePlacement(SBItemName, presentTypes);
  if (!violation) {
    return "";
  }

  if (violation.reason === "singleton") {
    if (violation.type === CHAT_INPUT_COMPONENT) {
      return TOOLTIP_MESSAGES.CHAT_INPUT_ALREADY_ADDED;
    }
    if (violation.type === WEBHOOK_COMPONENT) {
      return TOOLTIP_MESSAGES.WEBHOOK_ALREADY_ADDED;
    }
  }

  if (violation.reason === "exclusivity") {
    if (violation.type === CHAT_INPUT_COMPONENT) {
      return TOOLTIP_MESSAGES.CANNOT_ADD_CHAT_INPUT_WITH_WEBHOOK;
    }
    if (violation.type === WEBHOOK_COMPONENT) {
      return TOOLTIP_MESSAGES.CANNOT_ADD_WEBHOOK_WITH_CHAT_INPUT;
    }
  }

  return "";
};
