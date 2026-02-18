import { render, screen } from "@testing-library/react";
import InspectionPanelFields from "../components/InspectionPanelFields";
import type { NodeDataType } from "@/types/flow";

// Mock getFieldTitle
jest.mock("@/CustomNodes/utils/get-field-title", () => ({
  __esModule: true,
  default: (template: any, fieldName: string) => {
    return template[fieldName]?.display_name || fieldName;
  },
}));

// Mock sortToolModeFields
jest.mock("@/CustomNodes/helpers/sort-tool-mode-field", () => ({
  sortToolModeFields: (a: string, b: string) => a.localeCompare(b),
}));

// Mock parameter filtering helpers
jest.mock("@/CustomNodes/helpers/parameter-filtering", () => ({
  shouldRenderInspectionPanelField: (
    fieldName: string,
    template: any,
    isToolMode: boolean,
  ) => {
    // Filter out internal fields
    if (fieldName.startsWith("_")) return false;
    // Filter out code fields
    if (fieldName === "code" && template?.type === "code") return false;
    // Filter out tool mode fields when tool mode is enabled
    if (isToolMode && template?.tool_mode === true) return false;
    // Only show advanced fields in normal mode
    return template?.advanced === true && template?.show === true;
  },
  isInternalField: (fieldName: string) => fieldName.startsWith("_"),
  isCodeField: (fieldName: string, template: any) =>
    fieldName === "code" && template?.type === "code",
  isHandleInput: (template: any) => template?.input_types !== undefined,
  isToolModeEnabled: (template: any) => template?.tool_mode === true,
}));

// Mock InspectionPanelField
jest.mock("../components/InspectionPanelField", () => {
  return function MockInspectionPanelField({ title, name }: any) {
    return (
      <div data-testid={`field-${name}`}>
        Field: {title} ({name})
      </div>
    );
  };
});

// Mock InspectionPanelEditField
jest.mock("../components/InspectionPanelEditField", () => {
  return function MockInspectionPanelEditField({
    title,
    name,
    isOnCanvas,
  }: any) {
    return (
      <div data-testid={`edit-field-${name}`}>
        Edit Field: {title} ({name}) - {isOnCanvas ? "On Canvas" : "Advanced"}
      </div>
    );
  };
});

