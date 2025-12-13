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
  default: ({ name }: { name: string }) => (
    <div data-testid={`icon-${name}`}>{name}</div>
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

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("when hasIO is true", () => {
    it("should render with Play icon when closed", () => {
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
    });

    it("should render with PanelRightClose icon when open", () => {
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

    it("should not call toggle when clicked (disabled)", () => {
      render(<PlaygroundButtonSliding hasIO={false} />);

      const button = screen.getByTestId("playground-btn-flow-sliding");
      fireEvent.click(button);

      expect(mockToggle).not.toHaveBeenCalled();
    });
  });
});
