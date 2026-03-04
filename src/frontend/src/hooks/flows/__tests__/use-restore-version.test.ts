import { renderHook, act } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks — hoisted before imports
// ---------------------------------------------------------------------------

const invalidateQueriesMock = jest.fn();
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: invalidateQueriesMock }),
}));

const apiPostMock = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { post: (...args: any[]) => apiPostMock(...args) },
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
  default: (selector: any) =>
    selector({
      setSuccessData: setSuccessDataMock,
      setErrorData: setErrorDataMock,
    }),
}));

const clearPreviewMock = jest.fn();
const setPreviewStateMock = jest.fn();
jest.mock("@/stores/versionPreviewStore", () => {
  const store: any = (selector: any) =>
    selector({ clearPreview: clearPreviewMock });
  store.getState = () => ({
    clearPreview: clearPreviewMock,
    didRestore: false,
  });
  store.setState = (...args: any[]) => setPreviewStateMock(...args);
  return { __esModule: true, default: store };
});

// ---------------------------------------------------------------------------
// Import hook AFTER all mocks are set up
// ---------------------------------------------------------------------------

import useRestoreVersion from "../use-restore-version";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useRestoreVersion", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("calls activate endpoint, applies flow, clears preview, and shows success", async () => {
    const flowData = {
      id: "flow-1",
      data: { nodes: [{ id: "n1" }], edges: [{ id: "e1" }] },
    };
    apiPostMock.mockResolvedValueOnce({ data: flowData });

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1");
    });

    // Should POST to the activate endpoint
    expect(apiPostMock).toHaveBeenCalledWith(
      "/api/v1/flows/flow-1/versions/entry-1/activate",
      null,
      { params: { save_draft: true } },
    );

    // Should invalidate version queries
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["useGetFlowVersions"],
    });

    // Should apply the flow to canvas (without ?? [] fallback — uses real data)
    expect(applyFlowToCanvasMock).toHaveBeenCalledWith(flowData);

    // Should signal didRestore before clearing preview
    expect(setPreviewStateMock).toHaveBeenCalledWith({ didRestore: true });

    // Should clear the preview
    expect(clearPreviewMock).toHaveBeenCalled();

    // Should show success
    expect(setSuccessDataMock).toHaveBeenCalledWith({
      title: "Version restored",
    });

    // isRestoring should be false after completion
    expect(result.current.isRestoring).toBe(false);
  });

  it("calls onSuccess callback after successful restore", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: { id: "flow-1", data: { nodes: [{ id: "n1" }], edges: [] } },
    });
    const onSuccessMock = jest.fn();

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1", { onSuccess: onSuccessMock });
    });

    expect(onSuccessMock).toHaveBeenCalled();
  });

  it("shows error when API returns null data", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: { id: "flow-1", data: null },
    });

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1");
    });

    // Should NOT apply to canvas
    expect(applyFlowToCanvasMock).not.toHaveBeenCalled();

    // Should show error with our guard message
    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "Failed to restore version",
      list: ["Restored version contains no flow data"],
    });

    expect(result.current.isRestoring).toBe(false);
  });

  it("shows API error detail when API call fails", async () => {
    apiPostMock.mockRejectedValueOnce({
      response: { data: { detail: "Version not found" } },
    });

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1");
    });

    expect(applyFlowToCanvasMock).not.toHaveBeenCalled();

    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "Failed to restore version",
      list: ["Version not found"],
    });
  });

  it("shows applyFlowToCanvas error message (not API detail) when canvas apply throws", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: { id: "flow-1", data: { nodes: [{ id: "n1" }], edges: [] } },
    });
    applyFlowToCanvasMock.mockImplementationOnce(() => {
      throw new Error("processFlows destroyed all nodes — aborting");
    });

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1");
    });

    // Should show the thrown error message, not an empty API detail
    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "Failed to restore version",
      list: ["processFlows destroyed all nodes — aborting"],
    });
  });

  it("sets isRestoring to true during restore and false after", async () => {
    let resolvePost: (value: any) => void;
    apiPostMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolvePost = resolve;
      }),
    );

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    expect(result.current.isRestoring).toBe(false);

    let restorePromise: Promise<void>;
    act(() => {
      restorePromise = result.current.restore("entry-1");
    });

    // isRestoring should be true while waiting
    expect(result.current.isRestoring).toBe(true);

    await act(async () => {
      resolvePost!({
        data: { id: "flow-1", data: { nodes: [{ id: "n1" }], edges: [] } },
      });
      await restorePromise!;
    });

    expect(result.current.isRestoring).toBe(false);
  });

  it("does not call onSuccess when restore fails", async () => {
    apiPostMock.mockRejectedValueOnce(new Error("Network error"));
    const onSuccessMock = jest.fn();

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1", { onSuccess: onSuccessMock });
    });

    expect(onSuccessMock).not.toHaveBeenCalled();
  });

  it("falls back to 'Unknown error' when error has no message or API detail", async () => {
    apiPostMock.mockRejectedValueOnce({});

    const { result } = renderHook(() => useRestoreVersion("flow-1"));

    await act(async () => {
      await result.current.restore("entry-1");
    });

    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "Failed to restore version",
      list: ["Unknown error"],
    });
  });
});
