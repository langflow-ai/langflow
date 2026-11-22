import {
  DEFAULT_TRIGGER_POLLING_INTERVAL,
  MIN_TRIGGER_POLLING_INTERVAL,
  normalizeTriggerPollingInterval,
} from "../constants";

describe("normalizeTriggerPollingInterval", () => {
  it("keeps a valid interval", () => {
    expect(normalizeTriggerPollingInterval(7000)).toBe(7000);
  });

  it("never polls faster than the backend minimum", () => {
    expect(normalizeTriggerPollingInterval(10)).toBe(
      MIN_TRIGGER_POLLING_INTERVAL,
    );
    expect(normalizeTriggerPollingInterval(-5)).toBe(
      MIN_TRIGGER_POLLING_INTERVAL,
    );
  });

  it.each([undefined, null, "5000", Number.NaN, Number.POSITIVE_INFINITY])(
    "falls back to the default for %p",
    (value) => {
      expect(normalizeTriggerPollingInterval(value)).toBe(
        DEFAULT_TRIGGER_POLLING_INTERVAL,
      );
    },
  );
});
