import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import useFlowHistoryRepairStore, {
  type FlowHistoryProblem,
} from "@/stores/flowHistoryRepairStore";
import FlowHistoryRepairDialog from "..";

const openWith = (problem: Partial<FlowHistoryProblem> = {}) => {
  const repair = jest.fn().mockResolvedValue(undefined);
  act(() => {
    useFlowHistoryRepairStore.getState().setProblem({
      code: "FLOW_REVISION_MISMATCH",
      repair,
      ...problem,
    });
  });
  return repair;
};

describe("FlowHistoryRepairDialog", () => {
  afterEach(() => {
    act(() => useFlowHistoryRepairStore.getState().setProblem(null));
  });

  it("shows nothing without a problem", () => {
    render(<FlowHistoryRepairDialog />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("names the problem and keeps focus inside the dialog", async () => {
    const user = userEvent.setup();
    render(<FlowHistoryRepairDialog />);
    openWith({
      code: "FLOW_GRAPH_INVALID",
      graph: "stored",
      violations: ["EDGE_MISSING_NODE"],
    });

    const dialog = await screen.findByRole("dialog", {
      name: "This flow has problems Langflow can fix",
    });
    expect(dialog).toHaveAccessibleDescription(
      expect.stringContaining("The original is kept as a version"),
    );
    await waitFor(() =>
      expect(dialog).toContainElement(document.activeElement as HTMLElement),
    );
    // Tabbing past the last button comes back into the dialog.
    for (let step = 0; step < 4; step++) {
      await user.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
  });

  it("closes on Escape like Cancel", async () => {
    const user = userEvent.setup();
    render(<FlowHistoryRepairDialog />);
    const repair = openWith();
    await screen.findByRole("dialog");

    await user.keyboard("{Escape}");

    expect(useFlowHistoryRepairStore.getState().problem).toBeNull();
    expect(repair).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("closes on the close button like Cancel", async () => {
    const user = userEvent.setup();
    render(<FlowHistoryRepairDialog />);
    const repair = openWith();
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: "Close" }));

    expect(useFlowHistoryRepairStore.getState().problem).toBeNull();
    expect(repair).not.toHaveBeenCalled();
  });

  it("closes on Cancel", async () => {
    const user = userEvent.setup();
    render(<FlowHistoryRepairDialog />);
    openWith();
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(useFlowHistoryRepairStore.getState().problem).toBeNull();
  });

  it("repairs, then closes", async () => {
    const user = userEvent.setup();
    render(<FlowHistoryRepairDialog />);
    const repair = openWith();
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /repair and save/i }));

    expect(repair).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(useFlowHistoryRepairStore.getState().problem).toBeNull(),
    );
  });

  it("stays open on Escape while a repair runs, as Cancel is disabled", async () => {
    const user = userEvent.setup();
    let finish: () => void = () => {};
    render(<FlowHistoryRepairDialog />);
    openWith({
      repair: () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    });
    await screen.findByRole("dialog");

    await user.click(screen.getByRole("button", { name: /repair and save/i }));
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.keyboard("{Escape}");

    expect(useFlowHistoryRepairStore.getState().problem).not.toBeNull();
    await act(async () => finish());
    await waitFor(() =>
      expect(useFlowHistoryRepairStore.getState().problem).toBeNull(),
    );
  });
});
