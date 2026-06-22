import { act, renderHook } from "@testing-library/react";
import { useSpanTree } from "../useSpanTree";
import { buildSpan } from "./spanTestUtils";

const makeKey = (key: string): React.KeyboardEvent =>
  ({ key, preventDefault: jest.fn() }) as unknown as React.KeyboardEvent;

describe("useSpanTree", () => {
  let focusEl: { focus: jest.Mock };

  beforeEach(() => {
    focusEl = { focus: jest.fn() };
    jest
      .spyOn(document, "querySelector")
      .mockReturnValue(focusEl as unknown as Element);
  });

  afterEach(() => jest.restoreAllMocks());

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
      it("moves focusedId to the next visible span", () => {
        const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: null }),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

        expect(result.current.focusedId).toBe("b");
        expect(focusEl.focus).toHaveBeenCalled();
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
      it("moves focusedId to the previous visible span", () => {
        const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
        const { result } = renderHook(() =>
          useSpanTree({ spans, selectedSpanId: "b" }),
        );

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowUp")));

        expect(result.current.focusedId).toBe("a");
        expect(focusEl.focus).toHaveBeenCalled();
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

        act(() => result.current.handleTreeKeyDown(makeKey("ArrowRight")));

        expect(result.current.focusedId).toBe("leaf");
        expect(result.current.visibleIds).toEqual(["leaf"]);
        expect(focusEl.focus).not.toHaveBeenCalled();
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

  // ── focusNode (via keyboard navigation) ──────────────────────────────────────

  describe("focusNode (via keyboard)", () => {
    it("calls focus() on the DOM node when ArrowDown fires", () => {
      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

      expect(document.querySelector).toHaveBeenCalledWith(
        '[data-testid="span-node-b"]',
      );
      expect(focusEl.focus).toHaveBeenCalled();
    });

    it("updates focusedId even when the DOM element is not found", () => {
      jest
        .spyOn(document, "querySelector")
        .mockReturnValue(null as unknown as Element);

      const spans = [buildSpan({ id: "a" }), buildSpan({ id: "b" })];
      const { result } = renderHook(() =>
        useSpanTree({ spans, selectedSpanId: null }),
      );

      act(() => result.current.handleTreeKeyDown(makeKey("ArrowDown")));

      expect(result.current.focusedId).toBe("b");
    });
  });
});
