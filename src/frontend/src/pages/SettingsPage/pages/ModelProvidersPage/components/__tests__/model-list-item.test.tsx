import { render, screen, fireEvent } from "@testing-library/react";
import ModelListItem from "../model-list-item";
import { Model, DefaultModelData } from "../types";

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

jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: ({ checked, onCheckedChange, ...props }: any) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      data-testid="checkbox"
      {...props}
    />
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => {
  return function MockShadTooltip({ children, content }: any) {
    return <div title={content}>{children}</div>;
  };
});

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("ModelListItem", () => {
  const mockModel: Model = {
    model_name: "gpt-4",
    metadata: {
      model_type: "llm",
      preview: false,
      reasoning: false,
      tool_calling: false,
    },
  };

  const defaultProps = {
    model: mockModel,
    providerName: "OpenAI",
    type: "enabled" as const,
    isModelEnabled: true,
    defaultModelData: undefined,
    onToggleModel: jest.fn(),
    onSetDefaultModel: jest.fn(),
    onClearDefaultModel: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", () => {
    render(<ModelListItem {...defaultProps} />);
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  it("renders model name", () => {
    render(<ModelListItem {...defaultProps} />);
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  it("renders checkbox for enabled type", () => {
    render(<ModelListItem {...defaultProps} />);
    expect(screen.getByTestId("checkbox")).toBeInTheDocument();
  });

  it("does not render checkbox for available type", () => {
    const props = {
      ...defaultProps,
      type: "available" as const,
    };
    render(<ModelListItem {...props} />);
    expect(screen.queryByTestId("checkbox")).not.toBeInTheDocument();
  });

  it("checkbox is checked when model is enabled", () => {
    render(<ModelListItem {...defaultProps} />);
    const checkbox = screen.getByTestId("checkbox") as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it("calls onToggleModel when checkbox is clicked", () => {
    render(<ModelListItem {...defaultProps} />);
    const checkbox = screen.getByTestId("checkbox");
    fireEvent.click(checkbox);
    expect(defaultProps.onToggleModel).toHaveBeenCalled();
  });

  it("renders default button when model is enabled", () => {
    render(<ModelListItem {...defaultProps} />);
    expect(screen.getByTestId("default-gpt-4")).toBeInTheDocument();
  });

  it("does not render default button when model is not enabled", () => {
    const props = {
      ...defaultProps,
      isModelEnabled: false,
    };
    render(<ModelListItem {...props} />);
    expect(screen.queryByTestId("default-gpt-4")).not.toBeInTheDocument();
  });

  it("shows Sparkle icon for language models", () => {
    render(<ModelListItem {...defaultProps} />);
    expect(screen.getByTestId("icon-Sparkle")).toBeInTheDocument();
  });

  it("shows Zap icon for embedding models", () => {
    const props = {
      ...defaultProps,
      model: {
        ...mockModel,
        metadata: { ...mockModel.metadata, model_type: "embedding" },
      },
    };
    render(<ModelListItem {...props} />);
    expect(screen.getByTestId("icon-Zap")).toBeInTheDocument();
  });

  it("calls onSetDefaultModel when clicking default button for non-default model", () => {
    render(<ModelListItem {...defaultProps} />);
    const defaultButton = screen.getByTestId("default-gpt-4");
    fireEvent.click(defaultButton);
    expect(defaultProps.onSetDefaultModel).toHaveBeenCalledWith(
      "OpenAI",
      "gpt-4",
      "language",
    );
  });

  it("calls onClearDefaultModel when clicking default button for default model", () => {
    const defaultModelData: DefaultModelData = {
      default_model: {
        model_name: "gpt-4",
        provider: "OpenAI",
        model_type: "language",
      },
    };
    const props = {
      ...defaultProps,
      defaultModelData,
    };
    render(<ModelListItem {...props} />);
    const defaultButton = screen.getByTestId("default-gpt-4");
    fireEvent.click(defaultButton);
    expect(defaultProps.onClearDefaultModel).toHaveBeenCalledWith("language");
  });

  it("renders reasoning icon when model has reasoning capability", () => {
    const props = {
      ...defaultProps,
      model: {
        ...mockModel,
        metadata: { ...mockModel.metadata, reasoning: true },
      },
    };
    render(<ModelListItem {...props} />);
    expect(screen.getByTestId("icon-Brain")).toBeInTheDocument();
  });

  it("renders tool calling icon when model has tool calling capability", () => {
    const props = {
      ...defaultProps,
      model: {
        ...mockModel,
        metadata: { ...mockModel.metadata, tool_calling: true },
      },
    };
    render(<ModelListItem {...props} />);
    expect(screen.getByTestId("icon-Hammer")).toBeInTheDocument();
  });

  it("renders preview icon when model is in preview", () => {
    const props = {
      ...defaultProps,
      model: {
        ...mockModel,
        metadata: { ...mockModel.metadata, preview: true },
      },
    };
    render(<ModelListItem {...props} />);
    expect(screen.getByTestId("icon-Eye")).toBeInTheDocument();
  });

  it("renders embedding icon for embedding models", () => {
    const props = {
      ...defaultProps,
      model: {
        ...mockModel,
        metadata: { ...mockModel.metadata, model_type: "embedding" },
      },
    };
    render(<ModelListItem {...props} />);
    expect(screen.getByTestId("icon-Layers")).toBeInTheDocument();
  });
});
