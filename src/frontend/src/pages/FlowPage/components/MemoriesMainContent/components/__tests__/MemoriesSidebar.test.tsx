import { fireEvent, render, screen } from "@testing-library/react";
import { MemoriesSidebar } from "../MemoriesSidebar";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

describe("MemoriesSidebar", () => {
  const baseProps = {
    memories: [
      { id: "m1", name: "Memory One", status: "idle", is_active: true },
    ],
    filteredMemories: [
      { id: "m1", name: "Memory One", status: "idle", is_active: true },
    ],
    memoriesSearch: "",
    setMemoriesSearch: jest.fn(),
    selectedMemoryId: "m1",
    currentFlowId: "flow-1",
    onSelectMemory: jest.fn(),
    onCreateMemory: jest.fn(),
  } as any;

  it("renders memory and status", () => {
    render(<MemoriesSidebar {...baseProps} />);
    expect(screen.getByText("Memory One")).toBeInTheDocument();
    expect(screen.getByText("idle")).toBeInTheDocument();
  });

  it("calls onSelectMemory when memory item is clicked", () => {
    render(<MemoriesSidebar {...baseProps} />);
    fireEvent.click(screen.getByText("Memory One"));
    expect(baseProps.onSelectMemory).toHaveBeenCalledWith("m1");
  });

  it("opens create action", () => {
    render(<MemoriesSidebar {...baseProps} />);
    fireEvent.click(screen.getByText("Create"));
    expect(baseProps.onCreateMemory).toHaveBeenCalled();
  });
});
