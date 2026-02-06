import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderHook } from "@testing-library/react";
import EditableHeaderContent from "../components/EditableHeaderContent";
import type { NodeDataType } from "@/types/flow";

// Mock Markdown component
jest.mock("react-markdown", () => {
  return function MockMarkdown({ children }: any) {
    return <div data-testid="markdown-content">{children}</div>;
  };
});

// Mock Input component
jest.mock("@/components/ui/input", () => ({
  Input: ({ value, onChange, onKeyDown, ...props }: any) => (
    <input value={value} onChange={onChange} onKeyDown={onKeyDown} {...props} />
  ),
}));

// Mock Textarea component
jest.mock("@/components/ui/textarea", () => ({
  Textarea: ({ value, onChange, onKeyDown, ...props }: any) => (
    <textarea
      value={value}
      onChange={onChange}
      onKeyDown={onKeyDown}
      {...props}
    />
  ),
}));

// Mock stores
const mockTakeSnapshot = jest.fn();
const mockSetNode = jest.fn();

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      takeSnapshot: mockTakeSnapshot,
    }),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: any) =>
    selector({
      setNode: mockSetNode,
    }),
}));

// Mock utils
jest.mock("@/utils/utils", () => ({
  cn: (...classes: any[]) => classes.filter(Boolean).join(" "),
}));

