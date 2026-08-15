import { act, renderHook } from "@testing-library/react";
import useAutoArrange from "../hooks/use-auto-arrange";

const mockTakeSnapshot = jest.fn();
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({ takeSnapshot: mockTakeSnapshot }),
  },
}));

type MockNode = { id: string; position: { x: number; y: number } };
type MockEdge = { id: string; source: string; target: string };

let mockNodes: MockNode[] = [];
let mockEdges: MockEdge[] = [];
let mockCurrentFlow: { id: string } | undefined = { id: "flow-1" };
const mockSetNodes = jest.fn();

// Keep the selector/getState logic inside the factory — jest.mock hoists
// above the module's other top-level declarations.
jest.mock("@/stores/flowStore", () => {
  const getFlowState = () => ({
    nodes: mockNodes,
    edges: mockEdges,
    setNodes: mockSetNodes,
    currentFlow: mockCurrentFlow,
  });
  const useFlowStoreMock = (selector: (state: unknown) => unknown) =>
    selector(getFlowState());
  useFlowStoreMock.getState = getFlowState;
  return { __esModule: true, default: useFlowStoreMock };
});

const mockGetLayoutedNodes = jest.fn();
jest.mock("@/utils/layoutUtils", () => ({
  getLayoutedNodes: (...args: unknown[]) => mockGetLayoutedNodes(...args),
}));

const node = (id: string, x = 0, y = 0) => ({ id, position: { x, y } });

describe("useAutoArrange", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [];
    mockEdges = [];
    mockCurrentFlow = { id: "flow-1" };
  });

  it("reports canArrange=false with fewer than two nodes", () => {
    mockNodes = [node("a")];
    const { result } = renderHook(() => useAutoArrange());

    expect(result.current.canArrange).toBe(false);
  });

  it("reports canArrange=true with two or more nodes", () => {
    mockNodes = [node("a"), node("b")];
    const { result } = renderHook(() => useAutoArrange());

    expect(result.current.canArrange).toBe(true);
  });

  it("does nothing when there aren't enough nodes to arrange", async () => {
    mockNodes = [node("a")];
    const { result } = renderHook(() => useAutoArrange());

    await act(async () => {
      await result.current.handleAutoArrange();
    });

    expect(mockGetLayoutedNodes).not.toHaveBeenCalled();
    expect(mockTakeSnapshot).not.toHaveBeenCalled();
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it("takes a snapshot and applies the layouted positions", async () => {
    mockNodes = [node("a", 0, 0), node("b", 0, 0)];
    mockEdges = [{ id: "e1", source: "a", target: "b" }];
    const layouted = [node("a", 10, 20), node("b", 30, 40)];
    mockGetLayoutedNodes.mockResolvedValue(layouted);

    const { result } = renderHook(() => useAutoArrange());

    await act(async () => {
      await result.current.handleAutoArrange();
    });

    expect(mockGetLayoutedNodes).toHaveBeenCalledWith(mockNodes, mockEdges);
    expect(mockTakeSnapshot).toHaveBeenCalled();
    expect(mockSetNodes).toHaveBeenCalledWith([
      node("a", 10, 20),
      node("b", 30, 40),
    ]);
    expect(result.current.isArranging).toBe(false);
  });

  it("preserves a node added while layout was still computing, instead of reverting it", async () => {
    mockNodes = [node("a", 0, 0), node("b", 0, 0)];
    mockEdges = [];
    const layouted = [node("a", 10, 20), node("b", 30, 40)];

    // Simulate a node being added to the store WHILE getLayoutedNodes is
    // still awaiting — the merge must preserve it, not revert to the
    // pre-await snapshot.
    mockGetLayoutedNodes.mockImplementation(async () => {
      mockNodes = [...mockNodes, node("c", 99, 99)];
      return layouted;
    });

    const { result } = renderHook(() => useAutoArrange());

    await act(async () => {
      await result.current.handleAutoArrange();
    });

    const [applied] = mockSetNodes.mock.calls[0];
    expect(applied).toEqual([
      node("a", 10, 20),
      node("b", 30, 40),
      node("c", 99, 99),
    ]);
  });

  it("does not apply nodes and resets isArranging when layout fails", async () => {
    mockNodes = [node("a"), node("b")];
    mockGetLayoutedNodes.mockRejectedValue(new Error("layout failed"));
    const consoleErrorSpy = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const { result } = renderHook(() => useAutoArrange());

    await act(async () => {
      await result.current.handleAutoArrange();
    });

    expect(mockSetNodes).not.toHaveBeenCalled();
    expect(result.current.isArranging).toBe(false);
    consoleErrorSpy.mockRestore();
  });

  it("discards the layout if the active flow changed while it was computing", async () => {
    mockNodes = [node("a", 0, 0), node("b", 0, 0)];
    const layouted = [node("a", 10, 20), node("b", 30, 40)];

    // Simulate switching to a different flow (no unmount) WHILE
    // getLayoutedNodes is still awaiting — e.g. a flow switcher that reuses
    // the same CanvasControls instance.
    mockGetLayoutedNodes.mockImplementation(async () => {
      mockCurrentFlow = { id: "flow-2" };
      return layouted;
    });

    const { result } = renderHook(() => useAutoArrange());

    await act(async () => {
      await result.current.handleAutoArrange();
    });

    expect(mockTakeSnapshot).not.toHaveBeenCalled();
    expect(mockSetNodes).not.toHaveBeenCalled();
  });

  it("does not touch the store if the hook unmounted before layout resolved", async () => {
    mockNodes = [node("a"), node("b")];
    let resolveLayout: (value: MockNode[]) => void;
    mockGetLayoutedNodes.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveLayout = resolve;
        }),
    );

    const { result, unmount } = renderHook(() => useAutoArrange());

    let pending: Promise<void>;
    act(() => {
      pending = result.current.handleAutoArrange();
    });

    unmount();
    await act(async () => {
      resolveLayout!([node("a", 1, 1), node("b", 2, 2)]);
      await pending;
    });

    expect(mockTakeSnapshot).not.toHaveBeenCalled();
    expect(mockSetNodes).not.toHaveBeenCalled();
  });
});
