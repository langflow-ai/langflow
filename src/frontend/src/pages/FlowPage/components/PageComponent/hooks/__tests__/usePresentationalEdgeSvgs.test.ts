import { renderHook, waitFor } from "@testing-library/react";
import { createRef } from "react";
import { usePresentationalEdgeSvgs } from "../usePresentationalEdgeSvgs";

const SVG_NS = "http://www.w3.org/2000/svg";

function makeRef(el: HTMLElement | null) {
  const ref = createRef<HTMLElement>();
  Object.defineProperty(ref, "current", { value: el, writable: true });
  return ref;
}

/** Mirrors ReactFlow's edge layer: `<svg>` wrapper around the named `<g>`. */
function appendEdge(layer: Element, label: string) {
  const svg = document.createElementNS(SVG_NS, "svg");
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", "react-flow__edge");
  g.setAttribute("role", "group");
  g.setAttribute("aria-label", label);
  g.setAttribute("tabindex", "0");
  svg.appendChild(g);
  layer.appendChild(svg);
  return { svg, g };
}

function edgeSvgRoles(canvas: HTMLElement) {
  return [...canvas.querySelectorAll(".react-flow__edges > svg")].map((svg) =>
    svg.getAttribute("role"),
  );
}

describe("usePresentationalEdgeSvgs", () => {
  let canvas: HTMLDivElement;
  let layer: HTMLDivElement;

  beforeEach(() => {
    canvas = document.createElement("div");
    layer = document.createElement("div");
    layer.className = "react-flow__edges";
    canvas.appendChild(layer);
    document.body.appendChild(canvas);
  });

  afterEach(() => {
    document.body.removeChild(canvas);
  });

  it("does nothing when the ref is not attached", () => {
    expect(() =>
      renderHook(() => usePresentationalEdgeSvgs(makeRef(null))),
    ).not.toThrow();
  });

  it("marks edge wrappers already mounted when the hook runs", () => {
    appendEdge(layer, "Edge from A to B");
    appendEdge(layer, "Edge from B to C");

    renderHook(() => usePresentationalEdgeSvgs(makeRef(canvas)));

    expect(edgeSvgRoles(canvas)).toEqual(["presentation", "presentation"]);
  });

  it("marks edge wrappers that mount after the hook runs", async () => {
    renderHook(() => usePresentationalEdgeSvgs(makeRef(canvas)));

    appendEdge(layer, "Edge from A to B");

    await waitFor(() => {
      expect(edgeSvgRoles(canvas)).toEqual(["presentation"]);
    });
  });

  it("leaves ReactFlow's already-hidden marker <svg> alone", () => {
    const marker = document.createElementNS(SVG_NS, "svg");
    marker.setAttribute("class", "react-flow__marker");
    marker.setAttribute("aria-hidden", "true");
    marker.setAttribute("role", "presentation");
    layer.appendChild(marker);

    renderHook(() => usePresentationalEdgeSvgs(makeRef(canvas)));

    expect(marker.getAttribute("aria-hidden")).toBe("true");
  });

  it("never hides the wrapper, so the edge's name and tab stop survive", async () => {
    renderHook(() => usePresentationalEdgeSvgs(makeRef(canvas)));

    const { svg, g } = appendEdge(layer, "Edge from A to B");

    await waitFor(() => {
      expect(svg.getAttribute("role")).toBe("presentation");
    });
    // The regression this guards: an `aria-hidden` wrapper would strip the
    // accessible name from every edge and drop them out of the a11y tree.
    expect(svg.hasAttribute("aria-hidden")).toBe(false);
    expect(g.getAttribute("aria-label")).toBe("Edge from A to B");
    expect(g.getAttribute("tabindex")).toBe("0");
  });

  it("stops marking once unmounted", async () => {
    const { unmount } = renderHook(() =>
      usePresentationalEdgeSvgs(makeRef(canvas)),
    );
    unmount();

    const { svg } = appendEdge(layer, "Edge from A to B");

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(svg.getAttribute("role")).toBeNull();
  });
});
