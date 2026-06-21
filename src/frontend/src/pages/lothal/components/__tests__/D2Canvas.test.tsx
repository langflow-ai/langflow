import { act, fireEvent, render } from "@testing-library/react";
import { D2Canvas } from "../D2Canvas";

const b64 = (s: string) => window.btoa(s);

// jsdom has no PointerEvent and drops the init dict on fireEvent.pointer*, so
// build a MouseEvent (which carries clientX/button) and graft pointerId on.
function pointer(
  type: string,
  init: { pointerId: number; clientX?: number; button?: number },
): MouseEvent {
  const ev = new MouseEvent(type, {
    bubbles: true,
    clientX: init.clientX ?? 0,
    button: init.button ?? 0,
  });
  Object.defineProperty(ev, "pointerId", { value: init.pointerId });
  return ev;
}

describe("D2Canvas", () => {
  it("injects the server SVG markup", () => {
    const { container } = render(<D2Canvas svg="<svg><g>hi</g></svg>" />);
    expect(container.querySelector("svg g")?.textContent).toBe("hi");
  });

  it("sanitizes the server SVG, stripping injected scripts", () => {
    const { container } = render(
      <D2Canvas svg='<svg><script>alert(1)</script><g class="a">ok</g></svg>' />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("svg g")?.textContent).toBe("ok");
  });

  it("sizes the holder to the SVG's viewBox so it renders at natural size", () => {
    const { container } = render(
      <D2Canvas svg='<svg viewBox="0 0 320 240"></svg>' />,
    );
    const holder = container.querySelector(".lothal-d2-holder") as HTMLElement;
    expect(holder.style.width).toBe("320px");
    expect(holder.style.height).toBe("240px");
  });

  it("sizes the holder from a comma-separated, padded viewBox", () => {
    const { container } = render(
      <D2Canvas svg='<svg viewBox=" 0,0,320,240 "></svg>' />,
    );
    const holder = container.querySelector(".lothal-d2-holder") as HTMLElement;
    expect(holder.style.width).toBe("320px");
    expect(holder.style.height).toBe("240px");
  });

  it("ignores a second pointer landing mid-drag", () => {
    const { container } = render(<D2Canvas svg="<svg></svg>" />);
    const surface = container.querySelector(".lothal-d2-canvas") as HTMLElement;
    const holder = container.querySelector(".lothal-d2-holder") as HTMLElement;
    surface.setPointerCapture = jest.fn();
    surface.releasePointerCapture = jest.fn();

    // First pointer starts a pan and drags 40px right.
    fireEvent(surface, pointer("pointerdown", { pointerId: 1, clientX: 0 }));
    fireEvent(surface, pointer("pointermove", { pointerId: 1, clientX: 40 }));
    // A second finger lands — it must not hijack the active drag.
    fireEvent(surface, pointer("pointerdown", { pointerId: 2, clientX: 200 }));
    fireEvent(surface, pointer("pointermove", { pointerId: 1, clientX: 60 }));
    expect(holder.style.transform).toContain("translate(60px, 0px)");

    // The first pointer releases cleanly (its capture, not the second's).
    fireEvent(surface, pointer("pointerup", { pointerId: 1 }));
    expect(surface.releasePointerCapture).toHaveBeenCalledWith(1);
  });

  it("calls onAnchor with the resolved element on double-click", () => {
    const onAnchor = jest.fn();
    const { container } = render(
      <D2Canvas
        svg={`<svg><g class="shape ${b64("checkout")}"><rect/></g></svg>`}
        onAnchor={onAnchor}
      />,
    );
    const node = container.querySelector("g.shape") as Element;
    fireEvent.dblClick(node);
    expect(onAnchor).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "node", id: "checkout" }),
    );
  });

  it("resolves the element under the cursor when pointer capture retargets the dblclick", () => {
    // The pan gesture's setPointerCapture retargets the dblclick to the viewport
    // div (not the shape), so the handler must geometry hit-test via
    // elementFromPoint. jsdom has none, so stub it to return the real shape.
    const onAnchor = jest.fn();
    const { container } = render(
      <D2Canvas
        svg={`<svg><g class="shape ${b64("checkout")}"><rect/></g></svg>`}
        onAnchor={onAnchor}
      />,
    );
    const shape = container.querySelector("g.shape") as Element;
    const viewport = container.querySelector(".lothal-d2-canvas") as Element;
    const efp = jest.fn(() => shape);
    const doc = document as unknown as { elementFromPoint?: unknown };
    const prev = doc.elementFromPoint;
    doc.elementFromPoint = efp;
    try {
      // Fire on the viewport (the retargeted target), not the shape.
      fireEvent.dblClick(viewport);
    } finally {
      // Restore whatever was there (jsdom has none today, but don't assume).
      if (prev === undefined) delete doc.elementFromPoint;
      else doc.elementFromPoint = prev;
    }
    expect(efp).toHaveBeenCalled();
    expect(onAnchor).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "node", id: "checkout" }),
    );
  });

  it("does not throw on double-click when no element is hit", () => {
    const onAnchor = jest.fn();
    const { container } = render(
      <D2Canvas svg="<svg></svg>" onAnchor={onAnchor} />,
    );
    fireEvent.dblClick(container.querySelector("svg") as Element);
    expect(onAnchor).not.toHaveBeenCalled();
  });

  it("exposes zoom controls", () => {
    const { getByLabelText } = render(<D2Canvas svg="<svg></svg>" />);
    expect(getByLabelText("Zoom in")).toBeInTheDocument();
    expect(getByLabelText("Zoom out")).toBeInTheDocument();
  });

  it("re-fits the diagram when the viewport resizes (ResizeObserver)", () => {
    // jsdom has neither ResizeObserver nor real layout boxes. Provide a mock
    // observer whose callback we can fire on demand, so we can prove a resize
    // re-runs the fit.
    const fires: Array<() => void> = [];
    class MockResizeObserver {
      constructor(private cb: () => void) {}
      observe() {
        fires.push(() => this.cb());
      }
      unobserve() {}
      disconnect() {}
    }
    const g = globalThis as { ResizeObserver?: unknown };
    g.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;
    try {
      const { container } = render(
        <D2Canvas svg='<svg viewBox="0 0 400 300"></svg>' />,
      );
      const surface = container.querySelector(
        ".lothal-d2-canvas",
      ) as HTMLElement;
      const holder = container.querySelector(
        ".lothal-d2-holder",
      ) as HTMLElement;
      // On mount the viewport has zero size (jsdom), so the fit no-ops and the
      // transform stays at its default.
      expect(holder.style.transform).toBe("translate(0px, 0px) scale(1)");

      // Give the viewport a real size and fire the observer: the 400×300 diagram
      // now fits a 800×600 viewport at scale 1, centred.
      Object.defineProperty(surface, "clientWidth", {
        configurable: true,
        value: 800,
      });
      Object.defineProperty(surface, "clientHeight", {
        configurable: true,
        value: 600,
      });
      act(() => {
        for (const fire of fires) fire();
      });
      expect(holder.style.transform).toBe("translate(200px, 150px) scale(1)");
    } finally {
      g.ResizeObserver = undefined;
    }
  });
});
