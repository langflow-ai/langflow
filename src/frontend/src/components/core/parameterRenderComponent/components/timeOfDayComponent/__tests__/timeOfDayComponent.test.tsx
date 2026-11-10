import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import TimeOfDayComponent from "../index";

const baseProps = {
  id: "times",
  editNode: false,
  disabled: false,
  nodeClass: {} as never,
  handleNodeClass: jest.fn(),
  nodeId: "node",
};

const plain = (text: string) => text.replace(/[  ]/g, " ");

const renderList = (value: string[], handleOnNewValue = jest.fn()) => {
  render(
    <TimeOfDayComponent
      {...baseProps}
      list
      value={value}
      handleOnNewValue={handleOnNewValue}
    />,
  );
  return handleOnNewValue;
};

describe("TimeOfDayComponent", () => {
  it("should_show_saved_times_in_twelve_hour_time_in_english", () => {
    renderList(["18:30", "08:00"]);

    expect(
      plain((screen.getByTestId("times_0") as HTMLInputElement).value),
    ).toBe("6:30 PM");
    expect(
      plain((screen.getByTestId("times_1") as HTMLInputElement).value),
    ).toBe("8:00 AM");
  });

  it("should_save_a_typed_time_as_24_hour_time", () => {
    const save = renderList(["08:00"]);

    const input = screen.getByTestId("times_0");
    fireEvent.change(input, { target: { value: "6:45 pm" } });
    fireEvent.blur(input);

    expect(save).toHaveBeenCalledWith({ value: ["18:45"] });
  });

  it("should_say_how_to_write_a_time_it_cannot_read_and_keep_the_old_one", () => {
    const save = renderList(["08:00"]);

    const input = screen.getByTestId("times_0");
    fireEvent.change(input, { target: { value: "25:00" } });
    fireEvent.blur(input);

    expect(save).not.toHaveBeenCalled();
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(plain(screen.getByRole("alert").textContent ?? "")).toBe(
      "Enter a time such as 6:30 PM.",
    );
  });

  it("should_add_and_remove_times", () => {
    const save = renderList(["08:00", "12:00"]);

    fireEvent.click(screen.getByTestId("times_add"));
    expect(save).toHaveBeenLastCalledWith({ value: ["08:00", "12:00", ""] });

    fireEvent.click(screen.getAllByRole("button", { name: /remove/i })[0]);
    expect(save).toHaveBeenLastCalledWith({ value: ["12:00"] });
  });

  it("should_have_no_accessibility_violations", async () => {
    const { container } = render(
      <div>
        <span id="times-label">Time of day</span>
        <TimeOfDayComponent
          {...baseProps}
          list
          value={["08:00", "12:00"]}
          handleOnNewValue={jest.fn()}
          ariaLabelledBy="times-label"
        />
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
