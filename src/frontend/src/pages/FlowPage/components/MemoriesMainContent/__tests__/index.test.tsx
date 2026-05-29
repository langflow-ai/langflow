import { fireEvent, render, screen } from "@testing-library/react";
import MemoriesMainContent from "../index";

const mockSetCreateModalOpen = jest.fn();
const mockSetDocumentPanelOpen = jest.fn();
const mockSetSelectedDocument = jest.fn();

const mockFlowState = {
  currentFlowId: "flow-1",
  currentFlow: { name: "Flow One" },
};

// biome-ignore lint/suspicious/noExplicitAny: legacy
let mockedHookValue: any;

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
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
  MemoriesSidebar: ({
    onCreateMemory,
    onSelectMemory,
    selectedMemoryId,
    // biome-ignore lint/suspicious/noExplicitAny: legacy
  }: any) => (
    <div>
      <button onClick={onCreateMemory}>open-create</button>
      <button onClick={() => onSelectMemory?.("m1")}>select-memory</button>
      <div>selected:{selectedMemoryId ?? ""}</div>
    </div>
  ),
}));

const capturedMemoryDetailsProps: Record<string, unknown> = {};
jest.mock("../components/MemoryDetails", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  MemoryDetails: (props: any) => {
    Object.assign(capturedMemoryDetailsProps, props);
    return <div>MemoryDetails</div>;
  },
}));

jest.mock("../components/MemoryDocumentPanel", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  MemoryDocumentPanel: ({ onOpenChange }: any) => (
    <button onClick={() => onOpenChange(false)}>close-panel</button>
  ),
}));

jest.mock("@/modals/createMemoryModal", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  default: ({ onSuccess }: any) => (
    <button onClick={() => onSuccess("m-created")}>create-success</button>
  ),
}));

describe("MemoriesMainContent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(capturedMemoryDetailsProps).forEach(
      (k) => delete capturedMemoryDetailsProps[k],
    );
    mockedHookValue = {
      memories: [],
      filteredMemories: [],
      memoriesSearch: "",
      setMemoriesSearch: jest.fn(),
      memory: null,
      isLoading: false,
      docsData: { total: 0, sessions: [], documents: [] },
      docsLoading: false,
      selectedSession: null,
      setSelectedSession: jest.fn(),
      groupedBySession: new Map(),
      documentPanelOpen: true,
      setDocumentPanelOpen: mockSetDocumentPanelOpen,
      selectedDocument: { message_id: "m1" },
      setSelectedDocument: mockSetSelectedDocument,
      handleOpenDocumentPanel: jest.fn(),
      deleteMutation: { mutate: jest.fn(), isPending: false },
      updateMemoryMutation: { isPending: false },
      handleToggleActive: jest.fn(),
      onRefresh: jest.fn(),
      fetchNextSessionsPage: jest.fn(),
      hasNextSessionsPage: false,
      isFetchingNextSessionsPage: false,
      createModalOpen: false,
      setCreateModalOpen: mockSetCreateModalOpen,
      fetchNextMessagesPage: jest.fn(),
      hasNextMessagesPage: false,
      isFetchingNextMessagesPage: false,
    };
  });

  it("renders empty state when no memory is selected", () => {
    render(<MemoriesMainContent />);
    expect(screen.getByText("NoMemorySelected")).toBeInTheDocument();
  });

  it("renders loading state for selected memory", () => {
    mockedHookValue.isLoading = true;

    render(<MemoriesMainContent />);
    fireEvent.click(screen.getByText("select-memory"));
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders memory details when selected memory exists", () => {
    mockedHookValue.memory = { id: "m1" };

    render(<MemoriesMainContent />);
    fireEvent.click(screen.getByText("select-memory"));
    expect(screen.getByText("MemoryDetails")).toBeInTheDocument();
  });

  it("opens create modal via sidebar action", () => {
    render(<MemoriesMainContent />);

    fireEvent.click(screen.getByText("open-create"));
    expect(mockSetCreateModalOpen).toHaveBeenCalledWith(true);
  });

  it("clears selected document when panel closes", () => {
    render(<MemoriesMainContent />);

    fireEvent.click(screen.getByText("close-panel"));
    expect(mockSetDocumentPanelOpen).toHaveBeenCalledWith(false);
    expect(mockSetSelectedDocument).toHaveBeenCalledWith(null);
  });

  it("selects created memory after create success", () => {
    render(<MemoriesMainContent />);

    fireEvent.click(screen.getByText("create-success"));
    expect(screen.getByText("selected:m-created")).toBeInTheDocument();
  });

  it("passes onRefresh, fetchNextSessionsPage and session pagination flags to MemoryDetails", () => {
    const onRefresh = jest.fn();
    const fetchNextSessionsPage = jest.fn();
    mockedHookValue.memory = { id: "m1" };
    mockedHookValue.onRefresh = onRefresh;
    mockedHookValue.fetchNextSessionsPage = fetchNextSessionsPage;
    mockedHookValue.hasNextSessionsPage = true;
    mockedHookValue.isFetchingNextSessionsPage = true;

    render(<MemoriesMainContent />);
    fireEvent.click(screen.getByText("select-memory"));

    expect(capturedMemoryDetailsProps.onRefresh).toBe(onRefresh);
    expect(capturedMemoryDetailsProps.fetchNextSessionsPage).toBe(
      fetchNextSessionsPage,
    );
    expect(capturedMemoryDetailsProps.hasNextSessionsPage).toBe(true);
    expect(capturedMemoryDetailsProps.isFetchingNextSessionsPage).toBe(true);
  });
});
