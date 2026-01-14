import { render, screen, fireEvent } from "@testing-library/react";
import { ReferenceAutocomplete } from "../ReferenceAutocomplete";
import type { UpstreamOutput } from "@/types/references";

const mockOptions: UpstreamOutput[] = [
  {
    nodeId: "node1",
    nodeSlug: "ChatInput",
    nodeName: "Chat Input",
    outputName: "message",
    outputDisplayName: "Message",
    outputType: "Message",
  },
  {
    nodeId: "node2",
    nodeSlug: "TextSplitter",
    nodeName: "Text Splitter",
    outputName: "chunks",
    outputDisplayName: "Chunks",
    outputType: "str",
  },
  {
    nodeId: "node3",
    nodeSlug: "APIRequest",
    nodeName: "API Request",
    outputName: "response",
    outputDisplayName: "Response",
    outputType: "Data",
  },
];

describe("ReferenceAutocomplete", () => {
  const defaultProps = {
    isOpen: true,
    options: mockOptions,
    onSelect: jest.fn(),
    onClose: jest.fn(),
    filter: "",
    position: { top: 100, left: 50 },
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("rendering", () => {
    it("should not render when isOpen is false", () => {
      render(<ReferenceAutocomplete {...defaultProps} isOpen={false} />);

      expect(
        screen.queryByTestId("reference-autocomplete-dropdown"),
      ).not.toBeInTheDocument();
    });

    it("should not render when no options match filter", () => {
      render(<ReferenceAutocomplete {...defaultProps} filter="nonexistent" />);

      expect(
        screen.queryByTestId("reference-autocomplete-dropdown"),
      ).not.toBeInTheDocument();
    });

    it("should render dropdown when open with options", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      expect(
        screen.getByTestId("reference-autocomplete-dropdown"),
      ).toBeInTheDocument();
    });

    it("should render all options when no filter", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      expect(
        screen.getByTestId("reference-option-ChatInput-message"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("reference-option-TextSplitter-chunks"),
      ).toBeInTheDocument();
      expect(
        screen.getByTestId("reference-option-APIRequest-response"),
      ).toBeInTheDocument();
    });

    it("should display node name, output name, and type", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      const option = screen.getByTestId("reference-option-ChatInput-message");
      expect(option).toHaveTextContent("Chat Input");
      expect(option).toHaveTextContent("Message");
    });
  });

  describe("filtering", () => {
    it("should filter options by node name", () => {
      render(<ReferenceAutocomplete {...defaultProps} filter="Chat" />);

      expect(
        screen.getByTestId("reference-option-ChatInput-message"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("reference-option-TextSplitter-chunks"),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByTestId("reference-option-APIRequest-response"),
      ).not.toBeInTheDocument();
    });

    it("should filter options by output name", () => {
      render(<ReferenceAutocomplete {...defaultProps} filter="message" />);

      expect(
        screen.getByTestId("reference-option-ChatInput-message"),
      ).toBeInTheDocument();
      expect(
        screen.queryByTestId("reference-option-TextSplitter-chunks"),
      ).not.toBeInTheDocument();
    });

    it("should be case insensitive", () => {
      render(<ReferenceAutocomplete {...defaultProps} filter="chat" />);

      expect(
        screen.getByTestId("reference-option-ChatInput-message"),
      ).toBeInTheDocument();
    });

    it("should match partial text", () => {
      render(<ReferenceAutocomplete {...defaultProps} filter="API" />);

      expect(
        screen.getByTestId("reference-option-APIRequest-response"),
      ).toBeInTheDocument();
    });
  });

  describe("selection", () => {
    it("should call onSelect when option is clicked", () => {
      const onSelect = jest.fn();
      render(<ReferenceAutocomplete {...defaultProps} onSelect={onSelect} />);

      const option = screen.getByTestId("reference-option-ChatInput-message");
      fireEvent.mouseDown(option);

      expect(onSelect).toHaveBeenCalledWith(mockOptions[0]);
    });

    it("should highlight first option by default", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      const firstOption = screen.getByTestId(
        "reference-option-ChatInput-message",
      );
      expect(firstOption).toHaveClass("bg-muted");
    });
  });

  describe("keyboard navigation", () => {
    it("should select next option on ArrowDown", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      fireEvent.keyDown(document, { key: "ArrowDown" });

      const secondOption = screen.getByTestId(
        "reference-option-TextSplitter-chunks",
      );
      expect(secondOption).toHaveClass("bg-muted");
    });

    it("should select previous option on ArrowUp", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      // Move down first
      fireEvent.keyDown(document, { key: "ArrowDown" });
      fireEvent.keyDown(document, { key: "ArrowDown" });

      // Now move up
      fireEvent.keyDown(document, { key: "ArrowUp" });

      const secondOption = screen.getByTestId(
        "reference-option-TextSplitter-chunks",
      );
      expect(secondOption).toHaveClass("bg-muted");
    });

    it("should not go below last option", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      // Press ArrowDown many times
      for (let i = 0; i < 10; i++) {
        fireEvent.keyDown(document, { key: "ArrowDown" });
      }

      const lastOption = screen.getByTestId(
        "reference-option-APIRequest-response",
      );
      expect(lastOption).toHaveClass("bg-muted");
    });

    it("should not go above first option", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      // Press ArrowUp when at first option
      fireEvent.keyDown(document, { key: "ArrowUp" });

      const firstOption = screen.getByTestId(
        "reference-option-ChatInput-message",
      );
      expect(firstOption).toHaveClass("bg-muted");
    });

    it("should call onSelect on Enter", () => {
      const onSelect = jest.fn();
      render(<ReferenceAutocomplete {...defaultProps} onSelect={onSelect} />);

      fireEvent.keyDown(document, { key: "Enter" });

      expect(onSelect).toHaveBeenCalledWith(mockOptions[0]);
    });

    it("should select correct option on Enter after navigation", () => {
      const onSelect = jest.fn();
      render(<ReferenceAutocomplete {...defaultProps} onSelect={onSelect} />);

      fireEvent.keyDown(document, { key: "ArrowDown" });
      fireEvent.keyDown(document, { key: "Enter" });

      expect(onSelect).toHaveBeenCalledWith(mockOptions[1]);
    });

    it("should call onClose on Escape", () => {
      const onClose = jest.fn();
      render(<ReferenceAutocomplete {...defaultProps} onClose={onClose} />);

      fireEvent.keyDown(document, { key: "Escape" });

      expect(onClose).toHaveBeenCalled();
    });

    it("should reset selection index when filter changes", () => {
      const { rerender } = render(<ReferenceAutocomplete {...defaultProps} />);

      // Move selection down
      fireEvent.keyDown(document, { key: "ArrowDown" });
      fireEvent.keyDown(document, { key: "ArrowDown" });

      // Change filter
      rerender(<ReferenceAutocomplete {...defaultProps} filter="Chat" />);

      // First (and only) option should be selected
      const firstOption = screen.getByTestId(
        "reference-option-ChatInput-message",
      );
      expect(firstOption).toHaveClass("bg-muted");
    });

    it("should not respond to keyboard events when closed", () => {
      const onSelect = jest.fn();
      render(
        <ReferenceAutocomplete
          {...defaultProps}
          isOpen={false}
          onSelect={onSelect}
        />,
      );

      fireEvent.keyDown(document, { key: "Enter" });

      expect(onSelect).not.toHaveBeenCalled();
    });
  });

  describe("positioning", () => {
    it("should use absolute positioning by default", () => {
      render(<ReferenceAutocomplete {...defaultProps} />);

      const dropdown = screen.getByTestId("reference-autocomplete-dropdown");
      expect(dropdown).toHaveClass("absolute");
    });

    it("should use textarea positioning when isTextarea is true", () => {
      render(<ReferenceAutocomplete {...defaultProps} isTextarea={true} />);

      const dropdown = screen.getByTestId("reference-autocomplete-dropdown");
      expect(dropdown).toHaveStyle({ top: "100px", left: "50px" });
    });

    it("should use bottom positioning for inputs", () => {
      render(<ReferenceAutocomplete {...defaultProps} isTextarea={false} />);

      const dropdown = screen.getByTestId("reference-autocomplete-dropdown");
      expect(dropdown).toHaveStyle({ top: "100%", left: "0px" });
    });
  });

  describe("edge cases", () => {
    it("should handle empty options array", () => {
      render(<ReferenceAutocomplete {...defaultProps} options={[]} />);

      expect(
        screen.queryByTestId("reference-autocomplete-dropdown"),
      ).not.toBeInTheDocument();
    });

    it("should handle single option", () => {
      render(
        <ReferenceAutocomplete {...defaultProps} options={[mockOptions[0]]} />,
      );

      expect(
        screen.getByTestId("reference-option-ChatInput-message"),
      ).toBeInTheDocument();
    });

    it("should cleanup keyboard event listener on unmount", () => {
      const removeEventListenerSpy = jest.spyOn(
        document,
        "removeEventListener",
      );
      const { unmount } = render(<ReferenceAutocomplete {...defaultProps} />);

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        "keydown",
        expect.any(Function),
      );

      removeEventListenerSpy.mockRestore();
    });
  });
});
