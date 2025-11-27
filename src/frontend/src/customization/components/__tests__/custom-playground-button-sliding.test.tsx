import { fireEvent, render, screen } from "@testing-library/react";
import {
  type SlidingContainerStoreType,
  useSlidingContainerStore,
} from "../../stores/sliding-container-store";
import { PlaygroundButtonSliding } from "../custom-playground-button-sliding";

// Mock the sliding container store
jest.mock("../../stores/sliding-container-store", () => ({
  useSlidingContainerStore: jest.fn(),
}));

// Mock the icon component
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <div data-testid={`icon-${name}`} className={className}>
      {name}
    </div>
  ),
}));

// Mock the tooltip component
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content: string;
  }) => (
    <div data-testid="tooltip" data-content={content}>
      {children}
    </div>
  ),
}));

// Mock constants
jest.mock("@/constants/constants", () => ({
  PLAYGROUND_BUTTON_NAME: "Playground",
}));

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_PUBLISH: false,
}));

const mockUseSlidingContainerStore =
  useSlidingContainerStore as jest.MockedFunction<
    typeof useSlidingContainerStore
  >;

describe("PlaygroundButtonSliding", () => {
  const mockToggle = jest.fn();
  const mockIsOpen = false;

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseSlidingContainerStore.mockImplementation((selector) => {
      const state: Partial<SlidingContainerStoreType> = {
        isOpen: mockIsOpen,
        toggle: mockToggle,
      };
      return selector(state as SlidingContainerStoreType);
    });
  });

  describe("when hasIO is true", () => {
    it("should render the button with Play icon when closed", () => {
      mockUseSlidingContainerStore.mockImplementation((selector) => {
        const state: Partial<SlidingContainerStoreType> = {
          isOpen: false,
          toggle: mockToggle,
        };
        return selector(state as SlidingContainerStoreType);
      });

      render(<PlaygroundButtonSliding hasIO={true} />);

      expect(
        screen.getByTestId("playground-btn-flow-io-sliding"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("icon-Play")).toBeInTheDocument();
      expect(screen.getByText("Playground")).toBeInTheDocument();
    });

    it("should render the button with PanelRightClose icon when open", () => {
      mockUseSlidingContainerStore.mockImplementation((selector) => {
        const state: Partial<SlidingContainerStoreType> = {
          isOpen: true,
          toggle: mockToggle,
        };
        return selector(state as SlidingContainerStoreType);
      });

      render(<PlaygroundButtonSliding hasIO={true} />);

      expect(
        screen.getByTestId("playground-btn-flow-io-sliding"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("icon-PanelRightClose")).toBeInTheDocument();
      expect(screen.getByText("Playground")).toBeInTheDocument();
    });

    it("should call toggle when clicked", () => {
      mockUseSlidingContainerStore.mockImplementation((selector) => {
        const state: Partial<SlidingContainerStoreType> = {
          isOpen: false,
          toggle: mockToggle,
        };
        return selector(state as SlidingContainerStoreType);
      });

      render(<PlaygroundButtonSliding hasIO={true} />);

      const button = screen.getByTestId("playground-btn-flow-io-sliding");
      fireEvent.click(button);

      expect(mockToggle).toHaveBeenCalledTimes(1);
    });

    it("should have hover styles when hasIO is true", () => {
      render(<PlaygroundButtonSliding hasIO={true} />);

      const button = screen.getByTestId("playground-btn-flow-io-sliding");
      expect(button).toHaveClass("hover:bg-accent", "cursor-pointer");
    });
  });

  describe("when hasIO is false", () => {
    it("should render disabled button with tooltip", () => {
      render(<PlaygroundButtonSliding hasIO={false} />);

      expect(
        screen.getByTestId("playground-btn-flow-sliding"),
      ).toBeInTheDocument();
      expect(screen.getByTestId("tooltip")).toBeInTheDocument();
      expect(screen.getByTestId("tooltip")).toHaveAttribute(
        "data-content",
        "Add a Chat Input or Chat Output to use the playground",
      );
    });

    it("should show Play icon when disabled", () => {
      render(<PlaygroundButtonSliding hasIO={false} />);

      expect(screen.getByTestId("icon-Play")).toBeInTheDocument();
    });

    it("should have disabled styles", () => {
      render(<PlaygroundButtonSliding hasIO={false} />);

      const button = screen.getByTestId("playground-btn-flow-sliding");
      expect(button).toHaveClass("cursor-not-allowed", "text-muted-foreground");
    });

    it("should not call toggle when clicked (disabled)", () => {
      render(<PlaygroundButtonSliding hasIO={false} />);

      const button = screen.getByTestId("playground-btn-flow-sliding");
      fireEvent.click(button);

      expect(mockToggle).not.toHaveBeenCalled();
    });
  });

  describe("icon rendering", () => {
    it("should apply correct icon classes", () => {
      render(<PlaygroundButtonSliding hasIO={true} />);

      const icon = screen.getByTestId("icon-Play");
      expect(icon).toHaveClass("h-4", "w-4", "transition-all", "flex-shrink-0");
    });
  });

  describe("label visibility", () => {
    it("should render label with hidden md:block classes", () => {
      render(<PlaygroundButtonSliding hasIO={true} />);

      const label = screen.getByText("Playground");
      expect(label).toHaveClass("hidden", "md:block");
    });
  });
});
