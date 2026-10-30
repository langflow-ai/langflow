import { TRIGGER_PLACEMENT_KEY } from "@/utils/componentConstraints";
import { getDisabledTooltip } from "../get-disabled-tooltip";

describe("getDisabledTooltip", () => {
  describe("Trigger components", () => {
    it("explains the one-trigger rule when the flow already has a trigger", () => {
      expect(
        getDisabledTooltip(
          ["SlackOnMessage", TRIGGER_PLACEMENT_KEY],
          new Set(["ScheduleTrigger", TRIGGER_PLACEMENT_KEY]),
        ),
      ).toBe("This flow already has a trigger. A flow has one trigger.");
    });

    it("allows the first trigger", () => {
      expect(
        getDisabledTooltip(
          ["ScheduleTrigger", TRIGGER_PLACEMENT_KEY],
          new Set(),
        ),
      ).toBe("");
    });
  });

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
