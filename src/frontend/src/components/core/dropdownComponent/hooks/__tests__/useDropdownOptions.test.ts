import { act, renderHook } from "@testing-library/react";
import { useDropdownOptions } from "../useDropdownOptions";

const OPTIONS = ["08:00", "09:00"];

const renderOptions = (combobox: boolean, onSelect: jest.Mock) =>
  renderHook(() =>
    useDropdownOptions({
      value: "08:15",
      options: OPTIONS,
      validOptions: OPTIONS,
      optionsMetaData: undefined,
      combobox,
      disabled: false,
      hasChildren: false,
      onSelect,
    }),
  );

describe("useDropdownOptions saved custom value", () => {
  it("should_keep_a_saved_combobox_value_when_the_list_opens_and_closes", () => {
    const onSelect = jest.fn();
    const { result } = renderOptions(true, onSelect);

    act(() => result.current.setOpen(true));
    act(() => result.current.setOpen(false));

    expect(result.current.filteredOptions).toContain("08:15");
    expect(onSelect).not.toHaveBeenCalledWith("", undefined, true);
  });

  it("should_clear_a_value_outside_the_options_when_combobox_is_off", () => {
    const onSelect = jest.fn();
    renderOptions(false, onSelect);

    expect(onSelect).toHaveBeenCalledWith("", undefined, true);
  });
});
