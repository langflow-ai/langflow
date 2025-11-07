import { render, screen, fireEvent } from "@testing-library/react";
import ProviderListItem from "../provider-list-item";
import { Provider } from "../types";

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, ...props }: any) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: any) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: any) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: any) => (
    <div onClick={onClick}>{children}</div>
  ),
}));

jest.mock("@/modals/deleteConfirmationModal", () => {
  return function MockDeleteConfirmationModal({ open }: any) {
    return open ? <div data-testid="delete-confirmation-modal">Delete Modal</div> : null;
  };
});

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("ProviderListItem", () => {
  const mockProvider: Provider = {
    provider: "OpenAI",
    icon: "Bot",
    is_enabled: true,
    model_count: 5,
    models: [],
  };

  const defaultProps = {
    provider: mockProvider,
    type: "enabled" as const,
    defaultModelName: null,
    defaultEmbeddingModelName: null,
    onCardClick: jest.fn(),
    onEnableProvider: jest.fn(),
    onDeleteProvider: jest.fn(),
    deleteDialogOpen: false,
    setDeleteDialogOpen: jest.fn(),
    providerToDelete: null,
    setProviderToDelete: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", () => {
    render(<ProviderListItem {...defaultProps} />);
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("renders provider name", () => {
    render(<ProviderListItem {...defaultProps} />);
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("renders provider icon", () => {
    render(<ProviderListItem {...defaultProps} />);
    expect(screen.getByTestId("icon-Bot")).toBeInTheDocument();
  });

  it("renders model count with singular form", () => {
    const props = {
      ...defaultProps,
      provider: { ...mockProvider, model_count: 1 },
    };
    render(<ProviderListItem {...props} />);
    expect(screen.getByText("1 model")).toBeInTheDocument();
  });

  it("renders model count with plural form", () => {
    render(<ProviderListItem {...defaultProps} />);
    expect(screen.getByText("5 models")).toBeInTheDocument();
  });

  it("calls onCardClick when clicked", () => {
    render(<ProviderListItem {...defaultProps} />);
    const card = screen.getByText("OpenAI").closest("div");
    fireEvent.click(card!);
    expect(defaultProps.onCardClick).toHaveBeenCalledWith(mockProvider);
  });

  it("renders default model name when provided", () => {
    const props = {
      ...defaultProps,
      defaultModelName: "gpt-4",
    };
    render(<ProviderListItem {...props} />);
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Sparkle")).toBeInTheDocument();
  });

  it("renders default embedding model name when provided", () => {
    const props = {
      ...defaultProps,
      defaultEmbeddingModelName: "text-embedding-3",
    };
    render(<ProviderListItem {...props} />);
    expect(screen.getByText("text-embedding-3")).toBeInTheDocument();
    expect(screen.getByTestId("icon-Zap")).toBeInTheDocument();
  });

  it("renders dropdown menu for enabled providers", () => {
    render(<ProviderListItem {...defaultProps} />);
    expect(screen.getByTestId("icon-MoreVertical")).toBeInTheDocument();
  });

  it("renders plus button for available providers", () => {
    const props = {
      ...defaultProps,
      type: "available" as const,
      provider: { ...mockProvider, is_enabled: false },
    };
    render(<ProviderListItem {...props} />);
    expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
  });

  it("shows delete confirmation modal when deleteDialogOpen is true", () => {
    const props = {
      ...defaultProps,
      deleteDialogOpen: true,
      providerToDelete: "OpenAI",
    };
    render(<ProviderListItem {...props} />);
    expect(screen.getByTestId("delete-confirmation-modal")).toBeInTheDocument();
  });

  it("does not show delete modal for different provider", () => {
    const props = {
      ...defaultProps,
      deleteDialogOpen: true,
      providerToDelete: "Anthropic",
    };
    render(<ProviderListItem {...props} />);
    expect(screen.queryByTestId("delete-confirmation-modal")).not.toBeInTheDocument();
  });

  it("applies correct cursor style when provider has models", () => {
    const { container } = render(<ProviderListItem {...defaultProps} />);
    const card = container.querySelector(".cursor-pointer");
    expect(card).toBeInTheDocument();
  });

  it("applies disabled style when provider has no models", () => {
    const props = {
      ...defaultProps,
      provider: { ...mockProvider, model_count: 0 },
    };
    const { container } = render(<ProviderListItem {...props} />);
    const card = container.querySelector(".cursor-not-allowed");
    expect(card).toBeInTheDocument();
  });
});
