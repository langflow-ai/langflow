import { formatRelativeTime } from "../IngestionRunsSection";

describe("formatRelativeTime", () => {
  const zone = process.env.TZ;

  // Behind UTC, a time read as local lands in the future and showed as "0s ago".
  beforeAll(() => {
    process.env.TZ = "America/Sao_Paulo";
  });

  afterAll(() => {
    process.env.TZ = zone;
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
