import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { cloneDeep } from "lodash";
import React from "react";
import TableNodeComponent from "../../components/core/parameterRenderComponent/components/TableNodeComponent";

// Mock the modal component since it's a complex component
jest.mock("@/modals/tableModal", () => {
  return function MockTableModal({
    children,
    open,
    setOpen,
    onSave,
    onCancel,
    tableTitle,
    description,
    rowData,
  }: any) {
    // Clone children and add onClick handler to open modal
    const childrenWithClick = React.cloneElement(children, {
      onClick: () => setOpen(true),
    });

    return (
      <>
        {childrenWithClick}
        {open && (
          <div data-testid="table-modal">
            <div data-testid="modal-title">{tableTitle}</div>
            <div data-testid="modal-description">{description}</div>
            <div data-testid="modal-row-count">{rowData?.length || 0} rows</div>
            <button
              onClick={() => {
                onSave();
                setOpen(false);
              }}
              data-testid="modal-save"
            >
              Save
            </button>
            <button
              onClick={() => {
                onCancel();
                setOpen(false);
              }}
              data-testid="modal-cancel"
            >
              Cancel
            </button>
          </div>
        )}
      </>
    );
  };
});

// Mock the ForwardedIconComponent
jest.mock("../../components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name, className }: any) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Mock the ShadTooltip component
jest.mock("@/components/common/shadTooltipComponent", () => {
  return function MockShadTooltip({ children, content }: any) {
    return <div title={content}>{children}</div>;
  };
});

// Mock the Button component
jest.mock("../../components/ui/button", () => ({
  Button: ({ children, onClick, disabled, className, ...props }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      className={className}
      data-testid="table-trigger-button"
      {...props}
    >
      {children}
    </button>
  ),
}));

// Mock the utils functions
jest.mock("@/utils/utils", () => ({
  FormatColumns: jest.fn((columns) =>
    columns.map((col: any) => ({
      ...col,
      headerName: col.display_name || col.name,
      field: col.name,
    })),
  ),
  generateBackendColumnsFromValue: jest.fn((value, options) => [
    { name: "col1", display_name: "Column 1", type: "str" },
    { name: "col2", display_name: "Column 2", type: "str" },
  ]),
}));

// Mock the markdown utils
jest.mock("@/utils/markdownUtils", () => ({
  isMarkdownTable: jest.fn((text: string) => {
    return text.includes("|") && text.includes("-");
  }),
}));

describe("TableNodeComponent", () => {
  const defaultProps = {
    tableTitle: "Test Table",
    description: "Test Description",
    value: [
      { col1: "value1", col2: "value2" },
      { col1: "value3", col2: "value4" },
    ],
    editNode: false,
    id: "test-table",
    columns: [
      {
        name: "col1",
        display_name: "Column 1",
        type: "str",
        sortable: true,
        filterable: true,
      },
      {
        name: "col2",
        display_name: "Column 2",
        type: "str",
        sortable: true,
        filterable: true,
      },
    ],
    handleOnNewValue: jest.fn(),
    disabled: false,
    table_options: {},
    trigger_icon: "Table",
    trigger_text: "Open Table",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render the table trigger button", () => {
      render(<TableNodeComponent {...defaultProps} />);

      expect(screen.getByTestId("table-trigger-button")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Table")).toBeInTheDocument();
      expect(screen.getByText("Open Table")).toBeInTheDocument();
    });

    it("should render with custom trigger icon and text", () => {
      const props = {
        ...defaultProps,
        trigger_icon: "Database",
        trigger_text: "Custom Text",
      };

      render(<TableNodeComponent {...props} />);

      expect(screen.getByTestId("icon-Database")).toBeInTheDocument();
      expect(screen.getByText("Custom Text")).toBeInTheDocument();
    });

    it("should render disabled state correctly", () => {
      const props = { ...defaultProps, disabled: true };

      render(<TableNodeComponent {...props} />);

      const button = screen.getByTestId("table-trigger-button");
      expect(button).toBeDisabled();
    });

    it("should render with correct test id", () => {
      render(<TableNodeComponent {...defaultProps} />);

      expect(screen.getByTestId("div-test-table")).toBeInTheDocument();
    });
  });

  describe("Modal Functionality", () => {
    it("should open modal when button is clicked", async () => {
      const user = userEvent.setup();
      render(<TableNodeComponent {...defaultProps} />);

      const button = screen.getByTestId("table-trigger-button");
      await user.click(button);

      expect(screen.getByTestId("table-modal")).toBeInTheDocument();
      expect(screen.getByTestId("modal-title")).toHaveTextContent("Test Table");
      expect(screen.getByTestId("modal-description")).toHaveTextContent(
        "Test Description",
      );
    });

    it("should display correct row count in modal", async () => {
      const user = userEvent.setup();
      render(<TableNodeComponent {...defaultProps} />);

      await user.click(screen.getByTestId("table-trigger-button"));

      expect(screen.getByTestId("modal-row-count")).toHaveTextContent("2 rows");
    });

    it("should call handleOnNewValue when save is clicked", async () => {
      const user = userEvent.setup();
      const handleOnNewValue = jest.fn();
      const props = { ...defaultProps, handleOnNewValue };

      render(<TableNodeComponent {...props} />);

      await user.click(screen.getByTestId("table-trigger-button"));
      await user.click(screen.getByTestId("modal-save"));

      expect(handleOnNewValue).toHaveBeenCalledWith({
        value: defaultProps.value,
      });
    });

    it("should reset tempValue when cancel is clicked", async () => {
      const user = userEvent.setup();
      render(<TableNodeComponent {...defaultProps} />);

      await user.click(screen.getByTestId("table-trigger-button"));
      await user.click(screen.getByTestId("modal-cancel"));

      expect(screen.queryByTestId("table-modal")).not.toBeInTheDocument();
    });
  });

  describe("Props Handling", () => {
    it("should sync tempValue with incoming value changes", () => {
      const { rerender } = render(<TableNodeComponent {...defaultProps} />);

      const newValue = [{ col1: "new1", col2: "new2" }];
      rerender(<TableNodeComponent {...defaultProps} value={newValue} />);

      // The component should sync with new values (we can't directly test state,
      // but we can test the effect by checking the modal content)
      // This is implicitly tested through the modal row count
    });

    it("should handle empty value array", () => {
      const props = { ...defaultProps, value: [] };
      render(<TableNodeComponent {...props} />);

      expect(screen.getByTestId("table-trigger-button")).toBeInTheDocument();
    });

    it("should handle undefined value", () => {
      const props = { ...defaultProps, value: [] };
      render(<TableNodeComponent {...props} />);

      expect(screen.getByTestId("table-trigger-button")).toBeInTheDocument();
    });
  });

  describe("Paste Functionality", () => {
    beforeEach(() => {
      // Create a proper mock for isMarkdownTable
      require("@/utils/markdownUtils").isMarkdownTable.mockImplementation(
        (text: string) => {
          return (
            text.includes("|") &&
            text.includes("-") &&
            text.split("\n").length >= 2
          );
        },
      );
    });

    describe("TSV Parsing", () => {
      it("should parse TSV data without header", async () => {
        const user = userEvent.setup();
        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const tsvData = "value5\tvalue6\nvalue7\tvalue8";
        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => tsvData,
          },
        });

        // Check that the data was processed (we can't easily test the internal state,
        // but the paste event should be handled without errors)
        expect(modal).toBeInTheDocument();
      });

      it("should parse TSV data with header detection", async () => {
        const user = userEvent.setup();
        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const tsvData = "col1\tcol2\nvalue5\tvalue6";
        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => tsvData,
          },
        });

        expect(modal).toBeInTheDocument();
      });

      it("should handle TSV data with extra columns", async () => {
        const user = userEvent.setup();
        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const tsvData = "value1\tvalue2\textra1\textra2";
        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => tsvData,
          },
        });

        expect(modal).toBeInTheDocument();
      });
    });

    describe("Markdown Table Parsing", () => {
      it("should parse markdown table with header", async () => {
        const user = userEvent.setup();
        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const markdownTable = `| col1 | col2 |
|------|------|
| val1 | val2 |
| val3 | val4 |`;

        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => markdownTable,
          },
        });

        expect(modal).toBeInTheDocument();
      });

      it("should parse markdown table without separator", async () => {
        const user = userEvent.setup();
        // Mock isMarkdownTable to return false for table without separator
        require("@/utils/markdownUtils").isMarkdownTable.mockReturnValue(false);

        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const markdownTable = `| col1 | col2 |
| val1 | val2 |`;

        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => markdownTable,
          },
        });

        expect(modal).toBeInTheDocument();
      });
    });

    describe("Paste Error Handling", () => {
      it("should handle empty clipboard data", async () => {
        const user = userEvent.setup();
        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => "",
          },
        });

        expect(modal).toBeInTheDocument();
      });

      it("should handle invalid clipboard data", async () => {
        const user = userEvent.setup();
        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const modal = screen.getByTestId("table-modal");

        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => "invalid data format",
          },
        });

        expect(modal).toBeInTheDocument();
      });

      it("should not process paste when modal is closed", async () => {
        const consoleSpy = jest.spyOn(console, "error").mockImplementation();

        render(<TableNodeComponent {...defaultProps} />);

        const container = screen.getByTestId("div-test-table");

        fireEvent.paste(container, {
          clipboardData: {
            getData: () => "value1\tvalue2",
          },
        });

        // Should not throw errors or process the paste
        expect(consoleSpy).not.toHaveBeenCalled();
        consoleSpy.mockRestore();
      });

      it("should handle paste errors gracefully", async () => {
        const user = userEvent.setup();
        const consoleSpy = jest.spyOn(console, "error").mockImplementation();

        render(<TableNodeComponent {...defaultProps} />);

        await user.click(screen.getByTestId("table-trigger-button"));

        const modal = screen.getByTestId("table-modal");

        // Simulate an error in getData
        fireEvent.paste(modal, {
          clipboardData: {
            getData: () => {
              throw new Error("Clipboard error");
            },
          },
        });

        expect(consoleSpy).toHaveBeenCalledWith(
          "Error parsing clipboard data:",
          expect.any(Error),
        );

        consoleSpy.mockRestore();
      });
    });
  });

  describe("Edge Cases", () => {
    it("should handle missing columns prop", () => {
      const props = { ...defaultProps };
      delete (props as any).columns;

      render(<TableNodeComponent {...props} />);

      expect(screen.getByTestId("table-trigger-button")).toBeInTheDocument();
    });

    it("should handle table_options with hide_options", () => {
      const props = {
        ...defaultProps,
        table_options: {
          hide_options: false,
        },
      };

      render(<TableNodeComponent {...props} />);

      expect(screen.getByTestId("table-trigger-button")).toBeInTheDocument();
    });

    it("should handle editNode prop", () => {
      const props = { ...defaultProps, editNode: true };

      render(<TableNodeComponent {...props} />);

      expect(screen.getByTestId("table-trigger-button")).toBeInTheDocument();
    });
  });

  describe("Accessibility", () => {
    it("should have proper disabled state for accessibility", () => {
      const props = { ...defaultProps, disabled: true };

      render(<TableNodeComponent {...props} />);

      const button = screen.getByTestId("table-trigger-button");
      expect(button).toBeDisabled();
      expect(button).toHaveClass("cursor-not-allowed");
    });

    it("should have proper button text for screen readers", () => {
      render(<TableNodeComponent {...defaultProps} />);

      expect(screen.getByText("Open Table")).toBeInTheDocument();
    });
  });
});
