import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { getDefaultDisplay } from "@/pages/FlowPage/components/InspectionPanel/utils";
import type { InputFieldType } from "@/types/api";
import SliderComponent from "../index";

function renderSlider(inverted = true, value = 0.75) {
  const handleOnNewValue = jest.fn();
  const props: ComponentProps<typeof SliderComponent> = {
    id: "guardrails-strictness-test",
    editNode: false,
    disabled: false,
    value: value as never,
    rangeSpec: { min: 0, max: 1, step: 0.05 },
    valueInverted: inverted,
    sliderColor: inverted ? "red" : "default",
    minLabel: "Permissive",
    maxLabel: "Strict",
    handleOnNewValue,
  };
  render(<SliderComponent {...props} />);
  return handleOnNewValue;
}

describe("Slider display inversion", () => {
  it("shows the same strictness scale in the parameter default preview", () => {
    const field: InputFieldType = {
      type: "slider",
      required: false,
      list: false,
      show: true,
      readonly: false,
      value: 0.7,
      value_inverted: true,
      range_spec: { min: 0, max: 1, step: 0.05 },
    };
    expect(getDefaultDisplay(field, 0.75)).toEqual({ text: "0.25" });
    expect(getDefaultDisplay(field)).toEqual({ text: "0.30" });
  });
  it("displays strictness without rewriting a saved threshold", () => {
    const onChange = renderSlider();
    expect(screen.getByRole("slider")).toHaveAttribute("aria-valuenow", "0.25");
    expect(
      screen.getByTestId("default_slider_display_value"),
    ).toHaveTextContent("0.25");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("lowers the stored threshold when strictness increases", () => {
    const onChange = renderSlider();
    fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith({ value: 0.7 });
  });

  it("converts a typed strictness back to the stored threshold", () => {
    const onChange = renderSlider();
    fireEvent.click(screen.getByTestId("default_slider_display_value"));
    fireEvent.change(screen.getByTestId("slider_input"), {
      target: { value: "0.8" },
    });
    fireEvent.blur(screen.getByTestId("slider_input"));
    expect(onChange).toHaveBeenCalledWith({ value: 0.2 });
  });

  it.each([
    [0, "1"],
    [1, "0"],
  ])("preserves the saved boundary %s", (value, displayed) => {
    const onChange = renderSlider(true, value);
    expect(screen.getByRole("slider")).toHaveAttribute(
      "aria-valuenow",
      displayed,
    );
    expect(onChange).not.toHaveBeenCalled();
  });

  it("preserves ordinary slider direction by default", () => {
    const onChange = renderSlider(false);
    expect(screen.getByRole("slider")).toHaveAttribute("aria-valuenow", "0.75");
    fireEvent.keyDown(screen.getByRole("slider"), { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalledWith({ value: 0.8 });
  });
});
