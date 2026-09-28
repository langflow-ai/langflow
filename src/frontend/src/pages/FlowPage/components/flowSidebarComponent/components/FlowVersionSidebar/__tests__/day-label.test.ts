import i18n from "@/i18n";
import { dayLabel } from "../utils";

const t = (key: string, opts?: object) => i18n.t(key, opts) as string;

describe("dayLabel", () => {
  const now = new Date(2026, 8, 28, 10, 0);

  it("groups by calendar day, not by 24-hour windows", () => {
    expect(dayLabel(new Date(2026, 8, 28, 0, 5).toISOString(), t, now)).toBe(
      "Today",
    );
    expect(dayLabel(new Date(2026, 8, 27, 23, 55).toISOString(), t, now)).toBe(
      "Yesterday",
    );
  });

  it("shows older days as dates, with the year only when it differs", () => {
    expect(dayLabel(new Date(2026, 8, 20).toISOString(), t, now)).not.toMatch(
      /2026/,
    );
    expect(dayLabel(new Date(2025, 8, 20).toISOString(), t, now)).toMatch(
      /2025/,
    );
  });

  it("labels a missing or unreadable date", () => {
    expect(dayLabel(null, t, now)).toBe("Unknown date");
    expect(dayLabel("not a date", t, now)).toBe("Unknown date");
  });
});
