import { render, screen, fireEvent } from "@testing-library/react";
import ProviderModelsDialog from "../provider-models-dialog";
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

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: any) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }: any) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogHeader: ({ children }: any) => (
    <div data-testid="dialog-header">{children}</div>
  ),
  DialogTitle: ({ children }: any) => (
    <div data-testid="dialog-title">{children}</div>
  ),
  DialogDescription: ({ children }: any) => (
    <div data-testid="dialog-description">{children}</div>
  ),
  DialogFooter: ({ children }: any) => (
    <div data-testid="dialog-footer">{children}</div>
  ),
}));

jest.mock("../model-list-item", () => {
  return function MockModelListItem({ model }: any) {
    return (
      <div data-testid={`model-item-${model.model_name}`}>
        {model.model_name}
      </div>
    );
  };
});

describe("ProviderModelsDialog", () => {
  const mockProvider: Provider = {
    provider: "OpenAI",
    icon: "Bot",
    is_enabled: true,
    model_count: 2,
    models: [
      {
        model_name: "gpt-4",
        metadata: { model_type: "llm" },
      },
      {
        model_name: "gpt-3.5-turbo",
        metadata: { model_type: "llm" },
      },
    ],
  };

  const defaultProps = {
    open: false,
    onOpenChange: jest.fn(),
    provider: mockProvider,
    type: "enabled" as const,
    enabledModelsData: undefined,
    defaultModelData: undefined,
    defaultEmbeddingModelData: undefined,
    onBatchToggleModels: jest.fn(),
    onSetDefaultModel: jest.fn(),
    onClearDefaultModel: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("does not render when open is false", () => {
    render(<ProviderModelsDialog {...defaultProps} />);
    expect(screen.queryByTestId("dialog-content")).not.toBeInTheDocument();
  });

  it("renders when open is true", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByTestId("dialog-content")).toBeInTheDocument();
  });

  it("does not render when provider is null", () => {
    const props = { ...defaultProps, open: true, provider: null };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.queryByTestId("dialog-content")).not.toBeInTheDocument();
  });

  it("renders provider name in title", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("renders provider icon", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByTestId("icon-Bot")).toBeInTheDocument();
  });

  it("renders all models in the list", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByTestId("model-item-gpt-4")).toBeInTheDocument();
    expect(screen.getByTestId("model-item-gpt-3.5-turbo")).toBeInTheDocument();
  });

  it("renders no models message when provider has no models", () => {
    const props = {
      ...defaultProps,
      open: true,
      provider: { ...mockProvider, models: [] },
    };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByText("No models available")).toBeInTheDocument();
  });

  it("renders close button", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByText("Close")).toBeInTheDocument();
  });

  it("calls onOpenChange when close button is clicked", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    const closeButton = screen.getByText("Close");
    fireEvent.click(closeButton);
    expect(props.onOpenChange).toHaveBeenCalledWith(false);
  });

  it("renders enabled description for enabled type", () => {
    const props = { ...defaultProps, open: true, type: "enabled" as const };
    render(<ProviderModelsDialog {...props} />);
    expect(
      screen.getByText(/Configure model availability for this provider/i),
    ).toBeInTheDocument();
  });

  it("renders available description for available type", () => {
    const props = { ...defaultProps, open: true, type: "available" as const };
    render(<ProviderModelsDialog {...props} />);
    expect(
      screen.getByText(/These models are available for use with/i),
    ).toBeInTheDocument();
  });

  it("displays default LLM model name", () => {
    const props = {
      ...defaultProps,
      open: true,
      defaultModelData: {
        default_model: {
          model_name: "gpt-4-custom",
          provider: "OpenAI",
          model_type: "language",
        },
      },
    };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByText("gpt-4-custom")).toBeInTheDocument();
  });

  it("displays None when no default LLM model is set", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    const allNone = screen.getAllByText("None");
    expect(allNone.length).toBeGreaterThan(0);
  });

  it("displays default embedding model name", () => {
    const props = {
      ...defaultProps,
      open: true,
      defaultEmbeddingModelData: {
        default_model: {
          model_name: "text-embedding-3",
          provider: "OpenAI",
          model_type: "embedding",
        },
      },
    };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByText("text-embedding-3")).toBeInTheDocument();
  });

  it("renders dialog header", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByTestId("dialog-header")).toBeInTheDocument();
  });

  it("renders dialog footer", () => {
    const props = { ...defaultProps, open: true };
    render(<ProviderModelsDialog {...props} />);
    expect(screen.getByTestId("dialog-footer")).toBeInTheDocument();
  });
});
