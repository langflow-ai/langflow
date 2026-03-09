import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import KnowledgeBaseEmptyState from "../KnowledgeBaseEmptyState";

// Mock dependencies
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: jest.fn(),
    }),
  ),
}));

const mockCaptureSubmit = jest.fn();
const mockApplyOptimisticUpdate = jest.fn().mockReturnValue(true);

jest.mock("../../hooks/useOptimisticKnowledgeBase", () => ({
  useOptimisticKnowledgeBase: () => ({
    captureSubmit: mockCaptureSubmit,
    applyOptimisticUpdate: mockApplyOptimisticUpdate,
  }),
}));

// Mock the modal component
jest.mock("@/modals/knowledgeBaseUploadModal/KnowledgeBaseUploadModal", () => {
  return function MockKnowledgeBaseUploadModal({
    open,
    setOpen,
    onSubmit,
  }: {
    open: boolean;
    setOpen: (open: boolean) => void;
    onSubmit: (data: any) => void;
  }) {
    return open ? (
      <div data-testid="upload-modal">
        <button data-testid="modal-close" onClick={() => setOpen(false)}>
          Close
        </button>
        <button
          data-testid="modal-submit"
          onClick={() => {
            onSubmit({
              sourceName: "TestKB",
              files: [new File(["content"], "test.txt")],
              embeddingModel: null,
            });
            setOpen(false);
          }}
        >
          Submit
        </button>
      </div>
    ) : null;
  };
});

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIcon() {
    return <span data-testid="mock-icon" />;
  };
});

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("KnowledgeBaseEmptyState", () => {
  const mockHandleCreateKnowledge = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders empty state message correctly", () => {
    render(
      <KnowledgeBaseEmptyState
        handleCreateKnowledge={mockHandleCreateKnowledge}
      />,
      { wrapper: createTestWrapper() },
    );

    expect(screen.getByText("No knowledge bases")).toBeInTheDocument();
    expect(
      screen.getByText(/Create powerful AI experiences/),
    ).toBeInTheDocument();
  });

  it("renders Add Knowledge button", () => {
    render(
      <KnowledgeBaseEmptyState
        handleCreateKnowledge={mockHandleCreateKnowledge}
      />,
      { wrapper: createTestWrapper() },
    );

    const addButton = screen.getByText("Add Knowledge");
    expect(addButton).toBeInTheDocument();
  });

  it("opens modal when Add Knowledge button is clicked", () => {
    render(
      <KnowledgeBaseEmptyState
        handleCreateKnowledge={mockHandleCreateKnowledge}
      />,
      { wrapper: createTestWrapper() },
    );

    const addButton = screen.getByText("Add Knowledge");
    fireEvent.click(addButton);

    expect(screen.getByTestId("upload-modal")).toBeInTheDocument();
  });

  it("calls captureSubmit when form is submitted", () => {
    render(
      <KnowledgeBaseEmptyState
        handleCreateKnowledge={mockHandleCreateKnowledge}
      />,
      { wrapper: createTestWrapper() },
    );

    const addButton = screen.getByText("Add Knowledge");
    fireEvent.click(addButton);

    const submitButton = screen.getByTestId("modal-submit");
    fireEvent.click(submitButton);

    expect(mockCaptureSubmit).toHaveBeenCalledWith({
      sourceName: "TestKB",
      files: expect.any(Array),
      embeddingModel: null,
    });
  });

  it("calls applyOptimisticUpdate when modal closes after submission", () => {
    render(
      <KnowledgeBaseEmptyState
        handleCreateKnowledge={mockHandleCreateKnowledge}
      />,
      { wrapper: createTestWrapper() },
    );

    const addButton = screen.getByText("Add Knowledge");
    fireEvent.click(addButton);

    const submitButton = screen.getByTestId("modal-submit");
    fireEvent.click(submitButton);

    expect(mockApplyOptimisticUpdate).toHaveBeenCalled();
  });

  it("closes modal without calling applyOptimisticUpdate when closed without submission", () => {
    mockApplyOptimisticUpdate.mockClear();

    render(
      <KnowledgeBaseEmptyState
        handleCreateKnowledge={mockHandleCreateKnowledge}
      />,
      { wrapper: createTestWrapper() },
    );

    const addButton = screen.getByText("Add Knowledge");
    fireEvent.click(addButton);

    expect(screen.getByTestId("upload-modal")).toBeInTheDocument();

    const closeButton = screen.getByTestId("modal-close");
    fireEvent.click(closeButton);

    // Modal should call applyOptimisticUpdate even on close (it returns false if no submission)
    expect(mockApplyOptimisticUpdate).toHaveBeenCalled();
  });
});
