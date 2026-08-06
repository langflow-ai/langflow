import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "../command";

// cmdk scrolls the highlighted row into view on every selection change, and
// jsdom does not implement scrollIntoView.
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
});

const renderInlineCommand = () =>
  render(
    <Command label="Component search">
      <CommandInput aria-label="Search components" placeholder="Search…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Inputs">
          <CommandItem>Chat Input</CommandItem>
          <CommandItem>Text Input</CommandItem>
        </CommandGroup>
        <CommandGroup heading="Outputs">
          <CommandItem>Chat Output</CommandItem>
        </CommandGroup>
      </CommandList>
    </Command>,
  );

const renderInlineCommandWithoutInputLabel = () =>
  render(
    <Command label="Component search">
      <CommandInput placeholder="Search…" />
      <CommandList>
        <CommandGroup heading="Inputs">
          <CommandItem>Chat Input</CommandItem>
        </CommandGroup>
      </CommandList>
    </Command>,
  );

describe("Command accessibility", () => {
  it("should_have_no_axe_violations_when_rendered_inline", async () => {
    const { container } = renderInlineCommand();

    // `region` is a page-level landmark rule that a bare unit render cannot
    // satisfy — the palette is always embedded in a popover or dialog.
    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_expose_listbox_and_option_roles", () => {
    renderInlineCommand();

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Chat Input" }),
    ).toBeInTheDocument();
    // cmdk groups map to ARIA groups, so headings must be exposed as names.
    expect(screen.getByRole("group", { name: "Inputs" })).toBeInTheDocument();
  });

  // cmdk stamps its own `aria-labelledby` (pointing at the `<Command label>`
  // element) onto the input, and aria-labelledby would outrank aria-label in
  // the accessible-name computation. CommandInput drops that reference when a
  // caller passes `aria-label`, so the name the call site asked for wins.
  it("should_name_the_input_from_its_own_aria_label", () => {
    renderInlineCommand();

    const input = screen.getByRole("combobox");
    expect(input).not.toHaveAttribute("aria-labelledby");
    expect(input).toHaveAccessibleName("Search components");
  });

  // Without an `aria-label` the input keeps cmdk's own labelling, so
  // `<Command label>` still names it.
  it("should_fall_back_to_the_command_label_when_the_input_has_no_aria_label", () => {
    renderInlineCommandWithoutInputLabel();

    expect(screen.getByRole("combobox")).toHaveAccessibleName(
      "Component search",
    );
  });

  // Previously the input ended up with no accessible name at all here: cmdk's
  // aria-labelledby pointed at the empty `<Command>` label element and still
  // outranked aria-label (WCAG 4.1.2).
  it("should_name_the_input_when_the_command_has_no_label", () => {
    render(
      <Command>
        <CommandInput aria-label="Search components" />
        <CommandList>
          <CommandItem>Chat Input</CommandItem>
        </CommandList>
      </Command>,
    );

    expect(screen.getByRole("combobox")).toHaveAccessibleName(
      "Search components",
    );
  });

  it("should_expose_combobox_state_on_the_input", () => {
    renderInlineCommand();

    const input = screen.getByRole("combobox");
    expect(input).toHaveAttribute("aria-expanded", "true");
    expect(input).toHaveAttribute("aria-controls");
    expect(input).toHaveAttribute("aria-autocomplete", "list");
  });

  it("should_mark_the_highlighted_row_as_selected", async () => {
    const user = userEvent.setup();
    renderInlineCommand();

    await user.type(screen.getByRole("combobox"), "chat out");

    // WCAG 4.1.2: the visually highlighted row must also be programmatically
    // selected, otherwise screen readers announce nothing as the user filters.
    expect(screen.getByRole("option", { name: "Chat Output" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("should_filter_options_and_announce_the_empty_state", async () => {
    const user = userEvent.setup();
    renderInlineCommand();

    await user.type(screen.getByRole("combobox"), "zzzz");

    expect(screen.getByText("No results found.")).toBeInTheDocument();
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("should_have_no_axe_violations_when_rendered_in_a_dialog", async () => {
    render(
      <CommandDialog open label="Command palette">
        <CommandInput aria-label="Search components" />
        <CommandList>
          <CommandItem>Chat Input</CommandItem>
        </CommandList>
      </CommandDialog>,
    );

    // Radix portals dialog content to document.body, outside the render
    // container.
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  // The palette used to announce as the literal string "Dialog": CommandDialog
  // passed no DialogTitle, so DialogContent injected its visually-hidden
  // fallback. `label` now names both the dialog and the search input.
  it("should_name_the_command_dialog_from_its_label", () => {
    render(
      <CommandDialog open label="Command palette">
        <CommandList>
          <CommandItem>Chat Input</CommandItem>
        </CommandList>
      </CommandDialog>,
    );

    expect(
      screen.getByRole("dialog", { name: "Command palette" }),
    ).toBeInTheDocument();
  });

  // cmdk's own Separator renders `role="separator"` as a direct child of
  // CommandList's `role="listbox"`, which may only own `option` / `group`
  // children (axe aria-required-children). Ours is presentational instead.
  it("should_render_the_separator_as_presentational_inside_the_listbox", async () => {
    const { container } = render(
      <Command label="Component search">
        <CommandInput aria-label="Search components" />
        <CommandList>
          <CommandGroup heading="Inputs">
            <CommandItem>Chat Input</CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Outputs">
            <CommandItem>Chat Output</CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>,
    );

    expect(screen.queryByRole("separator")).not.toBeInTheDocument();
    expect(
      await axe(container, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_hide_the_separator_while_a_search_is_active", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <Command label="Component search">
        <CommandInput aria-label="Search components" />
        <CommandList>
          <CommandGroup heading="Inputs">
            <CommandItem>Chat Input</CommandItem>
          </CommandGroup>
          <CommandSeparator />
        </CommandList>
      </Command>,
    );

    expect(container.querySelector("[cmdk-separator]")).toBeInTheDocument();

    await user.type(screen.getByRole("combobox"), "chat");

    expect(container.querySelector("[cmdk-separator]")).not.toBeInTheDocument();
  });
});
