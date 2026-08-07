import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import SliderComponent from "..";

const baseProps = {
  // SliderComponentType.value is typed as string, but the component (and
  // every real caller) passes a number array — same pre-existing type
  // mismatch worked around in slider-node-selection.test.tsx.
  value: [0] as never,
  id: "slider-field",
  editNode: false,
  disabled: false,
  rangeSpec: { min: -2, max: 2, step: 0.01 },
  handleOnNewValue: jest.fn(),
};

describe("SliderComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Temperature</span>
        <SliderComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: Radix puts role="slider" on the Thumb, not the Root —
  // an accessible name applied to the wrong element is silently dropped.
  it("uses the field's real label as the slider thumb's accessible name", () => {
    render(
      <>
        <span id="field-label">Temperature</span>
        <SliderComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("slider", { name: "Temperature" }),
    ).toBeInTheDocument();
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<SliderComponent {...baseProps} />);

    expect(screen.getByRole("slider")).not.toHaveAttribute("aria-labelledby");
  });
});
