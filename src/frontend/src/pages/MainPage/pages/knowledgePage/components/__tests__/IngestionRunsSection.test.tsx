import { formatRelativeTime } from "../IngestionRunsSection";

describe("formatRelativeTime", () => {
  // Guard the native time zone so UTC cannot hide the original parsing bug.
  beforeAll(() => {
    expect(new Date("2026-10-16T12:00:00Z").getTimezoneOffset()).toBe(180);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  // On SQLite the runs API sends started_at without a zone. It is UTC all the same.
  it.each([
    "2026-10-16T12:00:00.123456",
    "2026-10-16T12:00:00.123456Z",
    "2026-10-16T12:00:00.123456+00:00",
  ])("reads %s as 15 minutes ago", (sent) => {
    jest.useFakeTimers().setSystemTime(Date.parse("2026-10-16T12:15:30Z"));

    expect(formatRelativeTime(sent)).toBe("15m ago");
  });
});
