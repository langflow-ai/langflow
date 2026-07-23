import { fireEvent, render, screen } from "@testing-library/react";
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
