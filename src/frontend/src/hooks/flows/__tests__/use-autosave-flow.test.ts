import { act, renderHook, waitFor } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FlowType } from "@/types/flow";
import { useDebounce } from "../../use-debounce";
import useAutoSaveFlow from "../use-autosave-flow";
import useSaveFlow from "../use-save-flow";

const mockUsePermissions = jest.fn();
const mockSetErrorData = jest.fn();

const makeMockFlow = (): FlowType =>
  ({
    id: "flow-1",
    name: "Test Flow",
  }) as FlowType;

// Mock dependencies
jest.mock("../use-save-flow");
jest.mock("../../use-debounce");
jest.mock("@/stores/flowsManagerStore");
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: mockSetErrorData }),
}));
jest.mock("@/stores/typesStore", () => ({
  useTypesStore: { getState: jest.fn(() => ({ templates: { Agent: {} } })) },
}));
jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: {
    getState: jest.fn(() => ({
      blockedComponentTypes: new Set(["ChatOutput"]),
    })),
  },
}));
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: jest.fn(() => ({ componentsToUpdate: [] })) },
}));
jest.mock("@/contexts/permissionsContext", () => ({
  usePermissions: () => mockUsePermissions(),
}));

describe("useAutoSaveFlow", () => {
  const mockSaveFlow = jest.fn();
  const mockDebouncedFn = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockSaveFlow.mockReset();
    mockDebouncedFn.mockReset();

    // Each test sets its own component state; without this the blocked-node
    // cases would leak into the ones after them.
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [],
    });
    (useTypesStore.getState as jest.Mock).mockReturnValue({
      templates: { Agent: {} },
    });
    (useUtilityStore.getState as jest.Mock).mockReturnValue({
      blockedComponentTypes: new Set(["ChatOutput"]),
    });
    (useSaveFlow as jest.Mock).mockReturnValue(mockSaveFlow);
    (useDebounce as jest.Mock).mockImplementation((fn) => {
      mockDebouncedFn.mockImplementation(fn);
      return mockDebouncedFn;
    });
    mockUsePermissions.mockReturnValue({
      can: jest.fn(() => true),
      isLoading: false,
    });
  });

  it("should return a debounced autosave function", () => {
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    const { result } = renderHook(() => useAutoSaveFlow());

    expect(useDebounce).toHaveBeenCalled();
    expect(typeof result.current).toBe("function");
  });

  it("should call saveFlow when autoSaving is enabled", async () => {
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    const autoSaveFlow = result.current;

    const mockFlow = makeMockFlow();
    await autoSaveFlow(mockFlow);

    expect(mockSaveFlow).toHaveBeenCalledWith(mockFlow);
  });

  it("keeps the flush barrier pending until direct and permission-delayed saves settle in order", async () => {
    let isLoading = false;
    const can = jest.fn(() => true);
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );
    mockUsePermissions.mockImplementation(() => ({ can, isLoading }));

    const events: string[] = [];
    let resolveFirst = () => {};
    let resolveSecond = () => {};
    mockSaveFlow.mockImplementation((flow: FlowType) => {
      events.push(`start:${flow.name}`);
      return new Promise<void>((resolve) => {
        const settle = () => {
          events.push(`settle:${flow.name}`);
          resolve();
        };
        if (flow.name === "First") {
          resolveFirst = settle;
        } else {
          resolveSecond = settle;
        }
      });
    });
    const { result, rerender } = renderHook(() => useAutoSaveFlow());
    const firstFlow = { ...makeMockFlow(), name: "First" };
    const secondFlow = { ...makeMockFlow(), name: "Second" };

    result.current(firstFlow);
    await waitFor(() => expect(mockSaveFlow).toHaveBeenCalledTimes(1));

    isLoading = true;
    rerender();
    result.current(secondFlow);
    expect(mockSaveFlow).toHaveBeenCalledTimes(1);

    isLoading = false;
    rerender();

    let flushSettled = false;
    const flushBarrier = result.current.flush().then(() => {
      flushSettled = true;
    });

    await Promise.resolve();
    expect(flushSettled).toBe(false);
    expect(mockSaveFlow).toHaveBeenCalledTimes(1);

    act(() => resolveFirst());
    await waitFor(() => expect(mockSaveFlow).toHaveBeenCalledTimes(2));
    expect(flushSettled).toBe(false);

    act(() => resolveSecond());
    await flushBarrier;

    expect(flushSettled).toBe(true);
    expect(events).toEqual([
      "start:First",
      "settle:First",
      "start:Second",
      "settle:Second",
    ]);
  });

  it("should not call saveFlow when autoSaving is disabled", () => {
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: false,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    const autoSaveFlow = result.current;

    const mockFlow = makeMockFlow();
    autoSaveFlow(mockFlow);

    expect(mockSaveFlow).not.toHaveBeenCalled();
  });

  it("reports the paused save once rather than on every attempt", async () => {
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [
        {
          id: "node-1",
          type: "ChatOutput",
          display_name: "Chat Output",
          blocked: true,
        },
      ],
    });
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    await result.current(makeMockFlow());
    await result.current(makeMockFlow());
    await result.current(makeMockFlow());

    // The user needs to know saving stopped, not to be told repeatedly.
    expect(mockSetErrorData).toHaveBeenCalledTimes(1);
    expect(mockSetErrorData.mock.calls[0][0].list[0]).toContain("Chat Output");
  });

  it("should call saveFlow without arguments when no flow is provided", async () => {
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    const autoSaveFlow = result.current;

    await autoSaveFlow();

    expect(mockSaveFlow).toHaveBeenCalledWith(undefined);
  });

  it("should use the correct autoSavingInterval for debounce", () => {
    const customInterval = 5000;

    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: customInterval,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    renderHook(() => useAutoSaveFlow());

    expect(useDebounce).toHaveBeenCalledWith(
      expect.any(Function),
      customInterval,
    );
  });

  it("should create new debounced function when interval changes", () => {
    const { rerender } = renderHook(() => useAutoSaveFlow());

    const firstCallArgs = (useDebounce as jest.Mock).mock.calls[0];

    // Simulate interval change
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 10000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    rerender();

    const secondCallArgs = (useDebounce as jest.Mock).mock.calls[1];

    // The interval should be different
    expect(firstCallArgs[1]).not.toBe(secondCallArgs[1]);
  });

  it("should handle toggling autoSaving on and off", async () => {
    let autoSaving = true;

    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );

    const { result, rerender } = renderHook(() => useAutoSaveFlow());
    const mockFlow = makeMockFlow();

    // AutoSaving enabled
    await result.current(mockFlow);
    expect(mockSaveFlow).toHaveBeenCalledWith(mockFlow);

    mockSaveFlow.mockClear();

    // Disable autoSaving
    autoSaving = false;
    rerender();

    result.current(mockFlow);
    expect(mockSaveFlow).not.toHaveBeenCalled();
  });

  it("should not call saveFlow while permissions are loading", () => {
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );
    mockUsePermissions.mockReturnValue({
      can: jest.fn(() => true),
      isLoading: true,
    });

    const { result } = renderHook(() => useAutoSaveFlow());
    result.current(makeMockFlow());

    expect(mockSaveFlow).not.toHaveBeenCalled();
  });

  it("should flush a pending autosave after permissions finish loading", async () => {
    let isLoading = true;
    const can = jest.fn(() => true);
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );
    mockUsePermissions.mockImplementation(() => ({
      can,
      isLoading,
    }));

    const { result, rerender } = renderHook(() => useAutoSaveFlow());
    const mockFlow = makeMockFlow();
    result.current(mockFlow);
    expect(mockSaveFlow).not.toHaveBeenCalled();

    isLoading = false;
    rerender();

    expect(can).toHaveBeenCalledWith("flow-1", "write");
    await waitFor(() => expect(mockSaveFlow).toHaveBeenCalledWith(mockFlow));
  });

  it("should not call saveFlow when write permission is denied", () => {
    const can = jest.fn(() => false);
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => {
        const state = {
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        };
        return selector(state);
      },
    );
    mockUsePermissions.mockReturnValue({
      can,
      isLoading: false,
    });

    const { result } = renderHook(() => useAutoSaveFlow());
    result.current(makeMockFlow());

    expect(can).toHaveBeenCalledWith("flow-1", "write");
    expect(mockSaveFlow).not.toHaveBeenCalled();
  });

  it("does not autosave a flow holding a component the server will reject", async () => {
    // A missing template cannot be persisted, so retrying the save only
    // produces failed requests before the user has touched anything.
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [
        { id: "node-1", type: "ChatOutput", blocked: true, outdated: false },
      ],
    });
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    // Awaiting matters: the save is enqueued on a promise chain, so a
    // synchronous assertion would pass whether or not the guard is present.
    await result.current(makeMockFlow());

    expect(mockSaveFlow).not.toHaveBeenCalled();
  });

  it("still autosaves once no component is blocked", async () => {
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [{ id: "node-1", blocked: false, outdated: true }],
    });
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    await result.current(makeMockFlow());

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
  });

  it("keeps saving a component the policy does not name", async () => {
    // LE-2226: a policy blocking some *other* component — or only a starter
    // template — must not stop persisting this flow. A missing template is
    // equally an uninstalled bundle, an imported flow, or the user's own
    // component, all of which the server accepts.
    (useUtilityStore.getState as jest.Mock).mockReturnValue({
      blockedComponentTypes: new Set(["SomeOtherComponent"]),
    });
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [
        {
          id: "node-1",
          type: "MyUninstalledBundleComponent",
          display_name: "Bundle Component",
          blocked: true,
        },
      ],
    });
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    await result.current(makeMockFlow());

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("keeps saving when no catalog policy is in force", async () => {
    // Without a policy the server accepts the write, so a missing template is
    // not a reason to stop persisting.
    (useUtilityStore.getState as jest.Mock).mockReturnValue({
      blockedComponentTypes: new Set<string>(),
    });
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [
        { id: "node-1", display_name: "Chat Output", blocked: true },
      ],
    });
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );

    const { result } = renderHook(() => useAutoSaveFlow());
    await result.current(makeMockFlow());

    expect(mockSaveFlow).toHaveBeenCalledTimes(1);
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("holds the paused edit so it lands once the block clears", async () => {
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [
        {
          id: "node-1",
          type: "ChatOutput",
          display_name: "Chat Output",
          blocked: true,
        },
      ],
    });
    let isLoading = false;
    mockUsePermissions.mockReturnValue({ can: jest.fn(() => true), isLoading });
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({
          autoSaving: true,
          autoSavingInterval: 3000,
          currentFlowId: "flow-1",
        }),
    );

    const { result, rerender } = renderHook(() => useAutoSaveFlow());
    await result.current(makeMockFlow());
    expect(mockSaveFlow).not.toHaveBeenCalled();

    // Removing the component unblocks the flow; the held edit should persist.
    (useFlowStore.getState as jest.Mock).mockReturnValue({
      componentsToUpdate: [],
    });
    isLoading = true;
    rerender();
    isLoading = false;
    mockUsePermissions.mockReturnValue({ can: jest.fn(() => true), isLoading });
    rerender();

    await waitFor(() => expect(mockSaveFlow).toHaveBeenCalledTimes(1));
  });
});
