import {
  RUN_POLL_MS,
  RUNS_LIST_POLL_MS,
  runRefetchInterval,
  runsListRefetchInterval,
} from "../polling";

describe("runRefetchInterval", () => {
  it("should poll a run that is still going", () => {
    expect(
      runRefetchInterval({ status: "success", data: { status: "running" } }),
    ).toBe(RUN_POLL_MS);
    expect(
      runRefetchInterval({ status: "success", data: { status: "queued" } }),
    ).toBe(RUN_POLL_MS);
  });

  it("should poll while the first load is pending", () => {
    expect(runRefetchInterval({ status: "pending", data: undefined })).toBe(
      RUN_POLL_MS,
    );
  });

  it.each(["completed", "failed", "cancelled"])(
    "should stop polling a %s run",
    (status) => {
      expect(runRefetchInterval({ status: "success", data: { status } })).toBe(
        false,
      );
    },
  );

  it("should stop polling when the run cannot be loaded", () => {
    expect(runRefetchInterval({ status: "error", data: undefined })).toBe(
      false,
    );
    expect(
      runRefetchInterval({ status: "error", data: { status: "running" } }),
    ).toBe(false);
  });
});

describe("runsListRefetchInterval", () => {
  it("should poll slowly while one run is still going", () => {
    expect(
      runsListRefetchInterval({
        status: "success",
        data: { items: [{ status: "completed" }, { status: "running" }] },
      }),
    ).toBe(RUNS_LIST_POLL_MS);
  });

  it("should not poll when every run ended, nothing loaded, or the list failed", () => {
    expect(
      runsListRefetchInterval({
        status: "success",
        data: { items: [{ status: "completed" }] },
      }),
    ).toBe(false);
    expect(
      runsListRefetchInterval({ status: "pending", data: undefined }),
    ).toBe(false);
    expect(
      runsListRefetchInterval({
        status: "error",
        data: { items: [{ status: "running" }] },
      }),
    ).toBe(false);
  });

  const comparisonRun = (
    status: string,
    index: number,
    finishedAt: string | null,
  ) => ({
    status,
    finished_at: finishedAt,
    config: { comparison: { id: "c", index, variants: [[], [], []] } },
  });
  const now = Date.parse("2026-10-30T12:00:00Z");

  it("should follow an active comparison as fast as a run", () => {
    expect(
      runsListRefetchInterval({
        status: "success",
        data: { items: [comparisonRun("running", 1, null)] },
      }),
    ).toBe(RUN_POLL_MS);
  });

  it("should keep polling briefly while a comparison starts its next variant", () => {
    const justEnded = comparisonRun("completed", 0, "2026-10-30T11:59:50Z");
    expect(
      runsListRefetchInterval(
        { status: "success", data: { items: [justEnded] } },
        now,
      ),
    ).toBe(RUN_POLL_MS);
  });

  it("should stop once the last variant ended, a variant was cancelled, or the next never came", () => {
    const cases = [
      comparisonRun("completed", 2, "2026-10-30T11:59:50Z"),
      comparisonRun("cancelled", 0, "2026-10-30T11:59:50Z"),
      comparisonRun("completed", 0, "2026-10-30T11:50:00Z"),
      comparisonRun("failed", 0, null),
    ];
    for (const run of cases) {
      expect(
        runsListRefetchInterval(
          { status: "success", data: { items: [run] } },
          now,
        ),
      ).toBe(false);
    }
  });

  it("should read the latest run of an oldest-first comparison list", () => {
    const first = {
      ...comparisonRun("completed", 0, "2026-10-30T11:59:40Z"),
      created_at: "2026-10-30T11:58:00Z",
    };
    const second = {
      ...comparisonRun("completed", 1, "2026-10-30T11:59:50Z"),
      created_at: "2026-10-30T11:59:00Z",
    };
    expect(
      runsListRefetchInterval(
        { status: "success", data: { items: [first, second] } },
        now,
      ),
    ).toBe(RUN_POLL_MS);
    const last = {
      ...comparisonRun("completed", 2, "2026-10-30T11:59:55Z"),
      created_at: "2026-10-30T11:59:30Z",
    };
    expect(
      runsListRefetchInterval(
        { status: "success", data: { items: [first, second, last] } },
        now,
      ),
    ).toBe(false);
  });
});
