import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import TypeToConfirmDeleteDialog from "../components/type-to-confirm-delete-dialog";

function renderDialog(
  props: React.ComponentProps<typeof TypeToConfirmDeleteDialog>,
) {
  return render(
    <TooltipProvider>
      <TypeToConfirmDeleteDialog {...props} />
    </TooltipProvider>,
  );
}

function rerenderDialog(
  rerender: ReturnType<typeof render>["rerender"],
  props: React.ComponentProps<typeof TypeToConfirmDeleteDialog>,
) {
  return rerender(
    <TooltipProvider>
      <TypeToConfirmDeleteDialog {...props} />
    </TooltipProvider>,
  );
}

const defaultProps = {
  open: true,
  onOpenChange: jest.fn(),
  deploymentName: "My Agent",
  onConfirm: jest.fn(),
};

describe("TypeToConfirmDeleteDialog", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders deployment name in the body", () => {
    renderDialog(defaultProps);

    expect(
      screen.getByText(/Permanently delete the deployment/),
    ).toBeInTheDocument();
    expect(screen.getByRole("code")).toHaveTextContent("My Agent");
  });

  it("Delete button is disabled when input is empty", () => {
    renderDialog(defaultProps);

    const deleteBtn = screen.getByTestId("btn-delete-type-to-confirm-delete");
    expect(deleteBtn).toBeDisabled();
  });

  it("Delete button is disabled when input does not match deployment name", () => {
    renderDialog(defaultProps);

    const input = screen.getByTestId("input-type-to-confirm-delete");
    fireEvent.change(input, { target: { value: "wrong-value" } });

    const deleteBtn = screen.getByTestId("btn-delete-type-to-confirm-delete");
    expect(deleteBtn).toBeDisabled();
  });

  it("Delete button is enabled when input matches deployment name exactly", () => {
    renderDialog(defaultProps);

    const input = screen.getByTestId("input-type-to-confirm-delete");
    fireEvent.change(input, { target: { value: "My Agent" } });

    const deleteBtn = screen.getByTestId("btn-delete-type-to-confirm-delete");
    expect(deleteBtn).toBeEnabled();
  });

  it("calls onConfirm when Delete button is clicked with correct input", () => {
    const onConfirm = jest.fn();
    renderDialog({ ...defaultProps, onConfirm });

    const input = screen.getByTestId("input-type-to-confirm-delete");
    fireEvent.change(input, { target: { value: "My Agent" } });

    const deleteBtn = screen.getByTestId("btn-delete-type-to-confirm-delete");
    fireEvent.click(deleteBtn);

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("Delete button is disabled when input matches deployment name with different casing", () => {
    renderDialog(defaultProps);

    const input = screen.getByTestId("input-type-to-confirm-delete");
    fireEvent.change(input, { target: { value: "my agent" } });

    const deleteBtn = screen.getByTestId("btn-delete-type-to-confirm-delete");
    expect(deleteBtn).toBeDisabled();
  });

  it("input resets to empty when dialog is closed (open becomes false)", () => {
    const { rerender } = renderDialog({ ...defaultProps, open: true });

    const input = screen.getByTestId("input-type-to-confirm-delete");
    fireEvent.change(input, { target: { value: "My Agent" } });
    expect(input).toHaveValue("My Agent");

    rerenderDialog(rerender, { ...defaultProps, open: false });

    // Input should be reset; since dialog is closed, query the component's
    // internal state by reopening it
    rerenderDialog(rerender, { ...defaultProps, open: true });

    const resetInput = screen.getByTestId("input-type-to-confirm-delete");
    expect(resetInput).toHaveValue("");
  });
});
