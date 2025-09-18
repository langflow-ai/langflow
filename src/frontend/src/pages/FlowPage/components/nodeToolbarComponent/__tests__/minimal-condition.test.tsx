import { act, renderHook } from "@testing-library/react";
import { useCallback, useEffect } from "react";

// Test the minimal condition logic in isolation
describe("NodeToolbar Minimal Condition Logic", () => {
  // Simulate the exact logic from the component
  const useMinimalLogic = (
    nodeOutputs: any[] | null | undefined,
    showNode: boolean,
    setShowNode: jest.Mock,
  ) => {
    const hasGroupOutputs = !!nodeOutputs?.some?.(
      (output) => output?.group_outputs,
    );
    const hasOutputs = !!(nodeOutputs?.length && nodeOutputs.length > 1);
    const isMinimal = !!(hasOutputs && !hasGroupOutputs);

    const handleMinimize = useCallback(() => {
      if (isMinimal || !showNode) {
        setShowNode(!showNode);
        return;
      }
      // Would show notice in real component
      console.log(
        "Minimization only available for components with one handle or fewer.",
      );
    }, [isMinimal, showNode, setShowNode]);

    useEffect(() => {
      if (!isMinimal && !showNode) {
        setShowNode(true);
        return;
      }
    }, [isMinimal, showNode, setShowNode]);

    return {
      hasGroupOutputs,
      hasOutputs,
      isMinimal,
      handleMinimize,
    };
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("isMinimal calculation", () => {
    it("should be true when node has multiple outputs without group outputs", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [
            { name: "output1", group_outputs: false },
            { name: "output2", group_outputs: false },
          ],
          true,
          mockSetShowNode,
        ),
      );

      expect(result.current.isMinimal).toBe(true);
      expect(result.current.hasOutputs).toBe(true);
      expect(result.current.hasGroupOutputs).toBe(false);
    });

    it("should be false when node has group outputs", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [
            { name: "output1", group_outputs: true },
            { name: "output2", group_outputs: false },
          ],
          true,
          mockSetShowNode,
        ),
      );

      expect(result.current.isMinimal).toBe(false);
      expect(result.current.hasOutputs).toBe(true);
      expect(result.current.hasGroupOutputs).toBe(true);
    });

    it("should be false when node has single output", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [{ name: "output1", group_outputs: false }],
          true,
          mockSetShowNode,
        ),
      );

      expect(result.current.isMinimal).toBe(false);
      expect(result.current.hasOutputs).toBe(false); // length <= 1
      expect(result.current.hasGroupOutputs).toBe(false);
    });

    it("should be false when node has no outputs", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic([], true, mockSetShowNode),
      );

      expect(result.current.isMinimal).toBe(false);
      expect(result.current.hasOutputs).toBe(false);
      expect(result.current.hasGroupOutputs).toBe(false);
    });

    it("should be false when outputs is undefined", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(undefined, true, mockSetShowNode),
      );

      expect(result.current.isMinimal).toBe(false);
      expect(result.current.hasOutputs).toBe(false);
      expect(result.current.hasGroupOutputs).toBe(false);
    });

    it("should be false when outputs is null", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(null, true, mockSetShowNode),
      );

      expect(result.current.isMinimal).toBe(false);
      expect(result.current.hasOutputs).toBe(false);
      expect(result.current.hasGroupOutputs).toBe(false);
    });
  });

  describe("handleMinimize behavior", () => {
    it("should toggle showNode when isMinimal is true", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [
            { name: "output1", group_outputs: false },
            { name: "output2", group_outputs: false },
          ],
          true,
          mockSetShowNode,
        ),
      );

      act(() => {
        result.current.handleMinimize();
      });

      expect(mockSetShowNode).toHaveBeenCalledWith(false);
    });

    it("should toggle showNode when showNode is false (expand)", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [{ name: "output1", group_outputs: true }], // Not minimal
          false, // But showNode is false, so should allow toggle
          mockSetShowNode,
        ),
      );

      act(() => {
        result.current.handleMinimize();
      });

      expect(mockSetShowNode).toHaveBeenCalledWith(true);
    });

    it("should not toggle when not minimal and showNode is true", () => {
      const consoleSpy = jest.spyOn(console, "log").mockImplementation();
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [{ name: "output1", group_outputs: true }], // Not minimal
          true, // showNode is true
          mockSetShowNode,
        ),
      );

      act(() => {
        result.current.handleMinimize();
      });

      expect(mockSetShowNode).not.toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalledWith(
        "Minimization only available for components with one handle or fewer.",
      );

      consoleSpy.mockRestore();
    });
  });

  describe("auto-expand effect", () => {
    it("should auto-expand non-minimal hidden nodes", () => {
      const mockSetShowNode = jest.fn();

      renderHook(() =>
        useMinimalLogic(
          [{ name: "output1", group_outputs: true }], // Not minimal
          false, // Hidden
          mockSetShowNode,
        ),
      );

      expect(mockSetShowNode).toHaveBeenCalledWith(true);
    });

    it("should not auto-expand minimal hidden nodes", () => {
      const mockSetShowNode = jest.fn();

      renderHook(() =>
        useMinimalLogic(
          [
            { name: "output1", group_outputs: false },
            { name: "output2", group_outputs: false },
          ], // Is minimal
          false, // Hidden
          mockSetShowNode,
        ),
      );

      expect(mockSetShowNode).not.toHaveBeenCalled();
    });

    it("should not auto-expand when node is already visible", () => {
      const mockSetShowNode = jest.fn();

      renderHook(() =>
        useMinimalLogic(
          [{ name: "output1", group_outputs: true }], // Not minimal
          true, // Already visible
          mockSetShowNode,
        ),
      );

      expect(mockSetShowNode).not.toHaveBeenCalled();
    });

    it("should update when isMinimal changes", () => {
      const mockSetShowNode = jest.fn();
      const { rerender } = renderHook(
        ({ outputs }) => useMinimalLogic(outputs, false, mockSetShowNode),
        {
          initialProps: {
            outputs: [{ name: "output1", group_outputs: true }], // Not minimal
          },
        },
      );

      expect(mockSetShowNode).toHaveBeenCalledWith(true);
      mockSetShowNode.mockClear();

      // Change to minimal outputs
      rerender({
        outputs: [
          { name: "output1", group_outputs: false },
          { name: "output2", group_outputs: false },
        ], // Is minimal
      });

      expect(mockSetShowNode).not.toHaveBeenCalled();
    });
  });

  describe("complex output combinations", () => {
    const testCases = [
      {
        description: "multiple outputs, all with group_outputs: false",
        outputs: [
          { name: "out1", group_outputs: false },
          { name: "out2", group_outputs: false },
          { name: "out3", group_outputs: false },
        ],
        expectedMinimal: true,
      },
      {
        description: "multiple outputs, mixed group_outputs",
        outputs: [
          { name: "out1", group_outputs: false },
          { name: "out2", group_outputs: true },
          { name: "out3", group_outputs: false },
        ],
        expectedMinimal: false,
      },
      {
        description: "multiple outputs, all with group_outputs: true",
        outputs: [
          { name: "out1", group_outputs: true },
          { name: "out2", group_outputs: true },
        ],
        expectedMinimal: false,
      },
      {
        description: "exactly two outputs, no group outputs",
        outputs: [
          { name: "out1", group_outputs: false },
          { name: "out2", group_outputs: false },
        ],
        expectedMinimal: true,
      },
      {
        description: "outputs with missing group_outputs property",
        outputs: [{ name: "out1" }, { name: "out2", group_outputs: false }],
        expectedMinimal: true, // Undefined is falsy
      },
    ];

    testCases.forEach(({ description, outputs, expectedMinimal }) => {
      it(`should handle ${description}`, () => {
        const mockSetShowNode = jest.fn();
        const { result } = renderHook(() =>
          useMinimalLogic(outputs, true, mockSetShowNode),
        );

        expect(result.current.isMinimal).toBe(expectedMinimal);
      });
    });
  });

  describe("edge cases", () => {
    it("should handle empty outputs array", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic([], true, mockSetShowNode),
      );

      expect(result.current.isMinimal).toBe(false);
      expect(result.current.hasOutputs).toBe(false);
      expect(result.current.hasGroupOutputs).toBe(false);
    });

    it("should handle outputs with null/undefined values", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [null, { name: "out1", group_outputs: false }, undefined],
          true,
          mockSetShowNode,
        ),
      );

      // Should still calculate correctly despite null/undefined entries
      expect(result.current.hasOutputs).toBe(true); // Length > 1
      expect(result.current.hasGroupOutputs).toBe(false);
      expect(result.current.isMinimal).toBe(true);
    });

    it("should handle outputs without name property", () => {
      const mockSetShowNode = jest.fn();
      const { result } = renderHook(() =>
        useMinimalLogic(
          [{ group_outputs: false }, { group_outputs: false }],
          true,
          mockSetShowNode,
        ),
      );

      expect(result.current.isMinimal).toBe(true);
    });
  });
});
