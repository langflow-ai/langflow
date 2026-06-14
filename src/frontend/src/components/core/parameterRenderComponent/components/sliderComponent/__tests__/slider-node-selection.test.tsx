import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import SliderComponent from "../index";

/**
 * Regression guard for the "Depth slider value lost on node selection" bug.
 *
 * Sliders live inside React Flow nodes. React Flow selects a node on `click`
 * and pans/drags it on `pointerdown`, while Radix drives the slider with the
 * same pointer events. When the interactive slider root does not isolate those
 * events, the first interaction on an *unselected* node is consumed by node
 * selection: the slider reacts visually but the value the user set is never
 * committed (it reverts or snaps to wherever the pointer landed).
 *
 * The fix stops pointer/click propagation on `SliderPrimitive.Root` and adds
 * React Flow's opt-out classes. These tests use a parent that stands in for the
 * node wrapper and assert that slider interactions never reach it, while
 * unrelated children still bubble normally.
 */

beforeAll(() => {
  // Radix Slider uses the Pointer Events API + pointer capture, which jsdom
  // does not fully implement. Polyfill them so the Radix handlers can run
  // during the test without throwing. MouseEvent is a constructible, bubbling
  // stand-in for PointerEvent; the handlers only read event.pointerId, which is
  // harmlessly undefined here.
  if (!("PointerEvent" in window)) {
    window.PointerEvent = window.MouseEvent as unknown as typeof PointerEvent;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = jest.fn();
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = jest.fn();
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = jest.fn(() => false);
  }
});

const renderSliderInNode = () => {
  const parentPointerDown = jest.fn();
  const parentClick = jest.fn();

  const sliderProps: ComponentProps<typeof SliderComponent> = {
    id: "slider_test",
    // The value prop type collapses to `never` (legacy generic: both
    // BaseInputProps and SliderComponentType declare `value`). The component
    // coerces it with Number() at runtime, so a scalar is what it expects.
    value: 1 as never,
    editNode: false,
    disabled: false,
    rangeSpec: { min: 1, max: 5, step: 1 },
    handleOnNewValue: jest.fn(),
  };

  render(
    // Stand-in for the React Flow node wrapper: it selects the node on click
    // and would drag it on pointer down.
    <div
      data-testid="rf-node"
      onPointerDown={parentPointerDown}
      onClick={parentClick}
    >
      <SliderComponent {...sliderProps} />
      <button type="button" data-testid="bubbling-control">
        control
      </button>
    </div>,
  );

  return { parentPointerDown, parentClick };
};

describe("SliderComponent — node-selection isolation", () => {
  it("applies React Flow opt-out classes to the interactive slider root", () => {
    renderSliderInNode();

    const sliderRoot = screen.getByTestId("slider_track").parentElement;

    expect(sliderRoot).toHaveClass(
      "nodrag",
      "nopan",
      "noflow",
      "nowheel",
      "nodelete",
    );
  });

  it("does not let a pointer-down on the slider bubble to the node wrapper", () => {
    const { parentPointerDown } = renderSliderInNode();

    fireEvent.pointerDown(screen.getByTestId("slider_thumb"));

    expect(parentPointerDown).not.toHaveBeenCalled();
  });

  it("does not let a click on the slider bubble to the node wrapper (which would select the node)", () => {
    const { parentClick } = renderSliderInNode();

    fireEvent.click(screen.getByTestId("slider_thumb"));

    expect(parentClick).not.toHaveBeenCalled();
  });

  it("still lets unrelated children bubble to the node wrapper (isolation is scoped to the slider)", () => {
    const { parentClick } = renderSliderInNode();

    fireEvent.click(screen.getByTestId("bubbling-control"));

    expect(parentClick).toHaveBeenCalledTimes(1);
  });
});