describe("EditableHeaderContent", () => {
  const createMockData = (overrides = {}): NodeDataType => ({
    id: "test-node-123",
    type: "TestComponent",
    node: {
      display_name: "Test Node",
      description: "Test description",
      template: {},
      ...overrides,
    },
  });

  const defaultProps = {
    data: createMockData(),
    editMode: false,
    setEditMode: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("View Mode Rendering", () => {
    it("should render display name in view mode", () => {
      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(defaultProps);
        return <div>{nameElement}</div>;
      };

      render(<TestComponent />);
      expect(screen.getByText("Test Node")).toBeInTheDocument();
    });

    it("should render markdown description in view mode", () => {
      const TestComponent = () => {
        const { descriptionElement } = EditableHeaderContent(defaultProps);
        return <div>{descriptionElement}</div>;
      };

      render(<TestComponent />);
      expect(screen.getByTestId("markdown-content")).toBeInTheDocument();
      expect(screen.getByTestId("markdown-content")).toHaveTextContent(
        "Test description",
      );
    });

    it("should render empty description when no description provided", () => {
      const props = {
        ...defaultProps,
        data: createMockData({ description: "" }),
      };

      const TestComponent = () => {
        const { descriptionElement } = EditableHeaderContent(props);
        return <div>{descriptionElement}</div>;
      };

      render(<TestComponent />);
      expect(screen.queryByTestId("markdown-content")).not.toBeInTheDocument();
    });

    it("should fallback to type when display_name is not provided", () => {
      const props = {
        ...defaultProps,
        data: createMockData({ display_name: undefined }),
      };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      render(<TestComponent />);
      expect(screen.getByText("TestComponent")).toBeInTheDocument();
    });
  });

  describe("Edit Mode Rendering", () => {
    it("should render input for name in edit mode", () => {
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");
      expect(input).toBeInTheDocument();
      expect(input).toHaveValue("Test Node");
    });

    it("should render textarea for description in edit mode", () => {
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { descriptionElement } = EditableHeaderContent(props);
        return <div>{descriptionElement}</div>;
      };

      render(<TestComponent />);
      const textarea = screen.getByTestId("inspection-panel-description");
      expect(textarea).toBeInTheDocument();
      expect(textarea).toHaveValue("Test description");
    });

    it("should take snapshot when entering edit mode", () => {
      const props = { ...defaultProps, editMode: false };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      const { rerender } = render(<TestComponent />);

      const propsEditMode = { ...defaultProps, editMode: true };
      const TestComponentEdit = () => {
        const { nameElement } = EditableHeaderContent(propsEditMode);
        return <div>{nameElement}</div>;
      };

      rerender(<TestComponentEdit />);

      // Snapshot should be taken when entering edit mode
      waitFor(() => {
        expect(mockTakeSnapshot).toHaveBeenCalled();
      });
    });
  });

  describe("Name Editing", () => {
    it("should update local name when typing", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");

      await user.clear(input);
      await user.type(input, "New Name");

      expect(input).toHaveValue("New Name");
    });

    it("should save on Enter key", async () => {
      const user = userEvent.setup();
      const setEditMode = jest.fn();
      const props = { ...defaultProps, editMode: true, setEditMode };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");

      await user.clear(input);
      await user.type(input, "New Name");
      await user.keyboard("{Enter}");

      await waitFor(() => {
        expect(mockSetNode).toHaveBeenCalled();
        expect(setEditMode).toHaveBeenCalledWith(false);
      });
    });

    it("should cancel on Escape key", async () => {
      const user = userEvent.setup();
      const setEditMode = jest.fn();
      const props = { ...defaultProps, editMode: true, setEditMode };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");

      await user.clear(input);
      await user.type(input, "New Name");
      await user.keyboard("{Escape}");

      await waitFor(() => {
        expect(setEditMode).toHaveBeenCalledWith(false);
      });

      // Value should be reset
      expect(input).toHaveValue("Test Node");
    });

    it("should trim whitespace when saving", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { nameElement, handleSave } = EditableHeaderContent(props);
        return (
          <div>
            {nameElement}
            <button onClick={handleSave} data-testid="save-button">
              Save
            </button>
          </div>
        );
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");

      await user.clear(input);
      await user.type(input, "  Spaced Name  ");

      await user.click(screen.getByTestId("save-button"));

      await waitFor(() => {
        expect(mockSetNode).toHaveBeenCalledWith(
          "test-node-123",
          expect.any(Function),
        );
      });

      // Get the callback function passed to setNode
      const setNodeCallback = mockSetNode.mock.calls[0][1];
      const oldNode = {
        data: {
          node: {
            display_name: "Test Node",
            description: "Test description",
          },
        },
      };
      const result = setNodeCallback(oldNode);

      expect(result.data.node.display_name).toBe("Spaced Name");
    });

    it("should fallback to original name if empty", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { nameElement, handleSave } = EditableHeaderContent(props);
        return (
          <div>
            {nameElement}
            <button onClick={handleSave} data-testid="save-button">
              Save
            </button>
          </div>
        );
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");

      await user.clear(input);
      await user.click(screen.getByTestId("save-button"));

      await waitFor(() => {
        expect(mockSetNode).toHaveBeenCalled();
      });

      const setNodeCallback = mockSetNode.mock.calls[0][1];
      const oldNode = {
        data: {
          node: {
            display_name: "Test Node",
            description: "Test description",
          },
        },
      };
      const result = setNodeCallback(oldNode);

      expect(result.data.node.display_name).toBe("Test Node");
    });
  });

  describe("Description Editing", () => {
    it("should update local description when typing", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { descriptionElement } = EditableHeaderContent(props);
        return <div>{descriptionElement}</div>;
      };

      render(<TestComponent />);
      const textarea = screen.getByTestId("inspection-panel-description");

      await user.clear(textarea);
      await user.type(textarea, "New description");

      expect(textarea).toHaveValue("New description");
    });

    it("should cancel description on Escape key", async () => {
      const user = userEvent.setup();
      const setEditMode = jest.fn();
      const props = { ...defaultProps, editMode: true, setEditMode };

      const TestComponent = () => {
        const { descriptionElement } = EditableHeaderContent(props);
        return <div>{descriptionElement}</div>;
      };

      render(<TestComponent />);
      const textarea = screen.getByTestId("inspection-panel-description");

      await user.clear(textarea);
      await user.type(textarea, "New description");
      await user.keyboard("{Escape}");

      await waitFor(() => {
        expect(setEditMode).toHaveBeenCalledWith(false);
      });

      // Value should be reset
      expect(textarea).toHaveValue("Test description");
    });
  });

  describe("Save Functionality", () => {
    it("should not save if no changes were made", () => {
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { handleSave } = EditableHeaderContent(props);
        return (
          <button onClick={handleSave} data-testid="save-button">
            Save
          </button>
        );
      };

      render(<TestComponent />);
      const saveButton = screen.getByTestId("save-button");

      fireEvent.click(saveButton);

      expect(mockSetNode).not.toHaveBeenCalled();
    });

    it("should save when changes are made", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { nameElement, handleSave } = EditableHeaderContent(props);
        return (
          <div>
            {nameElement}
            <button onClick={handleSave} data-testid="save-button">
              Save
            </button>
          </div>
        );
      };

      render(<TestComponent />);
      const input = screen.getByTestId("inspection-panel-name");

      await user.clear(input);
      await user.type(input, "Modified Name");

      await user.click(screen.getByTestId("save-button"));

      await waitFor(() => {
        expect(mockSetNode).toHaveBeenCalled();
      });
    });

    it("should save both name and description", async () => {
      const user = userEvent.setup();
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { nameElement, descriptionElement, handleSave } =
          EditableHeaderContent(props);
        return (
          <div>
            {nameElement}
            {descriptionElement}
            <button onClick={handleSave} data-testid="save-button">
              Save
            </button>
          </div>
        );
      };

      render(<TestComponent />);

      const input = screen.getByTestId("inspection-panel-name");
      const textarea = screen.getByTestId("inspection-panel-description");

      await user.clear(input);
      await user.type(input, "New Name");

      await user.clear(textarea);
      await user.type(textarea, "New Description");

      await user.click(screen.getByTestId("save-button"));

      await waitFor(() => {
        expect(mockSetNode).toHaveBeenCalled();
      });

      const setNodeCallback = mockSetNode.mock.calls[0][1];
      const oldNode = {
        data: {
          node: {
            display_name: "Test Node",
            description: "Test description",
          },
        },
      };
      const result = setNodeCallback(oldNode);

      expect(result.data.node.display_name).toBe("New Name");
      expect(result.data.node.description).toBe("New Description");
    });
  });

  describe("Click Outside Behavior", () => {
    it("should provide containerRef for click outside detection", () => {
      const props = { ...defaultProps, editMode: true };

      const TestComponent = () => {
        const { containerRef, nameElement } = EditableHeaderContent(props);
        return (
          <div ref={containerRef} data-testid="container">
            {nameElement}
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId("container")).toBeInTheDocument();
    });

    it("should not exit edit mode when clicking inside container", async () => {
      const setEditMode = jest.fn();
      const props = { ...defaultProps, editMode: true, setEditMode };

      const TestComponent = () => {
        const { containerRef, nameElement } = EditableHeaderContent(props);
        return (
          <div ref={containerRef} data-testid="container">
            {nameElement}
            <button data-testid="inside-button">Inside</button>
          </div>
        );
      };

      render(<TestComponent />);

      const insideButton = screen.getByTestId("inside-button");
      fireEvent.mouseDown(insideButton);

      // Should not exit edit mode immediately
      expect(setEditMode).not.toHaveBeenCalled();
    });
  });

  describe("Data Synchronization", () => {
    it("should update local state when data changes", () => {
      const props = { ...defaultProps, editMode: false };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      const { rerender } = render(<TestComponent />);

      expect(screen.getByText("Test Node")).toBeInTheDocument();

      const newProps = {
        ...props,
        data: createMockData({ display_name: "Updated Node" }),
      };

      const TestComponentUpdated = () => {
        const { nameElement } = EditableHeaderContent(newProps);
        return <div>{nameElement}</div>;
      };

      rerender(<TestComponentUpdated />);

      expect(screen.getByText("Updated Node")).toBeInTheDocument();
    });
  });

  describe("Edge Cases", () => {
    it("should handle undefined display_name", () => {
      const props = {
        ...defaultProps,
        data: createMockData({ display_name: undefined }),
      };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      expect(() => render(<TestComponent />)).not.toThrow();
    });

    it("should handle undefined description", () => {
      const props = {
        ...defaultProps,
        data: createMockData({ description: undefined }),
      };

      const TestComponent = () => {
        const { descriptionElement } = EditableHeaderContent(props);
        return <div>{descriptionElement}</div>;
      };

      expect(() => render(<TestComponent />)).not.toThrow();
    });

    it("should handle null node", () => {
      const props = {
        ...defaultProps,
        data: { ...defaultProps.data, node: null as any },
      };

      const TestComponent = () => {
        const { nameElement } = EditableHeaderContent(props);
        return <div>{nameElement}</div>;
      };

      expect(() => render(<TestComponent />)).not.toThrow();
    });
  });
});
