import { fireEvent, render } from "@testing-library/react";
import { D2Canvas } from "../D2Canvas";

const b64 = (s: string) => window.btoa(s);

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
});
