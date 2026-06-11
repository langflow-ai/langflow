import { fireEvent, render, screen } from "@testing-library/react";
import { MemoriesSidebar } from "../MemoriesSidebar";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

describe("MemoriesSidebar", () => {
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  const makeProps = (overrides: Partial<any> = {}) =>
    ({
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
      ...overrides,
      // biome-ignore lint/suspicious/noExplicitAny: legacy
    }) as any;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders memory item", () => {
    const props = makeProps();
    render(<MemoriesSidebar {...props} />);
    expect(screen.getByText("Memory One")).toBeInTheDocument();
  });

  it("calls onSelectMemory when memory item is clicked", () => {
    const props = makeProps();
    render(<MemoriesSidebar {...props} />);
    fireEvent.click(screen.getByText("Memory One"));
    expect(props.onSelectMemory).toHaveBeenCalledWith("m1");
  });

  it("opens create action", () => {
    const props = makeProps();
    render(<MemoriesSidebar {...props} />);
    fireEvent.click(screen.getByText("Create"));
    expect(props.onCreateMemory).toHaveBeenCalled();
  });
});
