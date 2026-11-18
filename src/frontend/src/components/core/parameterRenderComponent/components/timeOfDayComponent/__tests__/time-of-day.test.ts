import {
  formatTimeOfDay,
  parseTimeOfDay,
  suggestedTimes,
} from "../helpers/time-of-day";

const plain = (text: string) => text.replace(/[  ]/g, " ");

describe("time of day", () => {
  it("should_show_a_saved_time_in_the_readers_clock", () => {
    expect(plain(formatTimeOfDay("18:30", "en"))).toBe("6:30 PM");
    expect(plain(formatTimeOfDay("08:05", "en"))).toBe("8:05 AM");
    expect(formatTimeOfDay("18:30", "pt")).toBe("18:30");
    expect(formatTimeOfDay("18:30", "de")).toBe("18:30");
  });

  it.each([
    ["18:30", "18:30"],
    ["8:05", "08:05"],
    ["6:30 PM", "18:30"],
    ["6:30pm", "18:30"],
    ["12:00 AM", "00:00"],
    ["12:15 p.m.", "12:15"],
    ["7 am", "07:00"],
  ])("should_save_%s_as_%s", (typed, saved) => {
    expect(parseTimeOfDay(typed, "en")).toBe(saved);
  });

  it("should_read_back_whatever_the_locale_shows", () => {
    const shown = formatTimeOfDay("18:30", "ko");
    expect(parseTimeOfDay(shown, "ko")).toBe("18:30");
  });

  it.each(["24:00", "13:00 PM", "eight", "", "8:60"])(
    "should_refuse_%s",
    (typed) => {
      expect(parseTimeOfDay(typed, "en")).toBeNull();
    },
  );

  it("should_suggest_every_half_hour", () => {
    const times = suggestedTimes("en");
    expect(times).toHaveLength(48);
    expect(plain(times[1])).toBe("12:30 AM");
  });
});
