import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { NodeDataType } from "@/types/flow";
import InspectionPanelParameterRow from "../components/InspectionPanelParameterRow";

jest.mock("@/components/common/genericIconComponent", () => {
  return function MockIconComponent({ name, className }: any) {
    return (
      <span data-testid={`icon-${name}`} className={className}>
        {name}
      </span>
    );
  };
});

jest.mock("@/CustomNodes/GenericNode/components/NodeInputInfo", () => {
  return function MockNodeInputInfo({ info }: any) {
    return <span>{info}</span>;
  };
});

const mockHandleOnNewValue = jest.fn();
jest.mock("@/CustomNodes/hooks/use-handle-new-value", () => ({
  __esModule: true,
  default: () => ({
    handleOnNewValue: mockHandleOnNewValue,
  }),
}));

let mockEdges: any[] = [];
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) => selector({ edges: mockEdges }),
}));

let mockFactoryTemplates: Record<string, any> = {};
jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: any) =>
    selector({ templates: mockFactoryTemplates }),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapeJSONParse: (value: string) => JSON.parse(value),
}));

const renderWithProviders = (component: React.ReactNode) => {
  return render(<TooltipProvider>{component}</TooltipProvider>);
};

describe("InspectionPanelParameterRow", () => {
  const createMockData = (fieldOverrides = {}, nodeOverrides = {}): NodeDataType =>
    ({
      id: "test-node-123",
      type: "TestComponent",
      node: {
        display_name: "Test Node",
        description: "Test description",
        tool_mode: false,
        template: {
          test_field: {
            type: "str",
            value: "test value",
            advanced: false,
            show: true,
            required: false,
            info: "",
            api_editable: false,
            ...fieldOverrides,
          },
        },
        ...nodeOverrides,
      },
    }) as unknown as NodeDataType;

  const defaultProps = {
    data: createMockData(),
    name: "test_field",
    title: "Test Field",
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockEdges = [];
    mockFactoryTemplates = {};
  });

  describe("rendering", () => {
    it("renders title and default preview line", () => {
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      expect(screen.getByText("Test Field")).toBeInTheDocument();
      expect(screen.getByText(/Default/)).toBeInTheDocument();
      expect(screen.getByText(/test value/)).toBeInTheDocument();
    });

    it("renders no value editor of any kind", () => {
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      expect(document.querySelector("input")).toBeNull();
      expect(document.querySelector("textarea")).toBeNull();
      expect(document.querySelector("select")).toBeNull();
    });

    it("shows Remove for on-canvas parameters", () => {
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      expect(screen.getByTestId("inspector-remove-test_field")).toBeInTheDocument();
      expect(screen.queryByTestId("inspector-add-test_field")).not.toBeInTheDocument();
    });

    it("shows Add for off-canvas (advanced) parameters", () => {
      const props = { ...defaultProps, data: createMockData({ advanced: true }) };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      expect(screen.getByTestId("inspector-add-test_field")).toBeInTheDocument();
      expect(screen.queryByTestId("inspector-remove-test_field")).not.toBeInTheDocument();
    });

    it("renders the API toggle on every row, including off-canvas ones", () => {
      const props = { ...defaultProps, data: createMockData({ advanced: true }) };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      expect(screen.getByTestId("inspector-api-test_field")).toBeInTheDocument();
    });

    it("prefers the factory default from the types store over the current value", () => {
      mockFactoryTemplates = {
        TestComponent: { template: { test_field: { value: "factory default" } } },
      };
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      expect(screen.getByText(/factory default/)).toBeInTheDocument();
      expect(screen.queryByText(/test value/)).not.toBeInTheDocument();
    });

    it("humanizes boolean defaults as Enabled/Disabled", () => {
      const props = {
        ...defaultProps,
        data: createMockData({ type: "bool", value: true }),
      };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      expect(screen.getByText(/Enabled/)).toBeInTheDocument();
    });

    it("humanizes empty defaults as Empty", () => {
      const props = { ...defaultProps, data: createMockData({ value: "" }) };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      expect(screen.getByText(/Empty/)).toBeInTheDocument();
    });
  });

  describe("add/remove action", () => {
    it("removes an on-canvas parameter by setting advanced=true", async () => {
      const user = userEvent.setup();
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      await user.click(screen.getByTestId("inspector-remove-test_field"));

      expect(mockHandleOnNewValue).toHaveBeenCalledWith({ advanced: true });
    });

    it("adds an off-canvas parameter by setting advanced=false", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, data: createMockData({ advanced: true }) };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      await user.click(screen.getByTestId("inspector-add-test_field"));

      expect(mockHandleOnNewValue).toHaveBeenCalledWith({ advanced: false });
    });

    it("disables Remove when the field has a connected edge", async () => {
      const user = userEvent.setup();
      mockEdges = [
        {
          target: "test-node-123",
          targetHandle: JSON.stringify({ fieldName: "test_field" }),
        },
      ];
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      const removeButton = screen.getByTestId("inspector-remove-test_field");
      expect(removeButton).toBeDisabled();
      await user.click(removeButton);
      expect(mockHandleOnNewValue).not.toHaveBeenCalled();
    });
  });

  describe("api_editable toggle", () => {
    it("enables API editing on click", async () => {
      const user = userEvent.setup();
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      await user.click(screen.getByTestId("inspector-api-test_field"));

      expect(mockHandleOnNewValue).toHaveBeenCalledWith({ api_editable: true });
    });

    it("disables API editing when already enabled", async () => {
      const user = userEvent.setup();
      const props = {
        ...defaultProps,
        data: createMockData({ api_editable: true }),
      };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      const apiButton = screen.getByTestId("inspector-api-test_field");
      expect(apiButton).toHaveAttribute("aria-pressed", "true");
      await user.click(apiButton);

      expect(mockHandleOnNewValue).toHaveBeenCalledWith({ api_editable: false });
    });

    it("blocks API exposure for connected (disabled) fields", async () => {
      const user = userEvent.setup();
      mockEdges = [
        {
          target: "test-node-123",
          targetHandle: JSON.stringify({ fieldName: "test_field" }),
        },
      ];
      renderWithProviders(<InspectionPanelParameterRow {...defaultProps} />);

      const apiButton = screen.getByTestId("inspector-api-test_field");
      expect(apiButton).toBeDisabled();
      await user.click(apiButton);
      expect(mockHandleOnNewValue).not.toHaveBeenCalled();
    });

    it("blocks API exposure for tool-mode fields when tool mode is active", () => {
      const props = {
        ...defaultProps,
        data: createMockData({ tool_mode: true }, { tool_mode: true }),
      };
      renderWithProviders(<InspectionPanelParameterRow {...props} />);

      expect(screen.getByTestId("inspector-api-test_field")).toBeDisabled();
    });
  });
});
