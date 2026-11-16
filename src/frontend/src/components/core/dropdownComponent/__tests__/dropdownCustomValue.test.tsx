import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef } from "react";
import { Popover, PopoverContent } from "@/components/ui/popover";
import { DropdownSearchInput } from "../components/DropdownSearchInput";
import { DropdownTrigger } from "../components/DropdownTrigger";
import { useDropdownOptions } from "../hooks/useDropdownOptions";

const CUSTOM_MODEL = "us.anthropic.claude-opus-5-5";
const OPTIONS = ["anthropic.claude-3-5-sonnet-20241022-v2:0"];

function ModelDropdown({
  value = CUSTOM_MODEL,
  options = OPTIONS,
  combobox = true,
  onSelect = jest.fn(),
}: {
  value?: string;
  options?: string[];
  combobox?: boolean;
  onSelect?: jest.Mock;
}) {
  const refButton = useRef<HTMLButtonElement>(null);
  const dropdown = useDropdownOptions({
    value,
    options,
    validOptions: options,
    optionsMetaData: undefined,
    combobox,
    hasChildren: false,
    onSelect,
  });

  return (
    <Popover open={dropdown.open} onOpenChange={dropdown.setOpen}>
      <DropdownTrigger
        refButton={refButton}
        id="model-id"
        value={value}
        options={options}
        validOptions={options}
        combobox={combobox}
        sourceOptions={undefined}
        open={dropdown.open}
        filteredOptions={dropdown.filteredOptions}
        filteredMetadata={dropdown.filteredMetadata}
      />
      <PopoverContent>
        <DropdownSearchInput
          onSearch={dropdown.searchRoleByTerm}
          onKeyDown={() => {}}
        />
        <ul aria-label="Model IDs">
          {dropdown.filteredOptions.map((option) => (
            <li key={option}>{option}</li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

describe("Editable dropdown custom values", () => {
  it.each([{ options: OPTIONS }, { options: [] }])(
    "should display a saved custom model with options $options",
    ({ options }) => {
      render(<ModelDropdown options={options} />);

      expect(screen.getByRole("combobox")).toHaveTextContent(CUSTOM_MODEL);
    },
  );

  it("should keep a saved custom model when opening the picker", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    render(<ModelDropdown onSelect={onSelect} />);

    await user.click(screen.getByRole("combobox"));

    expect(onSelect).not.toHaveBeenCalled();
    expect(
      within(screen.getByRole("list", { name: "Model IDs" })).getByText(
        CUSTOM_MODEL,
      ),
    ).toBeInTheDocument();
  });

  it("should keep the selection while searching for another model", async () => {
    const user = userEvent.setup();
    const onSelect = jest.fn();
    render(<ModelDropdown onSelect={onSelect} />);

    await user.click(screen.getByRole("combobox"));
    const search = screen.getByRole("textbox", { name: "Search options..." });
    await user.type(search, "global.anthropic.claude-opus-5-5");
    await user.clear(search);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("combobox"));

    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("combobox")).toHaveTextContent(CUSTOM_MODEL);
    expect(
      within(screen.getByRole("list", { name: "Model IDs" })).getByText(
        CUSTOM_MODEL,
      ),
    ).toBeInTheDocument();
  });

  it("should preserve a custom selection when the options refresh", () => {
    const onSelect = jest.fn();
    const { rerender } = render(<ModelDropdown onSelect={onSelect} />);

    rerender(
      <ModelDropdown
        value="global.anthropic.claude-opus-5-5"
        options={[...OPTIONS, "another-model"]}
        onSelect={onSelect}
      />,
    );

    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole("combobox")).toHaveTextContent(
      "global.anthropic.claude-opus-5-5",
    );
  });

  it("should keep the placeholder when the selection is empty", () => {
    render(<ModelDropdown value="" />);

    expect(screen.getByRole("combobox")).toHaveTextContent("Select an option");
  });

  it("should still clear an unavailable value in a fixed dropdown", () => {
    const onSelect = jest.fn();
    render(<ModelDropdown combobox={false} onSelect={onSelect} />);

    expect(onSelect).toHaveBeenCalledWith("", undefined, true);
    expect(screen.getByRole("combobox")).toHaveTextContent("Select an option");
  });
});
