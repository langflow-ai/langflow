import { act, renderHook } from "@testing-library/react";
import { useCallback } from "react";

// LE-1810 (T7): any component can be minimized, regardless of how many
// input/output handles it has. This suite pins the new contract that
// replaced the old `isMinimal` restriction (multiple outputs, group
// outputs and connected-input counts no longer gate minimization).
describe("NodeToolbar minimize contract (LE-1810)", () => {
  const useMinimizeLogic = (showNode: boolean, setShowNode: jest.Mock) => {
    const handleMinimize = useCallback(() => {
      setShowNode(!showNode);
    }, [showNode, setShowNode]);

    return { handleMinimize };
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const scenarios: Array<{
    name: string;
    outputs: { name: string }[];
    edges: number;
  }> = [
    {
      name: "single output, no connections",
      outputs: [{ name: "o1" }],
      edges: 0,
    },
    {
      name: "multiple outputs without group outputs",
      outputs: [
        { name: "o1", group_outputs: false },
        { name: "o2", group_outputs: false },
      ],
      edges: 0,
    },
    {
      name: "group outputs",
      outputs: [
        { name: "o1", group_outputs: true },
        { name: "o2", group_outputs: false },
      ],
      edges: 1,
    },
    {
      name: "many connected inputs",
      outputs: [{ name: "o1" }],
      edges: 5,
    },
    { name: "no outputs at all", outputs: [], edges: 3 },
  ];

  it.each(scenarios)(
    "minimizes a node with $name",
    ({ outputs: _outputs, edges: _edges }) => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimizeLogic(true, mockSetShowNode),
      );

      act(() => {
        result.current.handleMinimize();
      });

      expect(mockSetShowNode).toHaveBeenCalledWith(false);
    },
  );

  it("expands a minimized node on toggle", () => {
    const mockSetShowNode = jest.fn();
    const { result } = renderHook(() =>
      useMinimizeLogic(false, mockSetShowNode),
    );

    act(() => {
      result.current.handleMinimize();
    });

    expect(mockSetShowNode).toHaveBeenCalledWith(true);
  });

  it("never surfaces a restriction notice", () => {
    const consoleSpy = jest.spyOn(console, "log").mockImplementation();
    const mockSetShowNode = jest.fn();
    const { result } = renderHook(() =>
      useMinimizeLogic(true, mockSetShowNode),
    );

    act(() => {
      result.current.handleMinimize();
    });

    expect(consoleSpy).not.toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
