import { fireEvent, render, screen } from "@testing-library/react";
import MemoriesMainContent from "../index";

const mockSetCreateModalOpen = jest.fn();
const mockSetDocumentPanelOpen = jest.fn();
const mockSetSelectedDocument = jest.fn();

const mockFlowState = {
  currentFlowId: "flow-1",
  currentFlow: { name: "Flow One" },
};

let mockedHookValue: any;

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: any) => unknown) => selector(mockFlowState),
}));

jest.mock("../hooks/useMemoriesData", () => ({
  useMemoriesData: () => mockedHookValue,
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div>Loading...</div>,
}));

jest.mock("../components/NoMemorySelected", () => ({
  NoMemorySelected: () => <div>NoMemorySelected</div>,
}));

jest.mock("../components/MemoriesSidebar", () => ({
  MemoriesSidebar: ({ onCreateMemory }: any) => (
    <button onClick={onCreateMemory}>open-create</button>
  ),
}));

jest.mock("../components/MemoryDetails", () => ({
  MemoryDetails: () => <div>MemoryDetails</div>,
}));

jest.mock("../components/MemoryDocumentPanel", () => ({
  MemoryDocumentPanel: ({ onOpenChange }: any) => (
    <button onClick={() => onOpenChange(false)}>close-panel</button>
  ),
}));

jest.mock("@/modals/createMemoryModal", () => ({
  __esModule: true,
  default: ({ onSuccess }: any) => (
    <button onClick={() => onSuccess("m-created")}>create-success</button>
  ),
}));

describe("MemoriesMainContent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedHookValue = {
      memories: [],
      filteredMemories: [],
      memoriesSearch: "",
      setMemoriesSearch: jest.fn(),
      memory: null,
      isLoading: false,
      docsData: { total: 0, sessions: [], documents: [] },
      docsLoading: false,
      searchQuery: "",
      setSearchQuery: jest.fn(),
      activeSearch: "",
      setActiveSearch: jest.fn(),
      selectedSession: null,
      setSelectedSession: jest.fn(),
      handleSearch: jest.fn(),
      groupedBySession: new Map(),
      documentPanelOpen: true,
      setDocumentPanelOpen: mockSetDocumentPanelOpen,
      selectedDocument: { message_id: "m1" },
      setSelectedDocument: mockSetSelectedDocument,
      handleOpenDocumentPanel: jest.fn(),
      deleteMutation: { mutate: jest.fn(), isPending: false },
      updateMemoryMutation: { isPending: false },
      handleToggleActive: jest.fn(),
      createModalOpen: false,
      setCreateModalOpen: mockSetCreateModalOpen,
    };
  });

  it("renders empty state when no memory is selected", () => {
    render(
      <MemoriesMainContent
        selectedMemoryId={null}
        onSelectMemory={jest.fn()}
      />,
    );
    expect(screen.getByText("NoMemorySelected")).toBeInTheDocument();
  });

  it("renders loading state for selected memory", () => {
    mockedHookValue.isLoading = true;

    render(
      <MemoriesMainContent selectedMemoryId="m1" onSelectMemory={jest.fn()} />,
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders memory details when selected memory exists", () => {
    mockedHookValue.memory = { id: "m1" };

    render(
      <MemoriesMainContent selectedMemoryId="m1" onSelectMemory={jest.fn()} />,
    );
    expect(screen.getByText("MemoryDetails")).toBeInTheDocument();
  });

  it("opens create modal via sidebar action", () => {
    render(
      <MemoriesMainContent selectedMemoryId="m1" onSelectMemory={jest.fn()} />,
    );

    fireEvent.click(screen.getByText("open-create"));
    expect(mockSetCreateModalOpen).toHaveBeenCalledWith(true);
  });

  it("clears selected document when panel closes", () => {
    render(
      <MemoriesMainContent selectedMemoryId="m1" onSelectMemory={jest.fn()} />,
    );

    fireEvent.click(screen.getByText("close-panel"));
    expect(mockSetDocumentPanelOpen).toHaveBeenCalledWith(false);
    expect(mockSetSelectedDocument).toHaveBeenCalledWith(null);
  });

  it("forwards create success to onSelectMemory", () => {
    const onSelectMemory = jest.fn();

    render(
      <MemoriesMainContent
        selectedMemoryId="m1"
        onSelectMemory={onSelectMemory}
      />,
    );

    fireEvent.click(screen.getByText("create-success"));
    expect(onSelectMemory).toHaveBeenCalledWith("m-created");
  });
});
