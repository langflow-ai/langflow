import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DateRangePopover } from "../DateRangePopover";
import { formatDateLabel } from "../traceViewHelpers";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, ...props }: { name: string }) => (
    <span data-testid={`icon-${name}`} data-icon-name={name} {...props} />
  ),
}));

describe("DateRangePopover", () => {
  it("renders Any time when no dates are set", () => {
    render(
      <DateRangePopover
        startDate=""
        endDate=""
        onStartDateChange={jest.fn()}
        onEndDateChange={jest.fn()}
      />,
    );
    expect(screen.queryByLabelText("Invalid date range")).toBeNull();
  });

  it("renders a formatted range label", () => {
    const startDate = "2025-05-10";
    const endDate = "2025-05-12";
    const expectedLabel = `${formatDateLabel(startDate)} - ${formatDateLabel(endDate)}`;

    render(
      <DateRangePopover
        startDate={startDate}
        endDate={endDate}
        onStartDateChange={jest.fn()}
        onEndDateChange={jest.fn()}
      />,
    );

    expect(screen.getByText(expectedLabel)).toBeInTheDocument();
  });

  it("shows an invalid indicator when end date is earlier", () => {
    render(
      <DateRangePopover
        startDate="2025-05-10"
        endDate="2025-05-01"
        onStartDateChange={jest.fn()}
        onEndDateChange={jest.fn()}
      />,
    );

    expect(screen.getByLabelText("Invalid date range")).toBeInTheDocument();
  });

  it("updates start and end dates on input change", async () => {
    const user = userEvent.setup();
    const onStartDateChange = jest.fn();
    const onEndDateChange = jest.fn();

    render(
      <DateRangePopover
        startDate=""
        endDate=""
        onStartDateChange={onStartDateChange}
        onEndDateChange={onEndDateChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Date range" }));

    fireEvent.change(screen.getByLabelText("Start date"), {
      target: { value: "2025-06-01" },
    });
    fireEvent.change(screen.getByLabelText("End date"), {
      target: { value: "2025-06-05" },
    });

    expect(onStartDateChange).toHaveBeenCalledWith("2025-06-01");
    expect(onEndDateChange).toHaveBeenCalledWith("2025-06-05");
  });

  it("clears both dates when Clear dates is clicked", async () => {
    const user = userEvent.setup();
    const onStartDateChange = jest.fn();
    const onEndDateChange = jest.fn();

    render(
      <DateRangePopover
        startDate="2025-05-10"
        endDate="2025-05-12"
        onStartDateChange={onStartDateChange}
        onEndDateChange={onEndDateChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Date range" }));
    await user.click(screen.getByRole("button", { name: "Clear Dates" }));

    expect(onStartDateChange).toHaveBeenCalledWith("");
    expect(onEndDateChange).toHaveBeenCalledWith("");
  });
});
