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
});
