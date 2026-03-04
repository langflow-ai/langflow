import { disableItem } from "../disable-item";
import type { UniqueInputsComponents } from "../../types";

describe("disableItem", () => {
  describe("ChatInput component", () => {
    it("should disable ChatInput when ChatInput already exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: false,
      };

      expect(disableItem("ChatInput", uniqueInputs)).toBe(true);
    });

    it("should disable ChatInput when Webhook exists (mutual exclusivity)", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: true,
      };

      expect(disableItem("ChatInput", uniqueInputs)).toBe(true);
    });

    it("should not disable ChatInput when neither exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: false,
      };

      expect(disableItem("ChatInput", uniqueInputs)).toBe(false);
    });

    it("should disable ChatInput when both exist (edge case)", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: true,
      };

      expect(disableItem("ChatInput", uniqueInputs)).toBe(true);
    });
  });

  describe("Webhook component", () => {
    it("should disable Webhook when Webhook already exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: true,
      };

      expect(disableItem("Webhook", uniqueInputs)).toBe(true);
    });

    it("should disable Webhook when ChatInput exists (mutual exclusivity)", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: false,
      };

      expect(disableItem("Webhook", uniqueInputs)).toBe(true);
    });

    it("should not disable Webhook when neither exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: false,
      };

      expect(disableItem("Webhook", uniqueInputs)).toBe(false);
    });
  });

  describe("Other components", () => {
    it("should not disable other components when both ChatInput and Webhook exist", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: true,
      };

      expect(disableItem("SomeOtherComponent", uniqueInputs)).toBe(false);
    });

    it("should not disable other components when only ChatInput exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: true,
        webhookInput: false,
      };

      expect(disableItem("TextInput", uniqueInputs)).toBe(false);
    });

    it("should not disable other components when only Webhook exists", () => {
      const uniqueInputs: UniqueInputsComponents = {
        chatInput: false,
        webhookInput: true,
      };

      expect(disableItem("TextInput", uniqueInputs)).toBe(false);
    });
  });
});
