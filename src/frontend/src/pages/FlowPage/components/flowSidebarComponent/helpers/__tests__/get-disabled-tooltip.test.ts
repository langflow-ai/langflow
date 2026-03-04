import { getDisabledTooltip } from "../get-disabled-tooltip";
import type { UniqueInputsComponents } from "../../types";

describe("getDisabledTooltip - mutual exclusivity", () => {
  it("should return tooltip when trying to add ChatInput while Webhook exists", () => {
    const uniqueInputs: UniqueInputsComponents = {
      chatInput: false,
      webhookInput: true,
    };

    expect(getDisabledTooltip("ChatInput", uniqueInputs)).toBe(
      "Cannot add Chat Input when Webhook is present",
    );
  });

  it("should return tooltip when trying to add Webhook while ChatInput exists", () => {
    const uniqueInputs: UniqueInputsComponents = {
      chatInput: true,
      webhookInput: false,
    };

    expect(getDisabledTooltip("Webhook", uniqueInputs)).toBe(
      "Cannot add Webhook when Chat Input is present",
    );
  });
});
