/**
 * useAssistantRevert orchestration: a safety snapshot of the CURRENT flow
 * state is created FIRST ("pre-revert <timestamp>"), then the target version
 * is restored via the shared useRestoreVersion mechanism (saveDraft=false so
 * the activate endpoint doesn't duplicate the safety snapshot). A snapshot
 * failure aborts the revert and surfaces the standard error alert.
 */

import { act, renderHook } from "@testing-library/react";

const callOrder: string[] = [];

const createSnapshotMock = jest.fn(async () => {
  callOrder.push("snapshot");
  return { id: "safety-1" };
});
jest.mock("@/controllers/API/queries/flow-version", () => ({
  usePostCreateSnapshot: () => ({ mutateAsync: createSnapshotMock }),
}));

const restoreMock = jest.fn(async () => {
  callOrder.push("restore");
});
const restoreHookMock = jest.fn();
jest.mock("@/hooks/flows/use-restore-version", () => ({
  __esModule: true,
  default: (...args: unknown[]) => {
    restoreHookMock(...args);
    return { restore: restoreMock, isRestoring: false };
  },
}));

const setErrorDataMock = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ setErrorData: setErrorDataMock }),
}));

let currentFlowIdMock: string | undefined = "flow-1";
let currentFlowMock = { id: "flow-1", version_token: "persisted-token" };
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      currentFlowId: currentFlowIdMock,
      currentFlow: currentFlowMock,
    }),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

import { useAssistantRevert } from "../use-assistant-revert";

describe("useAssistantRevert", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    callOrder.length = 0;
    currentFlowIdMock = "flow-1";
    currentFlowMock = { id: "flow-1", version_token: "persisted-token" };
  });

  it("should_create_the_safety_snapshot_before_restoring", async () => {
    const { result } = renderHook(() => useAssistantRevert());

    await act(async () => {
      await result.current.revert("ver-1");
    });

    expect(callOrder).toEqual(["snapshot", "restore"]);
    expect(createSnapshotMock).toHaveBeenCalledWith({
      flowId: "flow-1",
      description: expect.stringMatching(
        /^pre-revert \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$/,
      ),
    });
    expect(restoreMock).toHaveBeenCalledWith("ver-1", {
      saveDraft: false,
      onSuccess: undefined,
    });
  });

  it("should pass the persisted flow token for assistant revert", async () => {
    const { result } = renderHook(() => useAssistantRevert());
    await act(async () => {
      await result.current.revert("ver-1");
    });

    expect(restoreHookMock).toHaveBeenCalledWith("flow-1", "persisted-token");
  });

  it("should not use a token belonging to another flow", async () => {
    currentFlowMock = { id: "different-flow", version_token: "other-token" };
    renderHook(() => useAssistantRevert());

    expect(restoreHookMock).toHaveBeenCalledWith("flow-1", undefined);
  });

  it("should_propagate_onSuccess_to_the_restore_call", async () => {
    const onSuccess = jest.fn();
    const { result } = renderHook(() => useAssistantRevert());

    await act(async () => {
      await result.current.revert("ver-1", { onSuccess });
    });

    expect(restoreMock).toHaveBeenCalledWith("ver-1", {
      saveDraft: false,
      onSuccess,
    });
  });

  it("should_abort_and_show_the_error_alert_when_the_snapshot_fails", async () => {
    createSnapshotMock.mockRejectedValueOnce({
      response: { data: { detail: "Snapshot quota exceeded" } },
    });
    const { result } = renderHook(() => useAssistantRevert());

    await act(async () => {
      await result.current.revert("ver-1");
    });

    expect(restoreMock).not.toHaveBeenCalled();
    expect(setErrorDataMock).toHaveBeenCalledWith({
      title: "assistant.revert.errorTitle",
      list: ["Snapshot quota exceeded"],
    });
    expect(result.current.isReverting).toBe(false);
  });

  it("should_do_nothing_when_there_is_no_current_flow", async () => {
    currentFlowIdMock = undefined;
    const { result } = renderHook(() => useAssistantRevert());

    await act(async () => {
      await result.current.revert("ver-1");
    });

    expect(createSnapshotMock).not.toHaveBeenCalled();
    expect(restoreMock).not.toHaveBeenCalled();
  });
});
