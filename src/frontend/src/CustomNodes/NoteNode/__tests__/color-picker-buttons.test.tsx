/**
 * Unit tests for ColorPickerButtons component
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { COLOR_OPTIONS } from "@/constants/constants";
import type { NoteDataType } from "@/types/flow";
import { ColorPickerButtons } from "../components/color-picker-buttons";

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, className, ...props }: any) => (
    <button onClick={onClick} className={className} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("ColorPickerButtons", () => {
  const mockSetNode = jest.fn();
  const mockData = {
    id: "test-note-id",
    type: "noteNode",
    node: { description: "Test", template: { backgroundColor: "amber" } },
  } as NoteDataType;

  beforeEach(() => jest.clearAllMocks());

  it("renders all preset color buttons", () => {
    render(
      <ColorPickerButtons
        bgColor="amber"
        data={mockData}
        setNode={mockSetNode}
      />,
    );
    Object.keys(COLOR_OPTIONS).forEach((color) => {
      expect(
        screen.getByTestId(`color_picker_button_${color}`),
      ).toBeInTheDocument();
    });
  });

  it("renders custom color picker button", () => {
    render(
      <ColorPickerButtons
        bgColor="amber"
        data={mockData}
        setNode={mockSetNode}
      />,
    );
    expect(
      screen.getByTestId("color_picker_button_custom"),
    ).toBeInTheDocument();
  });

  it("highlights selected preset color", () => {
    render(
      <ColorPickerButtons
        bgColor="amber"
        data={mockData}
        setNode={mockSetNode}
      />,
    );
    const btn = screen.getByTestId("color_picker_button_amber");
    expect(btn.querySelector("div")?.className).toContain("border-blue-500");
  });

  it("calls setNode when preset color clicked", async () => {
    const user = userEvent.setup();
    render(
      <ColorPickerButtons
        bgColor="amber"
        data={mockData}
        setNode={mockSetNode}
      />,
    );
    await user.click(screen.getByTestId("color_picker_button_rose"));
    expect(mockSetNode).toHaveBeenCalledWith(
      "test-note-id",
      expect.any(Function),
    );
  });

  it("calls setNode with custom color on input change", () => {
    render(
      <ColorPickerButtons
        bgColor="amber"
        data={mockData}
        setNode={mockSetNode}
      />,
    );
    const input = screen
      .getByTestId("color_picker_button_custom")
      .querySelector("input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "#FF5733" } });
    expect(mockSetNode).toHaveBeenCalled();
  });
});
