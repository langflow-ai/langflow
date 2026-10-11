import { act, renderHook } from "@testing-library/react";

const invalidateQueriesMock = jest.fn();
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: invalidateQueriesMock }),
}));

const apiPostMock = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: unknown[]) => apiPostMock(...args) },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

const applyFlowToCanvasMock = jest.fn();
jest.mock("@/hooks/flows/use-apply-flow-to-canvas", () => ({
  __esModule: true,
  default: () => applyFlowToCanvasMock,
}));

const setSuccessDataMock = jest.fn();
const setErrorDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: object) => unknown) =>
    selector({
      setSuccessData: setSuccessDataMock,
      setErrorData: setErrorDataMock,
    }),
}));

// The fixes the preview made: it dropped the revision's broken edge.
let previewFixes: unknown[] = [];
const clearPreviewMock = jest.fn();
jest.mock("@/stores/versionPreviewStore", () => {
  const store = (selector: (state: object) => unknown) =>
    selector({ clearPreview: clearPreviewMock });
  return {
    __esModule: true,
    default: Object.assign(store, {
      setState: jest.fn(),
      getState: () => ({ previewFixes }),
    }),
  };
});

import useRestoreRevision from "../use-restore-revision";

const URL = "/api/v1/flows/flow-1/revisions/7/restore";

function refused(violations: { resolution: string; message: string }[]) {
  return {
    response: {
      status: 422,
      data: {
        detail: {
          code: "FLOW_GRAPH_INVALID",
          message: "The submitted flow breaks the flow graph rules.",
          violations: violations.map((violation) => ({
            code: "EDGE_HANDLE_NOT_FOUND",
            path: ["edges", 0],
            edge_id: "e",
            ...violation,
          })),
        },
      },
    },
  };
}

async function restore() {
  const { result } = renderHook(() => useRestoreRevision("flow-1"));
  await act(async () => {
    await result.current.restore(7);
  });
}

describe("useRestoreRevision", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // The preview dropped the broken edge "e" and respelled the handles of
    // "fine", which breaks no rule.
    previewFixes = [
      { type: "delete_edges", ids: ["e"] },
      {
        type: "update_edges",
        updates: [
          { id: "fine", op: "set_field", path: ["sourceHandle"], value: "s" },
        ],
      },
    ];
  });

  it("restores without sending fixes", async () => {
    apiPostMock.mockResolvedValueOnce({ data: { id: "flow-1" } });

    await restore();

    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock.mock.calls[0][0]).toBe(URL);
    expect(apiPostMock.mock.calls[0][1]).not.toHaveProperty("fixes");
    expect(applyFlowToCanvasMock).toHaveBeenCalledWith({ id: "flow-1" });
    expect(setSuccessDataMock).toHaveBeenCalledWith({
      title: "Version restored",
    });
  });

  it("resends a restore the client must fix with the preview's fixes for the flagged edges", async () => {
    apiPostMock
      .mockRejectedValueOnce(
        refused([{ resolution: "client", message: "edge e: no output gone" }]),
      )
      .mockResolvedValueOnce({ data: { id: "flow-1" } });

    await restore();

    expect(apiPostMock).toHaveBeenCalledTimes(2);
    const [url, body] = apiPostMock.mock.calls[1];
    expect(url).toBe(URL);
    expect(body.fixes).toEqual([{ type: "delete_edges", ids: ["e"] }]);
    expect(body.request_id).not.toBe(apiPostMock.mock.calls[0][1].request_id);
    expect(applyFlowToCanvasMock).toHaveBeenCalledWith({ id: "flow-1" });
    expect(setSuccessDataMock).toHaveBeenCalledWith({
      title:
        "Version restored without the connections its components no longer have",
      list: ["edge e: no output gone"],
    });
  });

  it("does not resend when a violation is not the client's to fix", async () => {
    apiPostMock.mockRejectedValueOnce(
      refused([
        { resolution: "client", message: "edge e: no output gone" },
        {
          resolution: "repair",
          message: "edge f: data.sourceHandle is missing",
        },
      ]),
    );

    await restore();

    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(applyFlowToCanvasMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "Failed to restore version",
      list: ["The submitted flow breaks the flow graph rules."],
    });
  });

  it("does not resend when the preview fixed nothing", async () => {
    previewFixes = [];
    apiPostMock.mockRejectedValueOnce(
      refused([{ resolution: "client", message: "edge e: no output gone" }]),
    );

    await restore();

    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(setErrorDataMock).toHaveBeenCalledTimes(1);
  });

  it("reports a resend that is refused again", async () => {
    apiPostMock
      .mockRejectedValueOnce(
        refused([{ resolution: "client", message: "edge e: no output gone" }]),
      )
      .mockRejectedValueOnce(
        refused([{ resolution: "client", message: "edge g: target taken" }]),
      );

    await restore();

    expect(apiPostMock).toHaveBeenCalledTimes(2);
    expect(applyFlowToCanvasMock).not.toHaveBeenCalled();
    expect(setSuccessDataMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).toHaveBeenCalledTimes(1);
  });
});
