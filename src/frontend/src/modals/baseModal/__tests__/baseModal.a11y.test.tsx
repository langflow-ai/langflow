import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import BaseModal from "../index";

const renderWithProviders = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("BaseModal full-screen accessibility", () => {
  it("should_render_full_screen_content", () => {
    render(
      <BaseModal open={true} setOpen={() => {}} type="full-screen">
        <BaseModal.Content>
          <p>Playground content</p>
        </BaseModal.Content>
      </BaseModal>,
    );

    expect(screen.getByText("Playground content")).toBeInTheDocument();
  });

  // Known gap (a11y-action-plan 1.5): type="full-screen" renders a plain
  // <div> wrapper with no dialog role, aria-modal, accessible name, or
  // focus trap — used by the playground modal.
  it("should_expose_full_screen_modal_as_dialog", () => {
    render(
      <BaseModal open={true} setOpen={() => {}} type="full-screen">
        <BaseModal.Content>
          <p>Playground content</p>
        </BaseModal.Content>
      </BaseModal>,
    );

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName();
  });
});

describe("BaseModal dialog accessible name", () => {
  it("should_use_header_title_as_dialog_name", () => {
    renderWithProviders(
      <BaseModal open={true} setOpen={() => {}} size="x-small">
        <BaseModal.Header description="Available across your flows.">
          Create Variable
        </BaseModal.Header>
        <BaseModal.Content>
          <p>Form fields</p>
        </BaseModal.Content>
      </BaseModal>,
    );

    expect(
      screen.getByRole("dialog", { name: "Create Variable" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Dialog")).not.toBeInTheDocument();
  });
});
