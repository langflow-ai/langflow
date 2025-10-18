import { renderHook } from "@testing-library/react";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { customStringify } from "@/utils/reactflowUtils";
import { useUnsavedChanges } from "../use-unsaved-changes";

// Mock the stores
jest.mock("@/stores/flowStore");
jest.mock("@/stores/flowsManagerStore");
jest.mock("@/utils/reactflowUtils");

describe("useUnsavedChanges", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should return false when currentFlow is null", () => {
    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow: null }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) =>
        selector({ currentFlow: { id: "flow-1", name: "Test Flow" } }),
    );

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(false);
  });

  it("should return false when savedFlow is null", () => {
    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow: { id: "flow-1", name: "Test Flow" } }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: null }),
    );

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(false);
  });

  it("should return false when both flows are null", () => {
    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow: null }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: null }),
    );

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(false);
  });

  it("should return false when flows are identical", () => {
    const mockFlow = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [], edges: [] },
    };

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow: mockFlow }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: mockFlow }),
    );
    (customStringify as jest.Mock).mockReturnValue(JSON.stringify(mockFlow));

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(false);
  });

  it("should return true when flows are different", () => {
    const currentFlow = {
      id: "flow-1",
      name: "Modified Flow",
      data: { nodes: [], edges: [] },
    };
    const savedFlow = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [], edges: [] },
    };

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: savedFlow }),
    );
    (customStringify as jest.Mock)
      .mockReturnValueOnce(JSON.stringify(currentFlow))
      .mockReturnValueOnce(JSON.stringify(savedFlow));

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(true);
  });

  it("should use customStringify to compare flows", () => {
    const currentFlow = { id: "flow-1", name: "Test Flow" };
    const savedFlow = { id: "flow-1", name: "Test Flow" };

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: savedFlow }),
    );
    (customStringify as jest.Mock)
      .mockReturnValueOnce("stringified-current")
      .mockReturnValueOnce("stringified-saved");

    renderHook(() => useUnsavedChanges());

    expect(customStringify).toHaveBeenCalledWith(currentFlow);
    expect(customStringify).toHaveBeenCalledWith(savedFlow);
  });

  it("should return true when nodes have changed", () => {
    const currentFlow = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [{ id: "node-1" }], edges: [] },
    };
    const savedFlow = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [], edges: [] },
    };

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: savedFlow }),
    );
    (customStringify as jest.Mock)
      .mockReturnValueOnce(JSON.stringify(currentFlow))
      .mockReturnValueOnce(JSON.stringify(savedFlow));

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(true);
  });

  it("should return true when edges have changed", () => {
    const currentFlow = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [], edges: [{ id: "edge-1" }] },
    };
    const savedFlow = {
      id: "flow-1",
      name: "Test Flow",
      data: { nodes: [], edges: [] },
    };

    (useFlowStore as unknown as jest.Mock).mockImplementation((selector) =>
      selector({ currentFlow }),
    );
    (useFlowsManagerStore as unknown as jest.Mock).mockImplementation(
      (selector) => selector({ currentFlow: savedFlow }),
    );
    (customStringify as jest.Mock)
      .mockReturnValueOnce(JSON.stringify(currentFlow))
      .mockReturnValueOnce(JSON.stringify(savedFlow));

    const { result } = renderHook(() => useUnsavedChanges());

    expect(result.current).toBe(true);
  });
});
