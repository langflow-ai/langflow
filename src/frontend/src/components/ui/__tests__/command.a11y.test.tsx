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

  // FINDING (documented, not fixed): cmdk always stamps its own
  // `aria-labelledby` (pointing at the `<Command label>` element) onto the
  // input, and aria-labelledby outranks aria-label in the accessible-name
  // computation. A caller passing `aria-label` to CommandInput therefore has
  // it silently ignored whenever the wrapping `<Command>` sets `label`. The
  // input is still named — just not with the name the call site asked for.
  it("should_name_the_input_from_the_command_label_not_the_input_aria_label", () => {
    renderInlineCommand();

    const input = screen.getByRole("combobox");
    expect(input).toHaveAttribute("aria-label", "Search components");
    expect(input).toHaveAccessibleName("Component search");
  });

  // FINDING (documented, not fixed): the corollary of the above. When the
  // wrapping `<Command>` has no `label`, cmdk's `aria-labelledby` resolves to
  // an empty element, and because it still outranks `aria-label` the search
  // box ends up with NO accessible name at all. In other words `<Command
  // label>` is the only way to name a CommandInput — passing `aria-label` to
  // the input is a no-op. Every call site that relies on `aria-label` alone
  // ships an unnamed combobox (WCAG 4.1.2).
  it("should_leave_the_input_unnamed_when_the_command_has_no_label", () => {
    render(
      <Command>
        <CommandInput aria-label="Search components" />
        <CommandList>
          <CommandItem>Chat Input</CommandItem>
        </CommandList>
      </Command>,
    );

    const input = screen.getByRole("combobox");
    expect(input).toHaveAttribute("aria-label", "Search components");
    expect(input).toHaveAccessibleName("");
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
      <CommandDialog open>
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

  // FINDING (documented, not fixed): CommandDialog passes no DialogTitle, so
  // DialogContent injects its visually-hidden "Dialog" fallback and the
  // command palette announces as literally "Dialog". Asserting the current
  // behaviour means a future real title trips this test instead of silently
  // passing, at which point the expectation should be updated.
  it("should_expose_the_command_dialog_with_its_current_fallback_name", () => {
    render(
      <CommandDialog open>
        <CommandInput aria-label="Search components" />
        <CommandList>
          <CommandItem>Chat Input</CommandItem>
        </CommandList>
      </CommandDialog>,
    );

    expect(screen.getByRole("dialog", { name: "Dialog" })).toBeInTheDocument();
  });

  // FINDING (documented, not fixed): CommandSeparator renders
  // `role="separator"` as a direct child of CommandList's `role="listbox"`.
  // A listbox may only own `option` / `group` children, so axe reports
  // `aria-required-children`. Fixing it belongs in command.tsx (the separator
  // needs `role="presentation"`), so this test pins the current behaviour.
  it("should_report_a_separator_inside_the_listbox_as_a_disallowed_child", async () => {
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

    const results = await axe(container, {
      rules: { region: { enabled: false } },
    });
    const violationIds = results.violations.map((violation) => violation.id);
    expect(violationIds).toContain("aria-required-children");
  });
});