// Mock utils
jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("InspectionPanelFields", () => {
  const createMockData = (templateOverrides = {}): NodeDataType => ({
    id: "test-node-123",
    type: "TestComponent",
    node: {
      display_name: "Test Node",
      description: "Test description",
      template: {
        basic_field: {
          type: "str",
          value: "basic value",
          advanced: false,
          show: true,
          display_name: "Basic Field",
        },
        advanced_field: {
          type: "str",
          value: "advanced value",
          advanced: true,
          show: true,
          display_name: "Advanced Field",
        },
        hidden_field: {
          type: "str",
          value: "hidden",
          advanced: false,
          show: false,
          display_name: "Hidden Field",
        },
        ...templateOverrides,
      },
      field_order: [],
    },
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Normal Mode (View Mode)", () => {
    it("should render only advanced fields in normal mode", () => {
      const data = createMockData();
      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.getByTestId("field-advanced_field")).toBeInTheDocument();
      expect(screen.queryByTestId("field-basic_field")).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("field-hidden_field"),
      ).not.toBeInTheDocument();
    });

    it("should show empty state when no advanced fields", () => {
      const data = createMockData({
        basic_field: {
          type: "str",
          value: "basic",
          advanced: false,
          show: true,
        },
      });
      // Remove advanced field
      delete data.node!.template.advanced_field;

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.getByText("No advanced settings")).toBeInTheDocument();
    });

    it("should filter internal fields", () => {
      const data = createMockData({
        _internal_field: {
          type: "str",
          value: "internal",
          advanced: true,
          show: true,
        },
      });

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(
        screen.queryByTestId("field-_internal_field"),
      ).not.toBeInTheDocument();
    });

    it("should filter code fields", () => {
      const data = createMockData({
        code: {
          type: "code",
          value: "print('hello')",
          advanced: true,
          show: true,
        },
      });

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.queryByTestId("field-code")).not.toBeInTheDocument();
    });

    it("should filter fields with show=false", () => {
      const data = createMockData();

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(
        screen.queryByTestId("field-hidden_field"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Edit Mode", () => {
    it("should render all editable fields in edit mode", () => {
      const data = createMockData();
      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(screen.getByTestId("edit-field-basic_field")).toBeInTheDocument();
      expect(
        screen.getByTestId("edit-field-advanced_field"),
      ).toBeInTheDocument();
    });

    it("should not render hidden fields in edit mode", () => {
      const data = createMockData();
      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(
        screen.queryByTestId("edit-field-hidden_field"),
      ).not.toBeInTheDocument();
    });

    it("should show empty state when no editable fields", () => {
      const data = createMockData({
        hidden_only: {
          type: "str",
          value: "hidden",
          advanced: false,
          show: false,
        },
      });
      // Remove other fields
      delete data.node!.template.basic_field;
      delete data.node!.template.advanced_field;

      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(screen.getByText("No editable fields")).toBeInTheDocument();
    });

    it("should indicate canvas vs advanced state", () => {
      const data = createMockData();
      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(screen.getByText(/Basic Field.*On Canvas/)).toBeInTheDocument();
      expect(screen.getByText(/Advanced Field.*Advanced/)).toBeInTheDocument();
    });

    it("should filter internal fields in edit mode", () => {
      const data = createMockData({
        _internal: {
          type: "str",
          value: "internal",
          advanced: false,
          show: true,
        },
      });

      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(
        screen.queryByTestId("edit-field-_internal"),
      ).not.toBeInTheDocument();
    });

    it("should filter code fields in edit mode", () => {
      const data = createMockData({
        code: {
          type: "code",
          value: "code",
          advanced: false,
          show: true,
        },
      });

      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(screen.queryByTestId("edit-field-code")).not.toBeInTheDocument();
    });
  });

  describe("Tool Mode", () => {
    it("should filter tool mode fields when tool mode is enabled", () => {
      const data = createMockData({
        tool_field: {
          type: "str",
          value: "tool",
          advanced: true,
          show: true,
          tool_mode: true,
        },
      });
      data.node!.tool_mode = true;

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.queryByTestId("field-tool_field")).not.toBeInTheDocument();
    });

    it("should show tool mode fields when tool mode is disabled", () => {
      const data = createMockData({
        tool_field: {
          type: "str",
          value: "tool",
          advanced: true,
          show: true,
          tool_mode: true,
        },
      });
      data.node!.tool_mode = false;

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.getByTestId("field-tool_field")).toBeInTheDocument();
    });
  });

  describe("Field Sorting", () => {
    it("should sort fields alphabetically by default", () => {
      const data = createMockData({
        zebra_field: {
          type: "str",
          value: "z",
          advanced: true,
          show: true,
        },
        alpha_field: {
          type: "str",
          value: "a",
          advanced: true,
          show: true,
        },
      });

      const { container } = render(
        <InspectionPanelFields data={data} isEditingFields={false} />,
      );

      const fields = container.querySelectorAll("[data-testid^='field-']");
      const fieldNames = Array.from(fields).map(
        (el) => el.getAttribute("data-testid")?.replace("field-", "") || "",
      );

      // Should be sorted
      expect(fieldNames[0]).toBe("advanced_field");
      expect(fieldNames[1]).toBe("alpha_field");
      expect(fieldNames[2]).toBe("zebra_field");
    });
  });

  describe("Component Keys", () => {
    it("should use unique keys for fields in normal mode", () => {
      const data = createMockData();
      const { container } = render(
        <InspectionPanelFields data={data} isEditingFields={false} />,
      );

      // React uses keys internally, we verify components render correctly
      expect(screen.getByTestId("field-advanced_field")).toBeInTheDocument();
    });

    it("should use unique keys for fields in edit mode", () => {
      const data = createMockData();
      const { container } = render(
        <InspectionPanelFields data={data} isEditingFields={true} />,
      );

      expect(screen.getByTestId("edit-field-basic_field")).toBeInTheDocument();
      expect(
        screen.getByTestId("edit-field-advanced_field"),
      ).toBeInTheDocument();
    });
  });

  describe("Mode Switching", () => {
    it("should switch from normal to edit mode", () => {
      const data = createMockData();
      const { rerender } = render(
        <InspectionPanelFields data={data} isEditingFields={false} />,
      );

      expect(screen.getByTestId("field-advanced_field")).toBeInTheDocument();
      expect(
        screen.queryByTestId("edit-field-basic_field"),
      ).not.toBeInTheDocument();

      rerender(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(
        screen.queryByTestId("field-advanced_field"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("edit-field-basic_field")).toBeInTheDocument();
    });

    it("should switch from edit to normal mode", () => {
      const data = createMockData();
      const { rerender } = render(
        <InspectionPanelFields data={data} isEditingFields={true} />,
      );

      expect(screen.getByTestId("edit-field-basic_field")).toBeInTheDocument();

      rerender(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(
        screen.queryByTestId("edit-field-basic_field"),
      ).not.toBeInTheDocument();
      expect(screen.getByTestId("field-advanced_field")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle empty template", () => {
      const data = createMockData();
      data.node!.template = {};

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.getByText("No advanced settings")).toBeInTheDocument();
    });

    it("should handle undefined template", () => {
      const data = createMockData();
      data.node!.template = undefined as any;

      expect(() => {
        render(<InspectionPanelFields data={data} isEditingFields={false} />);
      }).not.toThrow();
    });

    it("should handle null node", () => {
      const data = createMockData();
      data.node = null as any;

      expect(() => {
        render(<InspectionPanelFields data={data} isEditingFields={false} />);
      }).not.toThrow();
    });

    it("should handle missing field_order", () => {
      const data = createMockData();
      data.node!.field_order = undefined;

      expect(() => {
        render(<InspectionPanelFields data={data} isEditingFields={false} />);
      }).not.toThrow();
    });

    it("should handle fields with missing properties", () => {
      const data = createMockData({
        incomplete_field: {
          type: "str",
          // Missing other properties
        } as any,
      });

      expect(() => {
        render(<InspectionPanelFields data={data} isEditingFields={false} />);
      }).not.toThrow();
    });
  });

  describe("Multiple Fields", () => {
    it("should render multiple advanced fields", () => {
      const data = createMockData({
        advanced1: {
          type: "str",
          value: "1",
          advanced: true,
          show: true,
        },
        advanced2: {
          type: "str",
          value: "2",
          advanced: true,
          show: true,
        },
        advanced3: {
          type: "str",
          value: "3",
          advanced: true,
          show: true,
        },
      });

      render(<InspectionPanelFields data={data} isEditingFields={false} />);

      expect(screen.getByTestId("field-advanced1")).toBeInTheDocument();
      expect(screen.getByTestId("field-advanced2")).toBeInTheDocument();
      expect(screen.getByTestId("field-advanced3")).toBeInTheDocument();
    });

    it("should render multiple editable fields in edit mode", () => {
      const data = createMockData({
        field1: {
          type: "str",
          value: "1",
          advanced: false,
          show: true,
        },
        field2: {
          type: "str",
          value: "2",
          advanced: false,
          show: true,
        },
      });

      render(<InspectionPanelFields data={data} isEditingFields={true} />);

      expect(screen.getByTestId("edit-field-field1")).toBeInTheDocument();
      expect(screen.getByTestId("edit-field-field2")).toBeInTheDocument();
    });
  });

  describe("Layout", () => {
    it("should have correct container classes", () => {
      const data = createMockData();
      const { container } = render(
        <InspectionPanelFields data={data} isEditingFields={false} />,
      );

      const wrapper = container.querySelector(".pb-2");
      expect(wrapper).toBeInTheDocument();
    });

    it("should have padding wrapper", () => {
      const data = createMockData();
      const { container } = render(
        <InspectionPanelFields data={data} isEditingFields={false} />,
      );

      const innerWrapper = container.querySelector(".px-1");
      expect(innerWrapper).toBeInTheDocument();
    });
  });
});
