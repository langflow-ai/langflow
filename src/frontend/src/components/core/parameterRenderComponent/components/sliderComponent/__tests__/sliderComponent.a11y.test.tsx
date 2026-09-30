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

  // Regression guard, isolated from label text: the tests above pass
  // because the thumb's *computed accessible name* happens to match the
  // label's text — that would still be true if the thumb pointed at some
  // other element that coincidentally said "Temperature" too. Proving the
  // wiring itself (not just the end result) means asserting the thumb's
  // aria-labelledby value is literally the label's id, with a label whose
  // text gives no hint either way.
  it("wires the thumb's aria-labelledby to the label element's own id, not merely matching text", () => {
    render(
      <>
        <span id="node-3-field-x-label">x</span>
        <SliderComponent {...baseProps} ariaLabelledBy="node-3-field-x-label" />
      </>,
    );

    const thumb = screen.getByRole("slider");
    expect(thumb.getAttribute("aria-labelledby")).toBe("node-3-field-x-label");
    expect(document.getElementById("node-3-field-x-label")).toBe(
      screen.getByText("x"),
    );
  });
});
