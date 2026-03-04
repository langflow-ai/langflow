import { disableItem } from "../disable-item";
import type { UniqueInputsComponents } from "../../types";

describe("disableItem - mutual exclusivity", () => {
  it("should disable ChatInput when Webhook exists", () => {
    const uniqueInputs: UniqueInputsComponents = {
      chatInput: false,
      webhookInput: true,
    };

    expect(disableItem("ChatInput", uniqueInputs)).toBe(true);
  });

  it("should disable Webhook when ChatInput exists", () => {
    const uniqueInputs: UniqueInputsComponents = {
      chatInput: true,
      webhookInput: false,
    };

    expect(disableItem("Webhook", uniqueInputs)).toBe(true);
  });
});

