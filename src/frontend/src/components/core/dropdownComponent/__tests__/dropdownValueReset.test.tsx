import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useGetModelProviders } from "@/controllers/API/queries/models/use-get-model-providers";
import type { APIClassType } from "@/types/api";
import Dropdown from "../index";

interface MockChildrenProps {
  children: ReactNode;
}

interface MockCommandItemProps extends Record<string, unknown> {
  children: ReactNode;
  onSelect?: (value: string) => void;
  value?: string;
}

interface MockButtonProps extends Record<string, unknown> {
  children: ReactNode;
}

interface MockStoreSelectorFn<T> {
  (state: T): unknown;
}

let mockCurrentFlowId = "flow-one";

jest.mock("@radix-ui/react-popover", () => ({
  PopoverAnchor: ({ children }: MockChildrenProps) => <div>{children}</div>,
}));

jest.mock("fuse.js", () => {
  return jest.fn().mockImplementation(() => ({
    search: jest.fn(() => []),
  }));
});

jest.mock("@/CustomNodes/GenericNode/components/NodeDialogComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: jest.fn(),
}));

jest.mock("@/components/common/loadingTextComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/constants/constants", () => ({
  RECEIVING_INPUT_VALUE: "Receiving input",
  SELECT_AN_OPTION: "Select an option",
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: () => ({ mutateAsync: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: jest.fn(),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector?: MockStoreSelectorFn<{ setErrorData: jest.Mock }>) =>
    selector ? selector({ setErrorData: jest.fn() }) : {},
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: MockStoreSelectorFn<{ nodes: unknown[] }>) =>
    selector ? selector({ nodes: [] }) : {},
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (
    selector?: MockStoreSelectorFn<{
      currentFlowId: string;
    }>,
  ) => (selector ? selector({ currentFlowId: mockCurrentFlowId }) : {}),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (
    selector?: MockStoreSelectorFn<{ types: Record<string, unknown> }>,
  ) => (selector ? selector({ types: {} }) : {}),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapedJSONStringfy: jest.fn((v: unknown) => JSON.stringify(v)),
}));

jest.mock("@/utils/stringManipulation", () => ({
  convertStringToHTML: jest.fn((v: string) => v),
  getStatusColor: jest.fn(() => ""),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
  filterNullOptions: (opts: (string | null)[]) =>
    opts?.filter((o): o is string => o != null) ?? [],
  formatName: (name: string) => ({ firstWord: name }),
  groupByFamily: jest.fn(() => ({})),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: MockChildrenProps) => <div>{children}</div>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: MockButtonProps) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/components/ui/command", () => ({
  Command: ({ children }: MockChildrenProps) => <div>{children}</div>,
  CommandGroup: ({ children }: MockChildrenProps) => <div>{children}</div>,
  CommandItem: ({
    children,
    onSelect,
    value,
    ...props
  }: MockCommandItemProps) => (
    <button type="button" onClick={() => onSelect?.(value ?? "")} {...props}>
      {children}
    </button>
  ),
  CommandList: ({ children }: MockChildrenProps) => <div>{children}</div>,
  CommandSeparator: () => <hr />,
}));

jest.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: MockChildrenProps) => <div>{children}</div>,
  PopoverContent: ({ children }: MockChildrenProps) => <div>{children}</div>,
  PopoverContentWithoutPortal: ({ children }: MockChildrenProps) => (
    <div>{children}</div>
  ),
  PopoverTrigger: ({ children }: MockChildrenProps) => <div>{children}</div>,
}));

const mockNodeClass: APIClassType = {
  template: {},
  display_name: "Test",
  documentation: "",
  description: "",
};

const mockUseGetModelProviders = useGetModelProviders as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
  mockCurrentFlowId = "flow-one";
  mockUseGetModelProviders.mockReturnValue({
    data: undefined,
    isLoading: false,
    isFetching: false,
    isError: false,
  });
});

