jest.mock("@/controllers/API/api", () => ({ api: { get: jest.fn() } }));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

import { isRevisionNotRetained } from "../use-get-flow-revision";

const failure = (status: number, code?: string) => ({
  response: { status, data: { detail: code ? { code } : "Not found" } },
});

describe("isRevisionNotRetained", () => {
  it("is true only for a revision compaction removed", () => {
    expect(
      isRevisionNotRetained(failure(410, "FLOW_REVISION_NOT_RETAINED")),
    ).toBe(true);
    expect(isRevisionNotRetained(failure(404, "FLOW_REVISION_NOT_FOUND"))).toBe(
      false,
    );
    expect(isRevisionNotRetained(failure(410))).toBe(false);
    expect(isRevisionNotRetained(new Error("Network Error"))).toBe(false);
    expect(isRevisionNotRetained(null)).toBe(false);
  });
});
