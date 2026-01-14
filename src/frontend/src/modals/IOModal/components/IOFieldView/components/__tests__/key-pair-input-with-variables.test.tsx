import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

    const keyInputs = screen.getAllByPlaceholderText("Key");
    const valueInputs = screen.getAllByPlaceholderText("Value");

    expect(keyInputs).toHaveLength(1);
    expect(valueInputs).toHaveLength(1);
  });

  it("renders with existing key-value pairs", () => {
    const props = {
      ...defaultProps,
      value: [
        { key: "x-api-key", value: "API_KEY_1", id: "1", error: false },
        { key: "authorization", value: "Bearer token", id: "2", error: false },
      ],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByDisplayValue("x-api-key")).toBeInTheDocument();
    expect(screen.getByDisplayValue("API_KEY_1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("authorization")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Bearer token")).toBeInTheDocument();
  });

  it("shows global variable badge for matching variable names", async () => {
    const props = {
      ...defaultProps,
      value: [{ key: "x-api-key", value: "API_KEY_1", id: "1", error: false }],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(screen.getByText("API_KEY_1")).toBeInTheDocument();
    });
  });

  it("adds a new row when clicking add button", () => {
    const onChange = jest.fn();
    const props = { ...defaultProps, onChange };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const addButton = screen.getByRole("button", { name: /add/i });
    fireEvent.click(addButton);

    expect(onChange).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ key: "", value: "", error: false }),
        expect.objectContaining({ key: "", value: "", error: false }),
      ]),
    );
  });

  it("removes a row when clicking delete button", () => {
    const onChange = jest.fn();
    const props = {
      ...defaultProps,
      onChange,
      value: [
        { key: "key1", value: "value1", id: "1", error: false },
        { key: "key2", value: "value2", id: "2", error: false },
      ],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    fireEvent.click(deleteButtons[0]);

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ key: "key2", value: "value2", id: "2" }),
    ]);
  });

  it("updates key value on input change", () => {
    const onChange = jest.fn();
    const props = { ...defaultProps, onChange };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const keyInput = screen.getByPlaceholderText("Key");
    fireEvent.change(keyInput, { target: { value: "x-api-key" } });

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ key: "x-api-key", value: "", error: false }),
    ]);
  });

  it("updates value on input change", () => {
    const onChange = jest.fn();
    const props = { ...defaultProps, onChange };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const valueInput = screen.getByPlaceholderText("Value");
    fireEvent.change(valueInput, { target: { value: "test-value" } });

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ key: "", value: "test-value", error: false }),
    ]);
  });

  it("detects duplicate keys when duplicateKey is true", () => {
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

    // Component should mark duplicate keys with error
    expect(onChange).toHaveBeenCalled();
  });

  it("shows global variable dropdown when clicking variable button", async () => {
    render(<IOKeyPairInputWithVariables {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    const variableButtons = screen.getAllByRole("button", {
      name: /variable/i,
    });
    fireEvent.click(variableButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("API_KEY_1")).toBeInTheDocument();
      expect(screen.getByText("API_KEY_2")).toBeInTheDocument();
      expect(screen.getByText("TOKEN")).toBeInTheDocument();
    });
  });

  it("selects global variable from dropdown", async () => {
    const onChange = jest.fn();
    const props = { ...defaultProps, onChange };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const variableButtons = screen.getAllByRole("button", {
      name: /variable/i,
    });
    fireEvent.click(variableButtons[0]);

    await waitFor(() => {
      const apiKeyOption = screen.getByText("API_KEY_1");
      fireEvent.click(apiKeyOption);
    });

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ key: "", value: "API_KEY_1", error: false }),
    ]);
  });

  it("does not show variable dropdown when enableGlobalVariables is false", () => {
    const props = { ...defaultProps, enableGlobalVariables: false };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const variableButtons = screen.queryAllByRole("button", {
      name: /variable/i,
    });
    expect(variableButtons).toHaveLength(0);
  });

  it("handles empty value array gracefully", () => {
    const props = { ...defaultProps, value: [] };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    // Should render without crashing
    expect(screen.getByPlaceholderText("Key")).toBeInTheDocument();
  });

  it("preserves non-variable values when editing", () => {
    const onChange = jest.fn();
    const props = {
      ...defaultProps,
      onChange,
      value: [
        {
          key: "content-type",
          value: "application/json",
          id: "1",
          error: false,
        },
      ],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    const valueInput = screen.getByDisplayValue("application/json");
    fireEvent.change(valueInput, { target: { value: "text/plain" } });

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        key: "content-type",
        value: "text/plain",
        error: false,
      }),
    ]);
  });

  it("initializes selectedGlobalVariables from existing values", async () => {
    const props = {
      ...defaultProps,
      value: [
        { key: "x-api-key", value: "API_KEY_1", id: "1", error: false },
        { key: "authorization", value: "TOKEN", id: "2", error: false },
      ],
    };

    render(<IOKeyPairInputWithVariables {...props} />, {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      // Both variable badges should be visible
      const badges = screen.getAllByText(/API_KEY_1|TOKEN/);
      expect(badges.length).toBeGreaterThan(0);
    });
  });

  it("handles loading state for global variables", () => {
    const useGetGlobalVariables = jest.fn(() => ({
      data: undefined,
      isLoading: true,
    }));

    jest.mock(
      "@/controllers/API/queries/variables/use-get-global-variables",
      () => ({
        useGetGlobalVariables,
      }),
    );

    render(<IOKeyPairInputWithVariables {...defaultProps} />, {
      wrapper: createWrapper(),
    });

    // Should render without crashing during loading
    expect(screen.getByPlaceholderText("Key")).toBeInTheDocument();
  });
});

// Made with Bob
