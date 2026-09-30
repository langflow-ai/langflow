import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DeleteConfirmationModal from "../index";

describe("DeleteConfirmationModal accessibility", () => {
  it("exposes_destructive_confirmation_copy_and_cancel_path", () => {
    const onConfirm = jest.fn();

    render(
      <DeleteConfirmationModal
        open={true}
        setOpen={jest.fn()}
        onConfirm={onConfirm}
        description="folder"
        note="and all associated flows and components"
        asChild
      >
        <button type="button">Open delete dialog</button>
      </DeleteConfirmationModal>,
    );

    expect(screen.getByRole("dialog", { name: "Delete" })).toBeInTheDocument();
    expect(
      screen.getByText((content) =>
        content.includes(
          "This will permanently delete the folder and all associated flows and components.",
        ),
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes("This can't be undone.")),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("btn_cancel_delete_confirmation_modal"),
    ).toHaveTextContent("Cancel");
    expect(
      screen.getByTestId("btn_delete_delete_confirmation_modal"),
    ).toHaveTextContent("Delete");

    fireEvent.click(screen.getByTestId("btn_cancel_delete_confirmation_modal"));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("keeps_trigger_reachable_by_keyboard_tab", async () => {
    const user = userEvent.setup();

    render(
      <DeleteConfirmationModal
        onConfirm={jest.fn()}
        description="folder"
        asChild
      >
        <button type="button">Open delete dialog</button>
      </DeleteConfirmationModal>,
    );

    const trigger = screen.getByRole("button", {
      name: "Open delete dialog",
    });

    expect(trigger).not.toHaveAttribute("tabindex", "-1");
    expect(trigger).not.toHaveAttribute("aria-controls");

    await user.tab();

    expect(trigger).toHaveFocus();
  });
});
