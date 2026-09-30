import { fireEvent, render, screen } from "@testing-library/react";
import { type ComponentProps, createRef } from "react";
import CustomInputPopover from "../index";

const renderWithSelectedOptions = (setSelectedOptions = jest.fn()) => {
  const refInput = createRef<HTMLInputElement>();

  // The component destructures ~30 untyped props, so every one of them counts
  // as required. Only the multiselect-badge path is under test here.
  const props = {
    id: "multiselect-input",
    refInput,
    selectedOptions: ["alpha", "beta"],
    setSelectedOptions,
    value: "",
    disabled: false,
    setShowOptions: jest.fn(),
    showOptions: false,
    options: ["alpha", "beta", "gamma"],
    onChange: jest.fn(),
    editNode: false,
  } as unknown as ComponentProps<typeof CustomInputPopover>;

  render(<CustomInputPopover {...props} />);

  return { setSelectedOptions };
};

describe("Multiselect option badge remove control accessibility", () => {
  it("should_render_remove_controls_as_real_buttons", () => {
    renderWithSelectedOptions();

    const removeControls = screen.getAllByTestId("remove-icon-badge");
    expect(removeControls).toHaveLength(2);
    removeControls.forEach((control) => {
      expect(control.tagName).toBe("BUTTON");
      expect(control).toHaveAttribute("type", "button");
    });
  });

  it("should_name_each_remove_control_with_its_option", () => {
    renderWithSelectedOptions();

    expect(
      screen.getByRole("button", { name: "Remove alpha" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove beta" }),
    ).toBeInTheDocument();
  });

  it("should_be_focusable_and_remove_the_option_on_activation", () => {
    const setSelectedOptions = jest.fn();
    renderWithSelectedOptions(setSelectedOptions);

    const remove = screen.getByRole("button", { name: "Remove alpha" });
    remove.focus();
    expect(remove).toHaveFocus();

    fireEvent.click(remove);

    expect(setSelectedOptions).toHaveBeenCalledWith(["beta"]);
  });
});
