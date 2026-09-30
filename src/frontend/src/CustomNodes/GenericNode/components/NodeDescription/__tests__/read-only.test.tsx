import { fireEvent, render, screen } from "@testing-library/react";
import NodeDescription from "..";

const mockSetNode = jest.fn();
const mockTakeSnapshot = jest.fn();

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: { setNode: jest.Mock }) => unknown) =>
    selector({ setNode: mockSetNode }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { takeSnapshot: jest.Mock }) => unknown) =>
    selector({ takeSnapshot: mockTakeSnapshot }),
}));

describe("NodeDescription read-only mode", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not enter sticky-note edit mode on double click", () => {
    const setEditNameDescription = jest.fn();
    render(
      <NodeDescription
        nodeId="note-1"
        description="Read-only note"
        editNameDescription={false}
        setEditNameDescription={setEditNameDescription}
        stickyNote
        readOnly
      />,
    );

    fireEvent.doubleClick(screen.getByTestId("generic-node-desc"));

    expect(setEditNameDescription).not.toHaveBeenCalled();
    expect(mockTakeSnapshot).not.toHaveBeenCalled();
    expect(mockSetNode).not.toHaveBeenCalled();
  });

  it("closes an existing editor without rendering a textarea", () => {
    const setEditNameDescription = jest.fn();
    render(
      <NodeDescription
        nodeId="note-1"
        description="Read-only note"
        editNameDescription
        setEditNameDescription={setEditNameDescription}
        stickyNote
        readOnly
      />,
    );

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(setEditNameDescription).toHaveBeenCalledWith(false);
    expect(mockSetNode).not.toHaveBeenCalled();
  });
});
