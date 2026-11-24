import { disableItem } from "../disable-item";

describe("disableItem", () => {
  describe("ChatInput component", () => {
    it("should disable ChatInput when ChatInput already exists", () => {
      expect(disableItem("ChatInput", new Set(["ChatInput"]))).toBe(true);
    });

    it("should disable ChatInput when Webhook exists (mutual exclusivity)", () => {
      expect(disableItem("ChatInput", new Set(["Webhook"]))).toBe(true);
    });

    it("should not disable ChatInput when neither exists", () => {
      expect(disableItem("ChatInput", new Set())).toBe(false);
    });

    it("should disable ChatInput when both exist (edge case)", () => {
      expect(disableItem("ChatInput", new Set(["ChatInput", "Webhook"]))).toBe(
        true,
      );
    });
  });

  describe("Webhook component", () => {
    it("should disable Webhook when Webhook already exists", () => {
      expect(disableItem("Webhook", new Set(["Webhook"]))).toBe(true);
    });

    it("should disable Webhook when ChatInput exists (mutual exclusivity)", () => {
      expect(disableItem("Webhook", new Set(["ChatInput"]))).toBe(true);
    });

    it("should not disable Webhook when neither exists", () => {
      expect(disableItem("Webhook", new Set())).toBe(false);
    });
  });

  describe("Other components", () => {
    it("should not disable other components when both ChatInput and Webhook exist", () => {
      expect(
        disableItem("SomeOtherComponent", new Set(["ChatInput", "Webhook"])),
      ).toBe(false);
    });

    it("should not disable other components when only ChatInput exists", () => {
      expect(disableItem("TextInput", new Set(["ChatInput"]))).toBe(false);
    });

    it("should not disable other components when only Webhook exists", () => {
      expect(disableItem("TextInput", new Set(["Webhook"]))).toBe(false);
    });
  });
});
