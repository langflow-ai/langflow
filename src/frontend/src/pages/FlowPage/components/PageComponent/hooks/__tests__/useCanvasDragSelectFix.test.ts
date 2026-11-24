import { act, renderHook } from "@testing-library/react";
import { createRef } from "react";
import { useCanvasDragSelectFix } from "../useCanvasDragSelectFix";

// Note: jsdom does not implement vendor-prefixed CSS properties such as
// -webkit-user-select, so only the unprefixed user-select property is
// asserted here. The -webkit- prefix is exercised in real WKWebView browsers.

function makeRef(el: HTMLElement | null) {
  const ref = createRef<HTMLElement>();
  Object.defineProperty(ref, "current", { value: el, writable: true });
  return ref;
}

function fireMouseDown(target: HTMLElement, shiftKey = false) {
  target.dispatchEvent(
    new MouseEvent("mousedown", { bubbles: true, shiftKey }),
  );
}

function fireMouseUp() {
  document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
}

function getUserSelect() {
  return document.documentElement.style.getPropertyValue("user-select");
}

describe("useCanvasDragSelectFix", () => {
  let el: HTMLDivElement;

  beforeEach(() => {
    el = document.createElement("div");
    document.body.appendChild(el);
    document.documentElement.style.removeProperty("user-select");
  });

  afterEach(() => {
    document.body.removeChild(el);
    document.documentElement.style.removeProperty("user-select");
  });

  it("does nothing when ref.current is null", () => {
    renderHook(() => useCanvasDragSelectFix(makeRef(null)));
    expect(getUserSelect()).toBe("");
  });

  it("sets user-select:none on mousedown regardless of shift key state", () => {
    renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    act(() => fireMouseDown(el, false));
    expect(getUserSelect()).toBe("none");

    act(() => fireMouseUp());

    act(() => fireMouseDown(el, true));
    expect(getUserSelect()).toBe("none");
  });

  it("restores user-select on mouseup after drag", () => {
    renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    act(() => fireMouseDown(el));
    act(() => fireMouseUp());

    expect(getUserSelect()).toBe("");
  });

  it("only restores once — a second mouseup does not clear a subsequently set value", () => {
    renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    act(() => {
      fireMouseDown(el);
      fireMouseUp();
      document.documentElement.style.setProperty("user-select", "text");
      fireMouseUp();
    });

    // The restore listener was already removed after the first mouseup,
    // so the second mouseup cannot clear the value we just set.
    expect(getUserSelect()).toBe("text");
  });

  it("removes the mousedown listener on unmount", () => {
    const { unmount } = renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    unmount();

    act(() => fireMouseDown(el));

    expect(getUserSelect()).toBe("");
  });

  it("handles multiple drag cycles correctly", () => {
    renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    for (let i = 0; i < 3; i++) {
      act(() => fireMouseDown(el));
      expect(getUserSelect()).toBe("none");

      act(() => fireMouseUp());
      expect(getUserSelect()).toBe("");
    }
  });

  it("triggers on mousedown from a child element that bubbles up to the canvas ref", () => {
    const child = document.createElement("span");
    el.appendChild(child);
    renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    act(() => fireMouseDown(child));

    expect(getUserSelect()).toBe("none");

    el.removeChild(child);
  });

  it("does not add duplicate restore listeners when mousedown fires twice before mouseup", () => {
    renderHook(() => useCanvasDragSelectFix(makeRef(el)));

    act(() => {
      fireMouseDown(el);
      fireMouseDown(el);
    });

    // First mouseup should restore selection
    act(() => fireMouseUp());
    expect(getUserSelect()).toBe("");

    // A subsequent mouseup should not affect a value set after the first restore
    document.documentElement.style.setProperty("user-select", "text");
    act(() => fireMouseUp());
    expect(getUserSelect()).toBe("text");
  });
});
