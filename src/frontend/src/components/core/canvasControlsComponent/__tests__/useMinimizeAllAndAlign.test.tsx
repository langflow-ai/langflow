import { act, renderHook, waitFor } from "@testing-library/react";
import useMinimizeAllAndAlign, {
  MINIMIZED_NODE_HEIGHT,
  MINIMIZED_NODE_WIDTH,
} from "../hooks/use-minimize-all-and-align";

const mockUpdateNodeInternals = jest.fn();
const mockFitView = jest.fn();
jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => mockUpdateNodeInternals,
  useReactFlow: () => ({ fitView: mockFitView }),
}));

const mockTakeSnapshot = jest.fn();
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ takeSnapshot: mockTakeSnapshot }),
}));

let mockNodes: any[] = [];
const mockSetNodes = jest.fn();
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({ nodes: mockNodes, edges: [], setNodes: mockSetNodes }),
}));

const mockGetLayoutedNodes = jest.fn();
jest.mock("@/utils/layoutUtils", () => ({
  getLayoutedNodes: (...args: any[]) => mockGetLayoutedNodes(...args),
}));

const genericNode = (id: string, showNode?: boolean) => ({
  id,
  type: "genericNode",
  position: { x: 0, y: 0 },
  data: { id, showNode },
});

const noteNode = (id: string) => ({
  id,
  type: "noteNode",
  position: { x: 0, y: 0 },
  data: { id },
});

describe("useMinimizeAllAndAlign (LE-1810 T9)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetLayoutedNodes.mockImplementation(async (nodes) => nodes);
  });

  it("reports allMinimized=false when any generic node is expanded", () => {
    mockNodes = [genericNode("a", false), genericNode("b", true)];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    expect(result.current.allMinimized).toBe(false);
    expect(result.current.hasGenericNodes).toBe(true);
  });

  it("reports allMinimized=true when every generic node is collapsed", () => {
    mockNodes = [genericNode("a", false), genericNode("b", false), noteNode("n")];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    expect(result.current.allMinimized).toBe(true);
  });

  it("minimizes every generic node, aligns with collapsed dimensions and fits the view", async () => {
    mockNodes = [genericNode("a", true), genericNode("b"), noteNode("n")];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    await act(async () => {
      result.current.toggleMinimizeAllAndAlign();
    });

    expect(mockTakeSnapshot).toHaveBeenCalled();
    await waitFor(() => expect(mockGetLayoutedNodes).toHaveBeenCalled());

    const [collapsedNodes, , sizeOverride] =
      mockGetLayoutedNodes.mock.calls[0];
    const generics = collapsedNodes.filter(
      (node: any) => node.type === "genericNode",
    );
    expect(generics.every((node: any) => node.data.showNode === false)).toBe(
      true,
    );
    const note = collapsedNodes.find((node: any) => node.type === "noteNode");
    expect(note.data.showNode).toBeUndefined();
    expect(sizeOverride).toEqual({
      width: MINIMIZED_NODE_WIDTH,
      height: MINIMIZED_NODE_HEIGHT,
    });

    await waitFor(() => expect(mockSetNodes).toHaveBeenCalled());
    expect(mockUpdateNodeInternals).toHaveBeenCalledWith(["a", "b"]);
  });

  it("expands every generic node without re-layouting when all are minimized", async () => {
    mockNodes = [genericNode("a", false), genericNode("b", false)];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    await act(async () => {
      result.current.toggleMinimizeAllAndAlign();
    });

    expect(mockTakeSnapshot).toHaveBeenCalled();
    expect(mockGetLayoutedNodes).not.toHaveBeenCalled();
    expect(mockSetNodes).toHaveBeenCalledWith(expect.any(Function));

    const updater = mockSetNodes.mock.calls[0][0];
    const expanded = updater(mockNodes);
    expect(
      expanded
        .filter((node: any) => node.type === "genericNode")
        .every((node: any) => node.data.showNode === true),
    ).toBe(true);
    expect(mockUpdateNodeInternals).toHaveBeenCalledWith(["a", "b"]);
  });
});
