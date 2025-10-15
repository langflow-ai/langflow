import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import FeatureToggles from "../featureTogglesComponent";

// Mock the UI components
jest.mock("@/components/ui/badge", () => ({
  Badge: ({ children, variant, size }: any) => (
    <span
      data-testid={`badge-${variant}-${size}`}
      className={`badge-${variant} badge-${size}`}
    >
      {children}
    </span>
  ),
}));

jest.mock("@/components/ui/switch", () => ({
  Switch: ({ checked, onCheckedChange, "data-testid": testId }: any) => (
    <button
      data-testid={testId || "switch"}
      onClick={() => onCheckedChange(!checked)}
      aria-checked={checked}
      role="switch"
    >
      {checked ? "ON" : "OFF"}
    </button>
  ),
}));

describe("FeatureToggles", () => {
  const mockSetShowBeta = jest.fn();
  const mockSetShowLegacy = jest.fn();

  const defaultProps = {
    showBeta: false,
    setShowBeta: mockSetShowBeta,
    showLegacy: false,
    setShowLegacy: mockSetShowLegacy,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Basic Rendering", () => {
    it("should render both toggle sections", () => {
      render(<FeatureToggles {...defaultProps} />);

      // Allow multiple instances of "Show" to pass
      expect(screen.getAllByText("Show").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByTestId("badge-purpleStatic-xq")).toHaveTextContent(
        "Beta",
      );
      expect(screen.getByTestId("badge-secondaryStatic-xq")).toHaveTextContent(
        "Legacy",
      );
    });

    it("should render Beta toggle with correct elements", () => {
      render(<FeatureToggles {...defaultProps} />);

      expect(screen.getByTestId("badge-purpleStatic-xq")).toHaveTextContent(
        "Beta",
      );
      expect(screen.getByTestId("sidebar-beta-switch")).toBeInTheDocument();
    });

    it("should render Legacy toggle with correct elements", () => {
      render(<FeatureToggles {...defaultProps} />);

      expect(screen.getByTestId("badge-secondaryStatic-xq")).toHaveTextContent(
        "Legacy",
      );
      expect(screen.getByTestId("sidebar-legacy-switch")).toBeInTheDocument();
    });

    it("should render correct number of toggle sections", () => {
      render(<FeatureToggles {...defaultProps} />);

      const toggleSections = screen.getAllByText("Show");
      expect(toggleSections).toHaveLength(2);
    });
  });

  describe("Switch States", () => {
    it("should show Beta switch as OFF when showBeta is false", () => {
      render(<FeatureToggles {...defaultProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      expect(betaSwitch).toHaveAttribute("aria-checked", "false");
      expect(betaSwitch).toHaveTextContent("OFF");
    });

    it("should show Beta switch as ON when showBeta is true", () => {
      const propsWithBetaOn = { ...defaultProps, showBeta: true };
      render(<FeatureToggles {...propsWithBetaOn} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      expect(betaSwitch).toHaveAttribute("aria-checked", "true");
      expect(betaSwitch).toHaveTextContent("ON");
    });

    it("should show Legacy switch as OFF when showLegacy is false", () => {
      render(<FeatureToggles {...defaultProps} />);

      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");
      expect(legacySwitch).toHaveAttribute("aria-checked", "false");
      expect(legacySwitch).toHaveTextContent("OFF");
    });

    it("should show Legacy switch as ON when showLegacy is true", () => {
      const propsWithLegacyOn = { ...defaultProps, showLegacy: true };
      render(<FeatureToggles {...propsWithLegacyOn} />);

      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");
      expect(legacySwitch).toHaveAttribute("aria-checked", "true");
      expect(legacySwitch).toHaveTextContent("ON");
    });

    it("should handle both switches being ON", () => {
      const propsWithBothOn = {
        ...defaultProps,
        showBeta: true,
        showLegacy: true,
      };
      render(<FeatureToggles {...propsWithBothOn} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");

      expect(betaSwitch).toHaveAttribute("aria-checked", "true");
      expect(legacySwitch).toHaveAttribute("aria-checked", "true");
    });
  });

  describe("Beta Toggle Functionality", () => {
    it("should call setShowBeta with true when Beta switch is clicked while OFF", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      await user.click(betaSwitch);

      expect(mockSetShowBeta).toHaveBeenCalledWith(true);
    });

    it("should call setShowBeta with false when Beta switch is clicked while ON", async () => {
      const user = userEvent.setup();
      const propsWithBetaOn = { ...defaultProps, showBeta: true };
      render(<FeatureToggles {...propsWithBetaOn} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      await user.click(betaSwitch);

      expect(mockSetShowBeta).toHaveBeenCalledWith(false);
    });

    it("should only call setShowBeta once per click", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      await user.click(betaSwitch);

      expect(mockSetShowBeta).toHaveBeenCalledTimes(1);
    });

    it("should not affect Legacy switch when Beta is clicked", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      await user.click(betaSwitch);

      expect(mockSetShowLegacy).not.toHaveBeenCalled();
    });
  });

  describe("Legacy Toggle Functionality", () => {
    it("should call setShowLegacy with true when Legacy switch is clicked while OFF", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");
      await user.click(legacySwitch);

      expect(mockSetShowLegacy).toHaveBeenCalledWith(true);
    });

    it("should call setShowLegacy with false when Legacy switch is clicked while ON", async () => {
      const user = userEvent.setup();
      const propsWithLegacyOn = { ...defaultProps, showLegacy: true };
      render(<FeatureToggles {...propsWithLegacyOn} />);

      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");
      await user.click(legacySwitch);

      expect(mockSetShowLegacy).toHaveBeenCalledWith(false);
    });

    it("should only call setShowLegacy once per click", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");
      await user.click(legacySwitch);

      expect(mockSetShowLegacy).toHaveBeenCalledTimes(1);
    });

    it("should not affect Beta switch when Legacy is clicked", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");
      await user.click(legacySwitch);

      expect(mockSetShowBeta).not.toHaveBeenCalled();
    });
  });

  describe("Independent Toggle Behavior", () => {
    it("should handle both switches being toggled independently", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");

      await user.click(betaSwitch);
      await user.click(legacySwitch);

      expect(mockSetShowBeta).toHaveBeenCalledWith(true);
      expect(mockSetShowLegacy).toHaveBeenCalledWith(true);
      expect(mockSetShowBeta).toHaveBeenCalledTimes(1);
      expect(mockSetShowLegacy).toHaveBeenCalledTimes(1);
    });

    it("should allow rapid toggling without interference", async () => {
      const user = userEvent.setup();

      const Controlled: React.FC = () => {
        const [beta, setBeta] = React.useState(false);
        const [legacy] = React.useState(false);
        return (
          <FeatureToggles
            showBeta={beta}
            setShowBeta={(value: boolean) => {
              setBeta(value);
              mockSetShowBeta(value);
            }}
            showLegacy={legacy}
            setShowLegacy={mockSetShowLegacy}
          />
        );
      };

      render(<Controlled />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");

      await user.click(betaSwitch);
      await user.click(betaSwitch);
      await user.click(betaSwitch);

      expect(mockSetShowBeta).toHaveBeenCalledTimes(3);
      expect(mockSetShowBeta).toHaveBeenNthCalledWith(1, true);
      expect(mockSetShowBeta).toHaveBeenNthCalledWith(2, false);
      expect(mockSetShowBeta).toHaveBeenNthCalledWith(3, true);
    });
  });

  describe("Badge Configuration", () => {
    it("should render Beta badge with correct variant and size", () => {
      render(<FeatureToggles {...defaultProps} />);

      const betaBadge = screen.getByTestId("badge-purpleStatic-xq");
      expect(betaBadge).toHaveTextContent("Beta");
      expect(betaBadge).toHaveClass("badge-purpleStatic", "badge-xq");
    });

    it("should render Legacy badge with correct variant and size", () => {
      render(<FeatureToggles {...defaultProps} />);

      const legacyBadge = screen.getByTestId("badge-secondaryStatic-xq");
      expect(legacyBadge).toHaveTextContent("Legacy");
      expect(legacyBadge).toHaveClass("badge-secondaryStatic", "badge-xq");
    });
  });

  describe("Component Structure", () => {
    it("should render toggles in correct order", () => {
      render(<FeatureToggles {...defaultProps} />);

      const badges = screen.getAllByTestId(/^badge-/);
      expect(badges[0]).toHaveTextContent("Beta");
      expect(badges[1]).toHaveTextContent("Legacy");
    });

    it("should have switches with correct test IDs", () => {
      render(<FeatureToggles {...defaultProps} />);

      expect(screen.getByTestId("sidebar-beta-switch")).toBeInTheDocument();
      expect(screen.getByTestId("sidebar-legacy-switch")).toBeInTheDocument();
    });
  });

  describe("Props Handling", () => {
    it("should handle missing callback functions gracefully", () => {
      const propsWithoutCallbacks = {
        showBeta: false,
        setShowBeta: undefined as any,
        showLegacy: false,
        setShowLegacy: undefined as any,
      };

      expect(() => {
        render(<FeatureToggles {...propsWithoutCallbacks} />);
      }).not.toThrow();
    });

    it("should handle boolean state changes correctly", () => {
      const { rerender } = render(<FeatureToggles {...defaultProps} />);

      let betaSwitch = screen.getByTestId("sidebar-beta-switch");
      expect(betaSwitch).toHaveAttribute("aria-checked", "false");

      const newProps = { ...defaultProps, showBeta: true };
      rerender(<FeatureToggles {...newProps} />);

      betaSwitch = screen.getByTestId("sidebar-beta-switch");
      expect(betaSwitch).toHaveAttribute("aria-checked", "true");
    });
  });

  describe("User Interaction", () => {
    it("should respond to keyboard interactions on switches", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      // Tab to focus the switch and press Enter
      await user.tab();
      await user.keyboard("{Enter}");

      expect(mockSetShowBeta).toHaveBeenCalledWith(true);
    });

    it("should maintain focus behavior for accessibility", async () => {
      const user = userEvent.setup();
      render(<FeatureToggles {...defaultProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");

      await user.tab();
      expect(betaSwitch).toHaveFocus();

      await user.tab();
      expect(legacySwitch).toHaveFocus();
    });
  });

  describe("Edge Cases", () => {
    it("should render correctly with mixed initial states", () => {
      const mixedStateProps = {
        ...defaultProps,
        showBeta: true,
        showLegacy: false,
      };

      render(<FeatureToggles {...mixedStateProps} />);

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");

      expect(betaSwitch).toHaveAttribute("aria-checked", "true");
      expect(legacySwitch).toHaveAttribute("aria-checked", "false");
    });

    it("should handle rapid state changes", () => {
      const { rerender } = render(<FeatureToggles {...defaultProps} />);

      // Rapidly change states
      rerender(<FeatureToggles {...defaultProps} showBeta={true} />);
      rerender(<FeatureToggles {...defaultProps} showBeta={false} />);
      rerender(
        <FeatureToggles {...defaultProps} showBeta={true} showLegacy={true} />,
      );

      const betaSwitch = screen.getByTestId("sidebar-beta-switch");
      const legacySwitch = screen.getByTestId("sidebar-legacy-switch");

      expect(betaSwitch).toHaveAttribute("aria-checked", "true");
      expect(legacySwitch).toHaveAttribute("aria-checked", "true");
    });
  });
});
