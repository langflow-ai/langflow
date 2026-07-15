import { act, renderHook } from "@testing-library/react";
import useMinimizeAllAndAlign from "../hooks/use-minimize-all-and-align";

const mockUpdateNodeInternals = jest.fn();
jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => mockUpdateNodeInternals,
}));

type MockNode = {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: { id: string; showNode?: boolean };
};

const mockTakeSnapshot = jest.fn();
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ takeSnapshot: mockTakeSnapshot }),
}));

let mockNodes: MockNode[] = [];
const mockSetNodes = jest.fn();
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ nodes: mockNodes, setNodes: mockSetNodes }),
}));

const mockGetLayoutedNodes = jest.fn();
jest.mock("@/utils/layoutUtils", () => ({
  getLayoutedNodes: (...args: unknown[]) => mockGetLayoutedNodes(...args),
}));

const genericNode = (
  id: string,
  showNode?: boolean,
  position = { x: 10, y: 20 },
) => ({
  id,
  type: "genericNode",
  position,
  data: { id, showNode },
});

const noteNode = (id: string) => ({
  id,
  type: "noteNode",
  position: { x: 0, y: 0 },
  data: { id },
});

describe("useMinimizeAllAndAlign (LE-1810 T9 — minimize only, no re-layout)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("reports allMinimized=false when any generic node is expanded", () => {
    mockNodes = [genericNode("a", false), genericNode("b", true)];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    expect(result.current.allMinimized).toBe(false);
    expect(result.current.hasGenericNodes).toBe(true);
  });

  it("reports allMinimized=true when every generic node is collapsed", () => {
    mockNodes = [
      genericNode("a", false),
      genericNode("b", false),
      noteNode("n"),
    ];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    expect(result.current.allMinimized).toBe(true);
  });

  it("minimizes every generic node keeping positions — no layout, no viewport change", () => {
    mockNodes = [
      genericNode("a", true, { x: 1, y: 2 }),
      genericNode("b", undefined, { x: 3, y: 4 }),
      noteNode("n"),
    ];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    act(() => {
      result.current.toggleMinimizeAllAndAlign();
    });

    expect(mockTakeSnapshot).toHaveBeenCalled();
    // Reporter call on LE-1810: minimize-all must ONLY minimize.
    expect(mockGetLayoutedNodes).not.toHaveBeenCalled();

    const [updated] = mockSetNodes.mock.calls[0];
    const generics = updated.filter(
      (node: MockNode) => node.type === "genericNode",
    );
    expect(
      generics.every((node: MockNode) => node.data.showNode === false),
    ).toBe(true);
    expect(generics.map((node: MockNode) => node.position)).toEqual([
      { x: 1, y: 2 },
      { x: 3, y: 4 },
    ]);
    const note = updated.find((node: MockNode) => node.type === "noteNode");
    expect(note.data.showNode).toBeUndefined();
    expect(mockUpdateNodeInternals).toHaveBeenCalledWith(["a", "b"]);
  });

  it("expands every generic node keeping positions", () => {
    mockNodes = [
      genericNode("a", false, { x: 5, y: 6 }),
      genericNode("b", false, { x: 7, y: 8 }),
    ];
    const { result } = renderHook(() => useMinimizeAllAndAlign());

    act(() => {
      result.current.toggleMinimizeAllAndAlign();
    });

    expect(mockTakeSnapshot).toHaveBeenCalled();
    expect(mockGetLayoutedNodes).not.toHaveBeenCalled();

    const [updated] = mockSetNodes.mock.calls[0];
    expect(
      updated.every((node: MockNode) => node.data.showNode === true),
    ).toBe(true);
    expect(updated.map((node: MockNode) => node.position)).toEqual([
      { x: 5, y: 6 },
      { x: 7, y: 8 },
    ]);
    expect(mockUpdateNodeInternals).toHaveBeenCalledWith(["a", "b"]);
  });
});
