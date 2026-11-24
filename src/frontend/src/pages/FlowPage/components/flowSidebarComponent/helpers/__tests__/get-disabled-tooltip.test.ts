import { getDisabledTooltip } from "../get-disabled-tooltip";

describe("getDisabledTooltip", () => {
  describe("ChatInput component", () => {
    it("should return tooltip when ChatInput already exists", () => {
      expect(getDisabledTooltip("ChatInput", new Set(["ChatInput"]))).toBe(
        "Chat input already added",
      );
    });

    it("should return tooltip when trying to add ChatInput while Webhook exists", () => {
      expect(getDisabledTooltip("ChatInput", new Set(["Webhook"]))).toBe(
        "Cannot add Chat Input when Webhook is present",
      );
    });

    it("should return empty string when ChatInput can be added", () => {
      expect(getDisabledTooltip("ChatInput", new Set())).toBe("");
    });
  });

  describe("Webhook component", () => {
    it("should return tooltip when Webhook already exists", () => {
      expect(getDisabledTooltip("Webhook", new Set(["Webhook"]))).toBe(
        "Webhook already added",
      );
    });

    it("should return tooltip when trying to add Webhook while ChatInput exists", () => {
      expect(getDisabledTooltip("Webhook", new Set(["ChatInput"]))).toBe(
        "Cannot add Webhook when Chat Input is present",
      );
    });

    it("should return empty string when Webhook can be added", () => {
      expect(getDisabledTooltip("Webhook", new Set())).toBe("");
    });
  });

  describe("Other components", () => {
    it("should return empty string for other components", () => {
      expect(
        getDisabledTooltip(
          "SomeOtherComponent",
          new Set(["ChatInput", "Webhook"]),
        ),
      ).toBe("");
    });
  });
});
