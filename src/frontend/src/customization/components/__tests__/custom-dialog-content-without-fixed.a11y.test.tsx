import { render, screen } from "@testing-library/react";
import { Dialog, DialogTitle } from "@/components/ui/dialog";
import DialogContentWithouFixed from "../custom-dialog-content-without-fixed";

describe("DialogContentWithouFixed accessibility", () => {
  // Known gap (a11y-action-plan 1.6): the component renders an empty
  // fragment, so modals routed through it (timeout/fetch error dialogs)
  // produce no dialog, no title, and no content at all. Fails until the
  // fix lands.
  it("should_render_dialog_with_accessible_name_and_content", () => {
    render(
      <Dialog open>
        <DialogContentWithouFixed>
          <DialogTitle>Connection lost</DialogTitle>
          <p>Trying to reconnect…</p>
        </DialogContentWithouFixed>
      </Dialog>,
    );

    expect(
      screen.getByRole("dialog", { name: "Connection lost" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Trying to reconnect…")).toBeInTheDocument();
  });
});
