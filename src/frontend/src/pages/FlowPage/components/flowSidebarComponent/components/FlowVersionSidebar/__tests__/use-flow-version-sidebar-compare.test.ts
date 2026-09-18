/**
 * Compare-mode state machine.
 *
 * The regression that matters here: handleSelectEntry normally drives the canvas
 * preview (setSelectedId cascades into useFlowStore.setState + fitView). While a
 * comparison target is being picked, a row click must set the target instead, or
 * picking a version to compare against would silently swap the canvas.
 */
import { act, renderHook } from "@testing-library/react";
import type { FlowVersionEntry } from "@/types/flow/version";

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  downloadFlow: jest.fn(),
  processFlows: jest.fn(),
  removeApiKeys: jest.fn((flow: unknown) => flow),
}));

jest.mock("@/controllers/API/api", () => ({
  api: { get: jest.fn(), post: jest.fn() },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/flows",
}));

const versionEntries: FlowVersionEntry[] = [
  {
    id: "entry-1",
    flow_id: "flow-1",
    user_id: "user-1",
    version_number: 1,
    version_tag: "v1",
    description: "first",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "entry-2",
    flow_id: "flow-1",
    user_id: "user-1",
    version_number: 2,
    version_tag: "v2",
    description: "second",
    created_at: "2026-01-02T00:00:00Z",
  },
];

jest.mock("@/controllers/API/queries/flow-version", () => ({
  useGetFlowVersions: () => ({
    data: { entries: versionEntries, max_entries: 50 },
    isLoading: false,
    isError: false,
  }),
  useGetFlowVersionEntry: () => ({
    data: null,
    isLoading: false,
    isError: false,
  }),
  useDeleteVersionEntry: () => ({ mutate: jest.fn(), isPending: false }),
}));

type Loose = Record<string, unknown>;

const storeState: Loose = {
  currentFlow: {
    id: "flow-1",
    name: "Test Flow",
    data: { nodes: [], edges: [] },
  },
  nodes: [{ id: "draft-node" }],
  edges: [{ id: "draft-edge" }],
  autoSaveFlow: undefined,
  inspectionPanelVisible: false,
  reactFlowInstance: { fitView: jest.fn() },
};

const flowSetStateMock = jest.fn((partial: Loose) => {
  Object.assign(storeState, partial);
});

jest.mock("@/stores/flowStore", () => {
  const store = ((selector: (state: Loose) => unknown) =>
    selector(storeState)) as unknown as Record<string, unknown> &
    ((selector: (state: Loose) => unknown) => unknown);
  store.getState = () => storeState;
  store.setState = (partial: Loose) => flowSetStateMock(partial);
  store.subscribe = jest.fn(() => () => {});
  return { __esModule: true, default: store };
});

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: Loose) => unknown) =>
    selector({ setSuccessData: jest.fn(), setErrorData: jest.fn() }),
}));

const setPreviewMock = jest.fn();
jest.mock("@/stores/versionPreviewStore", () => {
  const state = {
    previewId: null,
    isPreviewLoading: false,
    didRestore: false,
    setPreview: setPreviewMock,
    clearPreview: jest.fn(),
    setPreviewLoading: jest.fn(),
  };
  const store = ((selector: (value: Loose) => unknown) =>
    selector(state)) as unknown as Record<string, unknown> &
    ((selector: (value: Loose) => unknown) => unknown);
  store.getState = () => state;
  store.setState = jest.fn();
  return { __esModule: true, default: store };
});

import { CURRENT_DRAFT_ID } from "../constants";
import { useFlowVersionSidebar } from "../use-flow-version-sidebar";

beforeEach(() => {
  setPreviewMock.mockClear();
  flowSetStateMock.mockClear();
});

describe("compare mode", () => {
  it("is inactive until a comparison is started", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    expect(result.current.compareBaseId).toBeNull();
    expect(result.current.compareTargetId).toBeNull();
    expect(result.current.isComparePickMode).toBe(false);
  });

  it("enters pick mode when a version is chosen as the base", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));

    expect(result.current.compareBaseId).toBe("entry-1");
    expect(result.current.isComparePickMode).toBe(true);
  });

  it("does not move the canvas selection while picking a target", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));
    const selectionBefore = result.current.selectedId;

    act(() => result.current.handleCompareClick(versionEntries[0]));
    setPreviewMock.mockClear();
    act(() => result.current.handleSelectEntry("entry-2"));

    expect(result.current.selectedId).toBe(selectionBefore);
    expect(result.current.compareTargetId).toBe("entry-2");
    expect(setPreviewMock).not.toHaveBeenCalled();
  });

  it("treats the current-draft row as the draft comparison target", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));
    act(() => result.current.handleSelectEntry(CURRENT_DRAFT_ID));

    expect(result.current.compareTargetId).toBe("draft");
  });

  it("ignores a click on the base row itself", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));
    act(() => result.current.handleSelectEntry("entry-1"));

    expect(result.current.compareTargetId).toBeNull();
    expect(result.current.isComparePickMode).toBe(true);
  });

  it("clears both sides when the comparison is cancelled", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));
    act(() => result.current.handleSelectEntry("entry-2"));
    act(() => result.current.handleCancelCompare());

    expect(result.current.compareBaseId).toBeNull();
    expect(result.current.compareTargetId).toBeNull();
  });

  it("swaps the two versions round", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));
    act(() => result.current.handleSelectEntry("entry-2"));
    act(() => result.current.handleSwapCompare());

    expect(result.current.compareBaseId).toBe("entry-2");
    expect(result.current.compareTargetId).toBe("entry-1");
  });

  it("leaves a draft comparison alone when swapping, since the draft has no version id", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));
    act(() => result.current.handleSelectEntry(CURRENT_DRAFT_ID));
    act(() => result.current.handleSwapCompare());

    expect(result.current.compareBaseId).toBe("entry-1");
    expect(result.current.compareTargetId).toBe("draft");
  });

  it("resumes driving the canvas selection once compare mode is left", () => {
    const { result } = renderHook(() => useFlowVersionSidebar("flow-1"));

    act(() => result.current.handleCompareClick(versionEntries[0]));
    act(() => result.current.handleCancelCompare());
    act(() => result.current.handleSelectEntry("entry-2"));

    expect(result.current.selectedId).toBe("entry-2");
  });
});
