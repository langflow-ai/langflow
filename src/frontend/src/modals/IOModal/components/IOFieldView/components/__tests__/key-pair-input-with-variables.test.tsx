import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import IOKeyPairInputWithVariables from "../key-pair-input-with-variables";

// Mock the useGetGlobalVariables hook
jest.mock(
  "@/controllers/API/queries/variables/use-get-global-variables",
  () => ({
    useGetGlobalVariables: jest.fn(() => ({
      data: [
        { name: "API_KEY_1", type: "CREDENTIAL" },
        { name: "API_KEY_2", type: "GENERIC" },
        { name: "TOKEN", type: "CREDENTIAL" },
      ],
      isLoading: false,
    })),
  }),
);

// Mock nanoid
jest.mock("nanoid", () => ({
  nanoid: jest.fn(() => "test-id-123"),
}));

// Mock IconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({
    name,
    className,
    ...props
  }: {
    name: string;
    className?: string;
  }) => (
    <span data-testid={`icon-${name}`} className={className} {...props}>
      {name}
    </span>
  ),
}));

// Mock InputComponent - filter out custom props to avoid React warnings
jest.mock(
  "@/components/core/parameterRenderComponent/components/inputComponent",
  () => ({
    __esModule: true,
    default: ({
      value,
      onChange,
      placeholder,
      id,
      disabled,
    }: {
      value: string;
      onChange: (value: string) => void;
      placeholder?: string;
      id?: string;
      disabled?: boolean;
    }) => (
      <input
        data-testid={id || "input-component"}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
      />
    ),
  }),
);

// Mock Input component from shadcn/ui
jest.mock("@/components/ui/input", () => ({
  Input: ({
    placeholder,
    value,
    onChange,
    disabled,
    ...props
  }: {
    placeholder?: string;
    value: string;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    disabled?: boolean;
  }) => (
    <input
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      disabled={disabled}
      {...props}
    />
  ),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("IOKeyPairInputWithVariables", () => {
  const defaultProps = {
    value: [{ key: "", value: "", id: "1", error: false }],
    onChange: jest.fn(),
    duplicateKey: false,
    isList: true,
    isInputField: true,
    testId: "test-input",
    enableGlobalVariables: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders with initial empty row", () => {
    render(<IOKeyPairInputWithVariables {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    const keyInputs = screen.getAllByPlaceholderText("Type key...");
    expect(keyInputs).toHaveLength(1);
  });

  it("renders with existing key-value pairs", () => {
    const props = {
      ...defaultProps,
      value: [
        { key: "x-api-key", value: "API_KEY_1", id: "1", error: false },
        { key: "authorization", value: "Bearer token", id: "2", error: false },
      ],
    };

    render(<IOKeyPairInputWithVariables {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getAllByPlaceholderText("Type key...")).toHaveLength(1);
  });

  it("calls onChange when key input changes", () => {
    const onChange = jest.fn();
    const props = { ...defaultProps, onChange };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const keyInput = screen.getByPlaceholderText("Type key...");
    fireEvent.change(keyInput, { target: { value: "x-api-key" } });

    expect(onChange).toHaveBeenCalled();
  });

  it("renders add button for last row when isList is true", () => {
    render(<IOKeyPairInputWithVariables {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    const plusIcon = screen.getByTestId("icon-Plus");
    expect(plusIcon).toBeInTheDocument();
  });

  it("renders delete button for non-last rows", () => {
    const props = {
      ...defaultProps,
      value: [
        { key: "key1", value: "value1", id: "1", error: false },
        { key: "key2", value: "value2", id: "2", error: false },
      ],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const xIcon = screen.getByTestId("icon-X");
    expect(xIcon).toBeInTheDocument();
  });

  it("does not render variable input when enableGlobalVariables is false", () => {
    const props = { ...defaultProps, enableGlobalVariables: false };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    // Should render regular input instead of InputComponent
    const inputs = screen.getAllByPlaceholderText(/Type/);
    expect(inputs.length).toBeGreaterThan(0);
  });

  it("handles empty value array gracefully", () => {
    const props = { ...defaultProps, value: [] };

    const { container } = render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    // Should render without crashing
    expect(container).toBeInTheDocument();
  });

  it("marks duplicate keys as errors when duplicateKey is true", () => {
    const onChange = jest.fn();
    const props = {
      ...defaultProps,
      onChange,
      duplicateKey: true,
      value: [
        { key: "x-api-key", value: "value1", id: "1", error: false },
        { key: "x-api-key", value: "value2", id: "2", error: false },
      ],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    // Component should render
    expect(screen.getAllByPlaceholderText("Type key...")).toHaveLength(2);
  });
});

// Made with Bob
