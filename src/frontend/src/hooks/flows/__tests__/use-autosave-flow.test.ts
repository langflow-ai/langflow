import { renderHook } from "@testing-library/react";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { useDebounce } from "../../use-debounce";
import useAutoSaveFlow from "../use-autosave-flow";
import useSaveFlow from "../use-save-flow";

const mockUsePermissions = jest.fn();

const makeMockFlow = (): FlowType =>
  ({
    id: "flow-1",
    name: "Test Flow",
  }) as FlowType;

// Mock dependencies
jest.mock("../use-save-flow");
jest.mock("../../use-debounce");
jest.mock("@/stores/flowsManagerStore");
jest.mock("@/contexts/permissionsContext", () => ({
  usePermissions: () => mockUsePermissions(),
}));

describe("useAutoSaveFlow", () => {
  const mockSaveFlow = jest.fn();
  const mockDebouncedFn = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();

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

  it("should call saveFlow when autoSaving is enabled", () => {
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
    autoSaveFlow(mockFlow);

    expect(mockSaveFlow).toHaveBeenCalledWith(mockFlow);
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

  it("should call saveFlow without arguments when no flow is provided", () => {
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

    autoSaveFlow();

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

  it("should handle toggling autoSaving on and off", () => {
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
    result.current(mockFlow);
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
});