describe("Dropdown value reset bug", () => {
  /**
   * GIVEN: Dropdown with saved value ("new_flow_2") and empty options
   *        (options haven't loaded from backend yet)
   * WHEN:  Component renders (flow reload)
   * THEN:  Value should NOT be reset — empty options means still loading
   */
  it("should_preserve_value_when_options_are_empty_and_loading", () => {
    const mockOnSelect = jest.fn();

    render(
      <Dropdown
        value="new_flow_2"
        options={[]}
        onSelect={mockOnSelect}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(mockOnSelect).not.toHaveBeenCalledWith("", undefined, true);
  });

  it("should_reset_value_when_options_are_loaded_and_value_is_not_in_options", () => {
    const mockOnSelect = jest.fn();

    render(
      <Dropdown
        value="deleted_tool"
        options={["tool_a", "tool_b", "tool_c"]}
        onSelect={mockOnSelect}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(mockOnSelect).toHaveBeenCalledWith("", undefined, true);
  });

  it("should_preserve_value_when_options_are_loaded_and_value_is_in_options", () => {
    const mockOnSelect = jest.fn();

    render(
      <Dropdown
        value="tool_b"
        options={["tool_a", "tool_b", "tool_c"]}
        onSelect={mockOnSelect}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(mockOnSelect).not.toHaveBeenCalledWith("", undefined, true);
  });
});

describe("Dropdown accessibility", () => {
  // The search box is a bare <input> that only carried a placeholder, which is
  // not an accessible name (WCAG 4.1.2 / 3.3.2).
  it("should_name_the_search_input", () => {
    render(
      <Dropdown
        value="tool_a"
        options={["tool_a", "tool_b"]}
        onSelect={jest.fn()}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByTestId("dropdown_search_input")).toHaveAccessibleName(
      "Search options...",
    );
  });
});

describe("legacy provider dropdown policy", () => {
  const renderProviderDropdown = (
    value = "Anthropic",
    options = ["OpenAI", "Anthropic", "Custom"],
  ) =>
    render(
      <Dropdown
        value={value}
        options={options}
        optionsMetaData={options.map((option) => ({ icon: option }))}
        onSelect={jest.fn()}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

  it("hides static provider options until the active flow policy resolves", () => {
    mockUseGetModelProviders.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: true,
      isError: false,
    });

    renderProviderDropdown();

    expect(mockUseGetModelProviders).toHaveBeenCalledWith(
      { flowId: "flow-one", purpose: "use" },
      { enabled: true },
    );
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
  });

  it("hides cached provider options while the active flow policy is paused", () => {
    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "OpenAI" }],
      isLoading: false,
      isFetching: false,
      fetchStatus: "paused",
      isError: false,
    });

    renderProviderDropdown("OpenAI");

    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
  });

  it("shows only scoped providers while preserving the custom option", () => {
    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "OpenAI" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });

    renderProviderDropdown("OpenAI");

    expect(screen.getAllByText("OpenAI").length).toBeGreaterThan(0);
    expect(screen.getByText("Custom")).toBeInTheDocument();
    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
  });

  it("keeps the legacy WatsonX alias and its aligned metadata", () => {
    const onSelect = jest.fn();
    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "IBM WatsonX" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });

    render(
      <Dropdown
        value=""
        options={["OpenAI", "IBM watsonx.ai", "Custom"]}
        optionsMetaData={[
          { icon: "OpenAI" },
          { icon: "WatsonxAI" },
          { icon: "brain" },
        ]}
        onSelect={onSelect}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(screen.getByText("IBM watsonx.ai")).toBeInTheDocument();
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("IBM watsonx.ai-0-option"));
    expect(onSelect).toHaveBeenCalledWith(
      "IBM watsonx.ai",
      undefined,
      undefined,
      { icon: "WatsonxAI" },
    );
  });

  it("hides a revoked saved provider without clearing it and keeps it hidden through a later error", () => {
    const onSelect = jest.fn();
    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "OpenAI" }, { provider: "Anthropic" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });
    const { rerender } = render(
      <Dropdown
        value="Anthropic"
        options={["OpenAI", "Anthropic", "Custom"]}
        onSelect={onSelect}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "OpenAI" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });
    rerender(
      <Dropdown
        value="Anthropic"
        options={["OpenAI", "Anthropic", "Custom"]}
        onSelect={onSelect}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalledWith("", undefined, true);

    mockUseGetModelProviders.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      isError: true,
    });
    rerender(
      <Dropdown
        value="Anthropic"
        options={["OpenAI", "Anthropic", "Custom"]}
        onSelect={onSelect}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalledWith("", undefined, true);
  });

  it("does not reuse a previous flow's provider grants while the next scope loads", () => {
    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "OpenAI" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });
    const { rerender } = renderProviderDropdown("OpenAI");

    expect(screen.getAllByText("OpenAI").length).toBeGreaterThan(0);

    mockCurrentFlowId = "flow-two";
    mockUseGetModelProviders.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: true,
      isError: false,
    });
    rerender(
      <Dropdown
        value="OpenAI"
        options={["OpenAI", "Anthropic", "Custom"]}
        onSelect={jest.fn()}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(mockUseGetModelProviders).toHaveBeenLastCalledWith(
      { flowId: "flow-two", purpose: "use" },
      { enabled: true },
    );
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();

    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "Anthropic" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });
    rerender(
      <Dropdown
        value="Anthropic"
        options={["OpenAI", "Anthropic", "Custom"]}
        onSelect={jest.fn()}
        name="agent_llm"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="provider-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(screen.getAllByText("Anthropic").length).toBeGreaterThan(0);
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
  });

  it("fails closed when no stored flow scope is available", () => {
    mockCurrentFlowId = "";

    renderProviderDropdown("OpenAI");

    expect(mockUseGetModelProviders).toHaveBeenCalledWith(
      { flowId: "", purpose: "use" },
      { enabled: false },
    );
    expect(screen.queryByText("OpenAI")).not.toBeInTheDocument();
    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
    expect(screen.getByText("Custom")).toBeInTheDocument();
  });

  it("leaves ordinary dropdowns unchanged", () => {
    mockUseGetModelProviders.mockReturnValue({
      data: [{ provider: "OpenAI" }],
      isLoading: false,
      isFetching: false,
      isError: false,
    });

    render(
      <Dropdown
        value="tool_b"
        options={["tool_a", "tool_b"]}
        onSelect={jest.fn()}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="ordinary-dropdown"
        editNode={false}
        handleOnNewValue={jest.fn()}
        disabled={false}
      />,
    );

    expect(screen.getAllByText("tool_a").length).toBeGreaterThan(0);
    expect(screen.getAllByText("tool_b").length).toBeGreaterThan(0);
  });

  it("handles an empty scoped result for an ALTK dropdown without Custom", () => {
    mockUseGetModelProviders.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      isError: false,
    });

    renderProviderDropdown("Anthropic", ["Anthropic"]);

    expect(screen.queryByText("Anthropic")).not.toBeInTheDocument();
    expect(screen.getByTestId("provider-dropdown")).toBeDisabled();
  });
});
