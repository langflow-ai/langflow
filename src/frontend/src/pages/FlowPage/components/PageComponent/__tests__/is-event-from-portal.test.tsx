import { fireEvent, render, screen } from "@testing-library/react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import isEventFromPortal from "../utils/is-event-from-portal";

const NodeWithDialog = ({
  onContextMenu,
}: {
  onContextMenu: (event: React.MouseEvent) => void;
}) => (
  // Mirrors how the canvas wires node handlers: the listener sits on the node
  // element, and the dialog is rendered from inside the node subtree.
  <div data-testid="node" role="group" onContextMenu={onContextMenu}>
    <span data-testid="node-body">Agent</span>
    <Dialog open>
      <DialogContent hideDescription aria-describedby={undefined}>
        <DialogTitle>Model providers</DialogTitle>
        <input data-testid="search-providers" />
      </DialogContent>
    </Dialog>
  </div>
);

describe("isEventFromPortal", () => {
  it("reports events raised inside the handler element as not portaled", () => {
    const results: boolean[] = [];
    render(
      <NodeWithDialog
        onContextMenu={(e) => results.push(isEventFromPortal(e))}
      />,
    );

    fireEvent.contextMenu(screen.getByTestId("node-body"));

    expect(results).toEqual([false]);
  });

  it("reports events raised inside a dialog portal as portaled", () => {
    const results: boolean[] = [];
    render(
      <NodeWithDialog
        onContextMenu={(e) => results.push(isEventFromPortal(e))}
      />,
    );

    fireEvent.contextMenu(screen.getByTestId("search-providers"));

    expect(results).toEqual([true]);
  });

  it("bubbles portal events to node handlers, which is what the guard exists for", () => {
    const onContextMenu = jest.fn();
    render(<NodeWithDialog onContextMenu={onContextMenu} />);

    fireEvent.contextMenu(screen.getByTestId("search-providers"));

    // Documents the React behaviour this guard compensates for: without it, a
    // right-click inside the modal reaches the node behind it.
    expect(onContextMenu).toHaveBeenCalledTimes(1);
  });
});
