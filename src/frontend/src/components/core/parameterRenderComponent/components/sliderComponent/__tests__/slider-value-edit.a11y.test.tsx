import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import SliderComponent from "../index";

beforeAll(() => {
  // Radix Slider needs the Pointer Events API, which jsdom does not implement.
  if (typeof window.PointerEvent === "undefined") {
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

const renderSlider = () => {
  const sliderProps: ComponentProps<typeof SliderComponent> = {
    id: "slider_test",
    // The value prop type collapses to `never` (legacy generic); the component
    // coerces it with Number() at runtime.
    value: 1 as never,
    editNode: false,
    disabled: false,
    rangeSpec: { min: 1, max: 5, step: 1 },
    handleOnNewValue: jest.fn(),
  };

  return render(<SliderComponent {...sliderProps} />);
};

describe("SliderComponent click-to-edit value accessibility", () => {
  it("should_render_the_value_as_a_real_button", () => {
    renderSlider();

    const trigger = screen.getByTestId("default_slider_display_value");
    expect(trigger.tagName).toBe("BUTTON");
    expect(trigger).toHaveAttribute("type", "button");
  });

  it("should_name_the_trigger_with_the_visible_value", () => {
    renderSlider();

    // WCAG 2.5.3: the accessible name must contain the visible text (the value).
    expect(
      screen.getByRole("button", { name: "Edit value 1.00" }),
    ).toBeInTheDocument();
  });

  it("should_enter_edit_mode_from_the_keyboard", () => {
    renderSlider();

    const trigger = screen.getByTestId("default_slider_display_value");
    trigger.focus();
    expect(trigger).toHaveFocus();

    fireEvent.keyDown(trigger, { key: "Enter" });
    fireEvent.click(trigger);

    expect(screen.getByTestId("slider_input")).toBeInTheDocument();
  });
});
