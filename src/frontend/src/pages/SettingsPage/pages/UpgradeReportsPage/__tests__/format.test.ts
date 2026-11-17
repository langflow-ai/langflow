import { reportAge, reportTime } from "../format";

const now = Date.parse("2026-11-18T19:00:00Z");

it.each([
  [0, "now"],
  [59_000, "59 seconds ago"],
  [60_000, "1 minute ago"],
  [3_600_000, "1 hour ago"],
  [86_400_000, "yesterday"],
  [3 * 86_400_000, "3 days ago"],
  [6 * 86_400_000, "6 days ago"],
  [7 * 86_400_000, "last week"],
  [14 * 86_400_000, "2 weeks ago"],
  [-2 * 86_400_000, "in 2 days"],
])("formats an age of %s milliseconds as %s", (elapsed, expected) => {
  expect(
    reportAge(new Date(now - elapsed).toISOString(), "en", "Unknown", now),
  ).toBe(expected);
});

it.each([null, undefined, "", "not-a-date"])(
  "keeps invalid age %s unknown",
  (value) => {
    expect(reportAge(value, "en", "Unknown", now)).toBe("Unknown");
    expect(reportTime(value, "en", "Unknown")).toBe("Unknown");
  },
);

it("formats report ages in the active locale", () => {
  expect(reportAge("2026-11-04T19:00:00Z", "de", "Unbekannt", now)).toBe(
    "vor 2 Wochen",
  );
});
