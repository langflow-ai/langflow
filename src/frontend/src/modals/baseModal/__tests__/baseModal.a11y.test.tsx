import { render, screen } from "@testing-library/react";
import BaseModal from "../index";

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
