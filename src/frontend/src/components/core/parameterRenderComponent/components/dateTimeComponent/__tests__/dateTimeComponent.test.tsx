import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import DateTimeComponent from "../index";

const baseProps = {
  id: "run_at",
  editNode: false,
  disabled: false,
  nodeClass: {} as never,
  handleNodeClass: jest.fn(),
  nodeId: "node",
};

const plain = (text: string) => text.replace(/[  ]/g, " ");

describe("DateTimeComponent", () => {
  it("should_show_the_saved_date_and_the_time_in_the_readers_clock", () => {
    render(
      <DateTimeComponent
        {...baseProps}
        value="2026-12-24T18:30"
        handleOnNewValue={jest.fn()}
      />,
    );

    expect(screen.getByTestId("run_at_date")).toHaveValue("2026-12-24");
    expect(
      plain((screen.getByTestId("run_at_time") as HTMLInputElement).value),
    ).toBe("6:30 PM");
  });

  it("should_save_once_both_the_date_and_the_time_are_set", () => {
    const save = jest.fn();
    render(
      <DateTimeComponent {...baseProps} value="" handleOnNewValue={save} />,
    );

    fireEvent.change(screen.getByTestId("run_at_date"), {
      target: { value: "2026-12-24" },
    });
    expect(save).not.toHaveBeenCalled();

    const time = screen.getByTestId("run_at_time");
    fireEvent.change(time, { target: { value: "9:15 AM" } });
    fireEvent.blur(time);

    expect(save).toHaveBeenCalledWith({ value: "2026-12-24T09:15" });
  });

  it("should_have_no_accessibility_violations", async () => {
    const { container } = render(
      <div>
        <span id="run-at-label">Date and time</span>
        <DateTimeComponent
          {...baseProps}
          value="2026-12-24T18:30"
          handleOnNewValue={jest.fn()}
          ariaLabelledBy="run-at-label"
        />
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
