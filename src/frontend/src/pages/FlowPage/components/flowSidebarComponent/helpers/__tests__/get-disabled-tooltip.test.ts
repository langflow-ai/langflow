import { getDisabledTooltip } from "../get-disabled-tooltip";
import type { UniqueInputsComponents } from "../../types";

describe("getDisabledTooltip", () => {
  describe("ChatInput component", () => {
    it("should return tooltip when ChatInput already exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: false,
      };

      expect(getDisabledTooltip("ChatInput", uniqueInputs)).toBe(
        "Chat input already added",
      );
    });

    it("should return tooltip when trying to add ChatInput while Webhook exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: true,
      };

      expect(getDisabledTooltip("ChatInput", uniqueInputs)).toBe(
        "Cannot add Chat Input when Webhook is present",
      );
    });

    it("should return empty string when ChatInput can be added", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: false,
      };

      expect(getDisabledTooltip("ChatInput", uniqueInputs)).toBe("");
    });
  });

  describe("Webhook component", () => {
    it("should return tooltip when Webhook already exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: true,
      };

      expect(getDisabledTooltip("Webhook", uniqueInputs)).toBe(
        "Webhook already added",
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

    it("should return empty string when Webhook can be added", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: false,
      };

      expect(getDisabledTooltip("Webhook", uniqueInputs)).toBe("");
    });
  });

  describe("Other components", () => {
    it("should return empty string for other components", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: true,
      };

      expect(getDisabledTooltip("SomeOtherComponent", uniqueInputs)).toBe("");
    });
  });
});
