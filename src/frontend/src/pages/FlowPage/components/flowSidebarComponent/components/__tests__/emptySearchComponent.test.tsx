import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NoResultsMessage from "../emptySearchComponent";

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: true, // Set to true for SearchConfigTrigger tests
}));

// Mock the SearchConfigTrigger component
jest.mock("../searchConfigTrigger", () => ({
  SearchConfigTrigger: ({
    showConfig,
    setShowConfig,
  }: {
    showConfig: boolean;
    setShowConfig: (showConfig: boolean) => void;
  }) => (
    <button
      data-testid="search-config-trigger"
      onClick={() => setShowConfig(!showConfig)}
    >
      Config Toggle: {showConfig.toString()}
    </button>
  ),
}));

describe("NoResultsMessage", () => {
  const mockOnClearSearch = jest.fn();
  const mockSetShowConfig = jest.fn();

  const defaultProps = {
    onClearSearch: mockOnClearSearch,
  };

  const defaultPropsWithConfig = {
    onClearSearch: mockOnClearSearch,
    showConfig: false,
    setShowConfig: mockSetShowConfig,
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
    it("should call onClearSearch when the clear action is clicked", async () => {
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

    it("should activate the clear action from the keyboard", async () => {
      const user = userEvent.setup();
      render(<NoResultsMessage {...defaultProps} />);

      const clearButton = screen.getByRole("button", {
        name: "Clear your search",
      });
      clearButton.focus();
      await user.keyboard("{Enter}");

      expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
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
    it("should render the clear action as a semantic button", () => {
      render(<NoResultsMessage {...defaultProps} />);

      expect(
        screen.getByRole("button", { name: "Clear your search" }),
      ).toBeInTheDocument();
    });

    it("should hide the clear action for a policy empty state", () => {
      render(
        <NoResultsMessage
          {...defaultProps}
          message="No components are available under policy."
          showClearSearch={false}
        />,
      );

      expect(
        screen.getByText("No components are available under policy."),
      ).toBeInTheDocument();
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
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
        onClearSearch: undefined,
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

  describe("SearchConfigTrigger Integration", () => {
    describe("When ENABLE_NEW_SIDEBAR is true", () => {
      it("should not render SearchConfigTrigger when setShowConfig is not provided", () => {
        render(<NoResultsMessage {...defaultProps} />);

        expect(
          screen.queryByTestId("search-config-trigger"),
        ).not.toBeInTheDocument();
      });

      it("should render SearchConfigTrigger when setShowConfig is provided", () => {
        render(<NoResultsMessage {...defaultPropsWithConfig} />);

        expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
        expect(screen.getByText("Config Toggle: false")).toBeInTheDocument();
      });

      it("should render SearchConfigTrigger with showConfig true", () => {
        const propsWithShowConfig = {
          ...defaultPropsWithConfig,
          showConfig: true,
        };

        render(<NoResultsMessage {...propsWithShowConfig} />);

        expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();
        expect(screen.getByText("Config Toggle: true")).toBeInTheDocument();
      });

      it("should maintain proper layout with SearchConfigTrigger", () => {
        const { container } = render(
          <NoResultsMessage {...defaultPropsWithConfig} />,
        );

        // SearchConfigTrigger should be in absolute positioned container
        expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();

        // Main content div should still be centered
        const mainContentDiv = container.querySelector(
          ".flex.h-full.flex-col.items-center.justify-center",
        );
        expect(mainContentDiv).toBeInTheDocument();
        expect(mainContentDiv).toHaveClass(
          "flex",
          "h-full",
          "flex-col",
          "items-center",
          "justify-center",
          "p-3",
          "text-center",
        );
      });

      it("should call setShowConfig when SearchConfigTrigger is clicked", async () => {
        const user = userEvent.setup();
        render(<NoResultsMessage {...defaultPropsWithConfig} />);

        const configTrigger = screen.getByTestId("search-config-trigger");
        await user.click(configTrigger);

        expect(mockSetShowConfig).toHaveBeenCalledWith(true);
        expect(mockSetShowConfig).toHaveBeenCalledTimes(1);
      });

      it("should not interfere with clear search functionality", async () => {
        const user = userEvent.setup();
        render(<NoResultsMessage {...defaultPropsWithConfig} />);

        // SearchConfigTrigger should work
        const configTrigger = screen.getByTestId("search-config-trigger");
        await user.click(configTrigger);
        expect(mockSetShowConfig).toHaveBeenCalledTimes(1);

        // Clear search should still work
        const clearLink = screen.getByText("Clear your search");
        await user.click(clearLink);
        expect(mockOnClearSearch).toHaveBeenCalledTimes(1);
      });
    });

    describe("Component Structure with SearchConfigTrigger", () => {
      it("should have relative positioning container as root", () => {
        const { container } = render(
          <NoResultsMessage {...defaultPropsWithConfig} />,
        );

        const rootDiv = container.firstChild as HTMLElement;
        expect(rootDiv).toHaveClass("flex", "h-full", "flex-col", "relative");
      });

      it("should render both SearchConfigTrigger and main content", () => {
        render(<NoResultsMessage {...defaultPropsWithConfig} />);

        // SearchConfigTrigger should be present
        expect(screen.getByTestId("search-config-trigger")).toBeInTheDocument();

        // Main content should still be present using partial text matching
        expect(screen.getByText(/No components found/)).toBeInTheDocument();
        expect(screen.getByText("Clear your search")).toBeInTheDocument();
      });

      it("should handle custom props with SearchConfigTrigger", () => {
        const customPropsWithConfig = {
          ...defaultPropsWithConfig,
          message: "Custom message with config",
          clearSearchText: "Custom clear",
          additionalText: "Custom additional",
          showConfig: true,
        };

        const { container } = render(
          <NoResultsMessage {...customPropsWithConfig} />,
        );

        // SearchConfigTrigger should be present and show correct state
        expect(screen.getByText("Config Toggle: true")).toBeInTheDocument();

        // Custom text should be rendered
        expect(container.textContent).toContain("Custom message with config");
        expect(screen.getByText("Custom clear")).toBeInTheDocument();
        expect(container.textContent).toContain("Custom additional");
      });
    });
  });
});
