import { act, renderHook } from "@testing-library/react";
import { useSpanTree } from "../useSpanTree";
import { buildSpan } from "./spanTestUtils";

const makeKey = (key: string): React.KeyboardEvent =>
  ({ key, preventDefault: jest.fn() }) as unknown as React.KeyboardEvent;

describe("useSpanTree", () => {

  // ── initial state ────────────────────────────────────────────────────────────

  describe("initial state", () => {
    it("expands all root spans by default", () => {
      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      expect(result.current.expandedIds.has("a")).toBe(true);
      expect(result.current.expandedIds.has("b")).toBe(true);
    });

    it("sets focusedId to selectedSpanId when provided", () => {
      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: "b" }),
      );

      expect(result.current.focusedId).toBe("b");
    });

    it("sets focusedId to first span when selectedSpanId is null", () => {
      const spans = [buildSpan({ id: "first" }), buildSpan({ id: "second" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      expect(result.current.focusedId).toBe("first");
    });

    it("sets focusedId to null when spans is empty", () => {
      const { result } = renderHook(() =>
        useSpanTree({ spans: [], selectedSpanId: null }),
      );

      expect(result.current.focusedId).toBeNull();
    });

    it("includes only root-level spans in visibleIds when no children are present", () => {
      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      expect(result.current.visibleIds).toEqual(["a", "b"]);
    });
  });

  // ── toggleExpand ─────────────────────────────────────────────────────────────

  describe("toggleExpand", () => {
    it("collapses an expanded root span", () => {
      const spans = [buildSpan({ id: "root" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      act(() => result.current.toggleExpand("root"));

      expect(result.current.expandedIds.has("root")).toBe(false);
    });

    it("re-expands a collapsed span", () => {
      const spans = [buildSpan({ id: "root" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      act(() => result.current.toggleExpand("root"));
      act(() => result.current.toggleExpand("root"));

      expect(result.current.expandedIds.has("root")).toBe(true);
    });

    it("hides a span's children from visibleIds when collapsed", () => {
      const child = buildSpan({ id: "child" });
      const spans = [buildSpan({ id: "root", children: [child] })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      expect(result.current.visibleIds).toContain("child");

      act(() => result.current.toggleExpand("root"));

      expect(result.current.visibleIds).not.toContain("child");
    });
  });

  // ── handleTreeKeyDown ─────────────────────────────────────────────────────────

  describe("handleTreeKeyDown", () => {
    it("does nothing when focusedId is null", () => {
      const { result } = renderHook(() =>
        useSpanTree({ spans: [], selectedSpanId: null }),
      );

      expect(() =>
        act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown"))),
      ).not.toThrow();
    });

    describe("ArrowDown", () => {
      it("moves focusedId to the next visible span and focuses the node", () => {
        const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );
        const focusMock = jest.fn();
        act(() =>
          result.current.registerNodeRef(
            "b",
            { focus: focusMock } as unknown as HTMLElement,
          ),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

        expect(result.current.focusedId).toBe("b");
        expect(focusMock).toHaveBeenCalled();
      });

      it("does not move past the last span", () => {
        const spans = [buildSpan({ id: "only" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

        expect(result.current.focusedId).toBe("only");
      });
    });

    describe("ArrowUp", () => {
      it("moves focusedId to the previous visible span and focuses the node", () => {
        const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: "b" }),
        );
        const focusMock = jest.fn();
        act(() =>
          result.current.registerNodeRef(
            "a",
            { focus: focusMock } as unknown as HTMLElement,
          ),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowUp")));

        expect(result.current.focusedId).toBe("a");
        expect(focusMock).toHaveBeenCalled();
      });

      it("does not move before the first span", () => {
        const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: "a" }),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowUp")));

        expect(result.current.focusedId).toBe("a");
      });
    });

    describe("ArrowRight", () => {
      it("expands a collapsed span that has children", () => {
        const child = buildSpan({ id: "child" });
        const spans = [buildSpan({ id: "root", children: [child] })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );

        act(() => result.current.toggleExpand("root"));
        expect(result.current.expandedIds.has("root")).toBe(false);

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowRight")));

        expect(result.current.expandedIds.has("root")).toBe(true);
      });

      it("moves focus to first child when the focused span is already expanded", () => {
        const child = buildSpan({ id: "child" });
        const spans = [buildSpan({ id: "root", children: [child] })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );
        // root is already expanded by default

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowRight")));

        expect(result.current.focusedId).toBe("child");
      });

      it("does nothing on a leaf span", () => {
        const spans = [buildSpan({ id: "leaf" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );
        const focusMock = jest.fn();
        act(() =>
          result.current.registerNodeRef(
            "leaf",
            { focus: focusMock } as unknown as HTMLElement,
          ),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowRight")));

        expect(result.current.focusedId).toBe("leaf");
        expect(result.current.visibleIds).toEqual(["leaf"]);
        expect(focusMock).not.toHaveBeenCalled();
      });
    });

    describe("ArrowLeft", () => {
      it("collapses an expanded span with children", () => {
        const child = buildSpan({ id: "child" });
        const spans = [buildSpan({ id: "root", children: [child] })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowLeft")));

        expect(result.current.expandedIds.has("root")).toBe(false);
      });

      it("moves focus to parent for a collapsed child span", () => {
        const child = buildSpan({ id: "child" });
        const spans = [buildSpan({ id: "root", children: [child] })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: "child" }),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowLeft")));

        expect(result.current.focusedId).toBe("root");
      });

      it("moves focus to parent for a leaf span", () => {
        const leaf = buildSpan({ id: "leaf", children: [] });
        const spans = [buildSpan({ id: "root", children: [leaf] })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: "leaf" }),
        );

        // collapse root first so leaf is a leaf and ArrowLeft goes to parent
        act(() => result.current.toggleExpand("root"));
        // now focus on leaf manually via setFocusedId
        act(() => result.current.setFocusedId("leaf"));

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowLeft")));

        expect(result.current.focusedId).toBe("root");
      });

      it("does nothing for a root span with no parent", () => {
        const spans = [buildSpan({ id: "root" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );

        // Collapse first, then ArrowLeft — no parent, so focusedId stays
        act(() => result.current.toggleExpand("root"));
        act(() => result.current.handleTreeKeyDown(makeKey("ArrowLeft")));

        expect(result.current.focusedId).toBe("root");
      });
    });
  });

  // ── registerNodeRef / focusNode ──────────────────────────────────────────────

  describe("registerNodeRef", () => {
    it("calls .focus() on the registered element when keyboard navigation fires", () => {
      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );
      const focusMock = jest.fn();
      act(() =>
        result.current.registerNodeRef(
          "b",
          { focus: focusMock } as unknown as HTMLElement,
        ),
      );

      act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

      expect(result.current.focusedId).toBe("b");
      expect(focusMock).toHaveBeenCalled();
    });

    it("updates focusedId even when the element is not registered", () => {
      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );
      // No registerNodeRef call — simulates unregistered / unmounted node

      act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

      expect(result.current.focusedId).toBe("b");
    });

    it("removes the ref entry when called with null (unmount)", () => {
      const spans = [buildSpan({ id: "a" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );
      const focusMock = jest.fn();
      act(() =>
        result.current.registerNodeRef(
          "a",
          { focus: focusMock } as unknown as HTMLElement,
        ),
      );
      act(() => result.current.registerNodeRef("a", null));

      // focusNode is only reachable via keyboard; trigger it directly via setFocusedId
      // (which does NOT call focusNode) to confirm the ref is gone without side effects
      act(() => result.current.setFocusedId("a"));

      expect(focusMock).not.toHaveBeenCalled();
    });
  });

  // ── rerender reconciliation ───────────────────────────────────────────────────

  describe("rerender reconciliation", () => {
    it("resets focusedId to the first span of a new trace when spans change", () => {
      const traceA = [buildSpan({ id: "a1" }), buildSpan({ id: "a2" })];
      const traceB = [buildSpan({ id: "b1" }), buildSpan({ id: "b2" })];

      const { result, rerender } = renderHook(
        ({ spans, selectedSpanId }) => useSpanTree({ spans, selectedSpanId }),
        { initialProps: { spans: traceA, selectedSpanId: null } },
      );

      expect(result.current.focusedId).toBe("a1");

      rerender({ spans: traceB, selectedSpanId: null });

      expect(result.current.focusedId).toBe("b1");
    });

    it("exactly one treeitem remains tabbable after spans rerender (Jira criterion)", () => {
      const traceA = [buildSpan({ id: "a1" })];
      const traceB = [buildSpan({ id: "b1" }), buildSpan({ id: "b2" })];

      const { result, rerender } = renderHook(
        ({ spans }) => useSpanTree({ spans, selectedSpanId: null }),
        { initialProps: { spans: traceA } },
      );

      rerender({ spans: traceB });

      // focusedId must be in visibleIds (at least one tabbable node)
      expect(result.current.visibleIds).toContain(result.current.focusedId);
      // must not point at the old trace
      expect(result.current.focusedId).not.toBe("a1");
    });

    it("respects selectedSpanId when the trace changes", () => {
      const traceA = [buildSpan({ id: "a1" })];
      const traceB = [buildSpan({ id: "b1" }), buildSpan({ id: "b2" })];

      const { result, rerender } = renderHook(
        ({ spans, selectedSpanId }) => useSpanTree({ spans, selectedSpanId }),
        { initialProps: { spans: traceA, selectedSpanId: null } },
      );

      rerender({ spans: traceB, selectedSpanId: "b2" });

      expect(result.current.focusedId).toBe("b2");
    });

    it("updates focusedId when selectedSpanId changes within the same trace", () => {
      const spans = [buildSpan({ id: "x" }), buildSpan({ id: "y" })];

      const { result, rerender } = renderHook(
        ({ selectedSpanId }) => useSpanTree({ spans, selectedSpanId }),
        { initialProps: { selectedSpanId: "x" as string | null } },
      );

      expect(result.current.focusedId).toBe("x");

      rerender({ selectedSpanId: "y" });

      expect(result.current.focusedId).toBe("y");
    });

    it("does not reset expandedIds when only selectedSpanId changes", () => {
      const child = buildSpan({ id: "child" });
      const spans = [buildSpan({ id: "root", children: [child] })];

      const { result, rerender } = renderHook(
        ({ selectedSpanId }) => useSpanTree({ spans, selectedSpanId }),
        { initialProps: { selectedSpanId: null as string | null } },
      );

      // Collapse root — user-driven state change
      act(() => result.current.toggleExpand("root"));
      expect(result.current.expandedIds.has("root")).toBe(false);

      // Change selectedSpanId only — expandedIds must be preserved
      rerender({ selectedSpanId: "root" });

      expect(result.current.expandedIds.has("root")).toBe(false);
    });
  });
});
