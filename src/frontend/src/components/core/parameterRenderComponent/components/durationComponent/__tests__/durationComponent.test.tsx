import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import DurationComponent from "../index";

const baseProps = {
  id: "timeout",
  editNode: false,
  disabled: false,
  nodeClass: {} as never,
  handleNodeClass: jest.fn(),
  nodeId: "node",
  name: "timeout",
};

describe("DurationComponent", () => {
  it("should render the numeric value and the unit tabs", () => {
    render(
      <DurationComponent
        {...baseProps}
        value={{ value: 3, unit: "Days" }}
        options={["Minutes", "Hours", "Days"]}
        handleOnNewValue={jest.fn()}
      />,
    );
    expect(screen.getByTestId("duration-value-timeout")).toHaveValue(3);
    expect(screen.getByTestId("duration-unit-0_minutes")).toBeInTheDocument();
    expect(screen.getByTestId("duration-unit-2_days")).toBeInTheDocument();
  });

  it("should emit the merged value when the number changes", () => {
    const handleOnNewValue = jest.fn();
    render(
      <DurationComponent
        {...baseProps}
        value={{ value: 3, unit: "Days" }}
        options={["Minutes", "Hours", "Days"]}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.change(screen.getByTestId("duration-value-timeout"), {
      target: { value: "10" },
    });
    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: { value: 10, unit: "Days" },
    });
  });

  it("should emit the merged value when the unit changes", () => {
    const handleOnNewValue = jest.fn();
    render(
      <DurationComponent
        {...baseProps}
        value={{ value: 3, unit: "Days" }}
        options={["Minutes", "Hours", "Days"]}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.mouseDown(screen.getByTestId("duration-unit-0_minutes"));
    fireEvent.click(screen.getByTestId("duration-unit-0_minutes"));
    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: { value: 3, unit: "Minutes" },
    });
  });

  it("should coerce a malformed value to a safe default", () => {
    render(
      <DurationComponent
        {...baseProps}
        value={undefined as never}
        options={["Minutes", "Hours", "Days"]}
        handleOnNewValue={jest.fn()}
      />,
    );
    expect(screen.getByTestId("duration-value-timeout")).toHaveValue(0);
  });

  it("should coerce a non-numeric input to 0 instead of NaN", () => {
    const handleOnNewValue = jest.fn();
    render(
      <DurationComponent
        {...baseProps}
        value={{ value: 3, unit: "Days" }}
        options={["Minutes", "Hours", "Days"]}
        handleOnNewValue={handleOnNewValue}
      />,
    );
    fireEvent.change(screen.getByTestId("duration-value-timeout"), {
      target: { value: "" },
    });
    expect(handleOnNewValue).toHaveBeenCalledWith({
      value: { value: 0, unit: "Days" },
    });
  });
});

describe("DurationComponent accessibility", () => {
  // A real label element is required here: aria-labelledby pointing at a
  // missing id is itself an axe violation, so a dangling id would mask the
  // exact regression these tests exist to catch.
  const renderWithLabel = (extraProps = {}) =>
    render(
      <>
        <span id="timeout-label">Timeout</span>
        <DurationComponent
          {...baseProps}
          value={{ value: 3, unit: "Days" }}
          options={["Minutes", "Hours", "Days"]}
          handleOnNewValue={jest.fn()}
          ariaLabelledBy="timeout-label"
          {...extraProps}
        />
      </>,
    );

  it("should_have_no_axe_violations", async () => {
    const { container } = renderWithLabel();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_the_field_label_as_the_numeric_input_accessible_name", () => {
    renderWithLabel();
    expect(screen.getByRole("spinbutton", { name: "Timeout" })).toBe(
      screen.getByTestId("duration-value-timeout"),
    );
  });

  it("should_expose_the_field_label_as_the_unit_tablist_accessible_name", () => {
    renderWithLabel();
    expect(
      screen.getByRole("tablist", { name: "Timeout" }),
    ).toBeInTheDocument();
  });

  it("should_render_with_no_accessible_name_when_ariaLabelledBy_is_absent", () => {
    render(
      <DurationComponent
        {...baseProps}
        value={{ value: 3, unit: "Days" }}
        options={["Minutes", "Hours", "Days"]}
        handleOnNewValue={jest.fn()}
      />,
    );
    expect(
      screen.getByTestId("duration-value-timeout"),
    ).not.toHaveAccessibleName();
  });
});
