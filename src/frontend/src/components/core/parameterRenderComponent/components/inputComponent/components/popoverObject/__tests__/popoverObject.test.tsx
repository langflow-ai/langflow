import { fireEvent, render, screen } from "@testing-library/react";
import { createRef } from "react";
import CustomInputPopoverObject from "../index";

const baseOptions = [
  { id: "a", name: "Alpha" },
  { id: "b", name: "Bravo" },
];

const renderPopoverObject = (overrides: Record<string, unknown> = {}) => {
  const refInput = createRef<HTMLInputElement>();
  const defaults = {
    id: "popover-object-input",
    refInput,
    onInputLostFocus: () => {},
    selectedOption: "",
    setSelectedOption: undefined,
    selectedOptions: undefined,
    setSelectedOptions: undefined,
    value: "",
    autoFocus: false,
    disabled: false,
    setShowOptions: () => {},
    required: false,
    editNode: false,
    className: "",
    placeholder: "",
    onChange: () => {},
    blurOnEnter: false,
    options: baseOptions,
    optionsPlaceholder: "",
    optionButton: undefined,
    optionsButton: undefined,
    handleKeyDown: () => {},
    showOptions: false,
    inspectionPanel: false,
  };
  return {
    refInput,
    ...render(<CustomInputPopoverObject {...defaults} {...overrides} />),
  };
};

describe("CustomInputPopoverObject", () => {
  describe("text-entry mode", () => {
    it("renders displayValue and wires IME onChange when no selection setters exist", () => {
      const onChange = jest.fn();
      renderPopoverObject({ value: "hello", onChange });
      const input = screen.getByTestId(
        "popover-object-input",
      ) as HTMLInputElement;

      expect(input.value).toBe("hello");
      expect(input.readOnly).toBe(false);

      fireEvent.change(input, { target: { value: "hello!" } });
      expect(onChange).toHaveBeenCalledWith("hello!");
    });
  });

  describe("single-selection mode", () => {
    it("renders the selected option name as read-only when selectedOption is set", () => {
      renderPopoverObject({
        selectedOption: "a",
        setSelectedOption: jest.fn(),
        options: baseOptions,
      });
      const input = screen.getByTestId(
        "popover-object-input",
      ) as HTMLInputElement;

      expect(input.value).toBe("Alpha");
      expect(input.readOnly).toBe(true);
    });

    it("falls back to empty string when selected id is not in options", () => {
      renderPopoverObject({
        selectedOption: "missing",
        setSelectedOption: jest.fn(),
        options: baseOptions,
      });
      const input = screen.getByTestId(
        "popover-object-input",
      ) as HTMLInputElement;
      expect(input.value).toBe("");
    });

    it("does not crash when options is undefined", () => {
      expect(() =>
        renderPopoverObject({
          selectedOption: "a",
          setSelectedOption: jest.fn(),
          options: undefined,
        }),
      ).not.toThrow();
      const input = screen.getByTestId(
        "popover-object-input",
      ) as HTMLInputElement;
      expect(input.value).toBe("");
    });
  });

  describe("multi-selection mode", () => {
    it("joins selected option names with comma when selectedOptions is non-empty", () => {
      renderPopoverObject({
        selectedOptions: ["a", "b"],
        setSelectedOptions: jest.fn(),
        options: baseOptions,
      });
      const input = screen.getByTestId(
        "popover-object-input",
      ) as HTMLInputElement;

      expect(input.value).toBe("Alpha, Bravo");
      expect(input.readOnly).toBe(true);
    });

    it("does not crash when selectedOptions is undefined but setSelectedOptions exists", () => {
      // `selectedOptions?.length !== 0` is true for undefined, so the branch
      // activates — the null-guard (selectedOptions ?? []) prevents a crash.
      expect(() =>
        renderPopoverObject({
          selectedOptions: undefined,
          setSelectedOptions: jest.fn(),
          onChange: undefined,
          options: baseOptions,
        }),
      ).not.toThrow();
    });

    it("does not crash when options is undefined in multi-selection mode", () => {
      expect(() =>
        renderPopoverObject({
          selectedOptions: ["a"],
          setSelectedOptions: jest.fn(),
          options: undefined,
        }),
      ).not.toThrow();
    });
  });
});
