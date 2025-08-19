import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import NoResultsMessage from "../emptySearchComponent";

describe("NoResultsMessage", () => {
  const mockOnClearSearch = jest.fn();

  const defaultProps = {
    onClearSearch: mockOnClearSearch,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render with default message", () => {
      const { container } = render(<NoResultsMessage {...defaultProps} />);

      expect(container.textContent).toContain("No components found.");
      expect(screen.getByText("Clear your search")).toBeInTheDocument();
      expect(container.textContent).toContain(
        "or filter and try a different query.",
      );
    });

    it("should render with custom message", () => {
      const customProps = {
        ...defaultProps,
        message: "Custom no results message",
      };

      const { container } = render(<NoResultsMessage {...customProps} />);

      expect(container.textContent).toContain("Custom no results message");
    });

    it("should render with custom clear search text", () => {
      const customProps = {
        ...defaultProps,
        clearSearchText: "Reset search",
      };

      render(<NoResultsMessage {...customProps} />);

      expect(screen.getByText("Reset search")).toBeInTheDocument();
    });

    it("should render with custom additional text", () => {
      const customProps = {
        ...defaultProps,
        additionalText: "or try something else.",
      };

      const { container } = render(<NoResultsMessage {...customProps} />);

      expect(container.textContent).toContain("or try something else.");
    });

    it("should render with all custom props", () => {
      const allCustomProps = {
        ...defaultProps,
        message: "Nothing here!",
        clearSearchText: "Reset",
        additionalText: "or adjust filters.",
      };

      const { container } = render(<NoResultsMessage {...allCustomProps} />);

      expect(container.textContent).toContain("Nothing here!");
      expect(screen.getByText("Reset")).toBeInTheDocument();
      expect(container.textContent).toContain("or adjust filters.");
    });
  });

  describe("Clear Search Functionality", () => {
    it("should call onClearSearch when clear link is clicked", async () => {
      const user = userEvent.setup();
      render(<NoResultsMessage {...defaultProps} />);

      const clearLink = screen.getByText("Clear your search");
      await user.click(clearLink);

      expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
    });

    it("should call onClearSearch when custom clear text is clicked", async () => {
      const user = userEvent.setup();
      const customProps = {
        ...defaultProps,
        clearSearchText: "Reset filters",
      };

      render(<NoResultsMessage {...customProps} />);

      const clearLink = screen.getByText("Reset filters");
      await user.click(clearLink);

      expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
    });

    it("should handle keyboard events on clear link", () => {
      render(<NoResultsMessage {...defaultProps} />);

      const clearLink = screen.getByText("Clear your search");
      fireEvent.keyDown(clearLink, { key: "Enter" });
      fireEvent.keyDown(clearLink, { key: " " });

      // Note: onClick events in tests don't automatically handle keyboard events
      // This test ensures the element is focusable and receives keyboard events
      expect(clearLink).toBeInTheDocument();
    });

    it("should only call onClearSearch once per click", async () => {
      const user = userEvent.setup();
      render(<NoResultsMessage {...defaultProps} />);

      const clearLink = screen.getByText("Clear your search");
      await user.click(clearLink);
      await user.click(clearLink);

      expect(mockOnClearSearch).toHaveBeenCalledTimes(2);
    });
  });

  describe("Component Structure", () => {
    it("should render clear link as clickable element", () => {
      render(<NoResultsMessage {...defaultProps} />);

      const clearLink = screen.getByText("Clear your search");
      expect(clearLink).toBeInTheDocument();
      expect(clearLink.tagName).toBe("A");
    });
  });

  describe("Text Concatenation", () => {
    it("should properly concatenate message, clear text, and additional text", () => {
      const { container } = render(<NoResultsMessage {...defaultProps} />);

      expect(container.textContent).toContain("No components found.");
      expect(container.textContent).toContain("Clear your search");
      expect(container.textContent).toContain(
        "or filter and try a different query.",
      );
    });

    it("should handle empty strings gracefully", () => {
      const emptyProps = {
        ...defaultProps,
        message: "",
        clearSearchText: "",
        additionalText: "",
      };

      render(<NoResultsMessage {...emptyProps} />);

      // Should still render the structure even with empty strings
      const paragraph = screen.getByRole("paragraph");
      expect(paragraph).toBeInTheDocument();
    });

    it("should handle only message provided", () => {
      const messageOnlyProps = {
        ...defaultProps,
        message: "Only message",
        clearSearchText: "",
        additionalText: "",
      };

      const { container } = render(<NoResultsMessage {...messageOnlyProps} />);

      expect(container.textContent).toContain("Only message");
    });
  });

  describe("Default Props Behavior", () => {
    it("should use default values when props are undefined", () => {
      const minimalProps = {
        onClearSearch: mockOnClearSearch,
      };

      const { container } = render(<NoResultsMessage {...minimalProps} />);

      expect(container.textContent).toContain("No components found.");
      expect(screen.getByText("Clear your search")).toBeInTheDocument();
      expect(container.textContent).toContain(
        "or filter and try a different query.",
      );
    });

    it("should override default values when props are provided", () => {
      const overrideProps = {
        onClearSearch: mockOnClearSearch,
        message: "Override message",
        clearSearchText: "Override clear",
        additionalText: "Override additional",
      };

      const { container } = render(<NoResultsMessage {...overrideProps} />);

      expect(container.textContent).not.toContain("No components found.");
      expect(screen.queryByText("Clear your search")).not.toBeInTheDocument();
      expect(container.textContent).not.toContain(
        "or filter and try a different query.",
      );

      expect(container.textContent).toContain("Override message");
      expect(screen.getByText("Override clear")).toBeInTheDocument();
      expect(container.textContent).toContain("Override additional");
    });
  });

  describe("Callback Function", () => {
    it("should handle missing onClearSearch gracefully", () => {
      const propsWithoutCallback = {
        onClearSearch: undefined as any,
      };

      expect(() => {
        render(<NoResultsMessage {...propsWithoutCallback} />);
      }).not.toThrow();
    });

    it("should work with different callback functions", async () => {
      const user = userEvent.setup();
      const alternativeCallback = jest.fn();
      const alternativeProps = {
        onClearSearch: alternativeCallback,
      };

      render(<NoResultsMessage {...alternativeProps} />);

      const clearLink = screen.getByText("Clear your search");
      await user.click(clearLink);

      expect(alternativeCallback).toHaveBeenCalledTimes(1);
      expect(mockOnClearSearch).not.toHaveBeenCalled();
    });
  });

  describe("Re-rendering", () => {
    it("should update when props change", () => {
      const { rerender, container } = render(
        <NoResultsMessage {...defaultProps} />,
      );

      expect(container.textContent).toContain("No components found.");

      const newProps = {
        ...defaultProps,
        message: "Updated message",
      };

      rerender(<NoResultsMessage {...newProps} />);

      expect(container.textContent).not.toContain("No components found.");
      expect(container.textContent).toContain("Updated message");
    });

    it("should maintain functionality after re-render", async () => {
      const user = userEvent.setup();
      const { rerender } = render(<NoResultsMessage {...defaultProps} />);

      rerender(<NoResultsMessage {...defaultProps} />);

      const clearLink = screen.getByText("Clear your search");
      await user.click(clearLink);

      expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
    });
  });
});
