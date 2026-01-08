import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProviderListItem from "../components/ProviderListItem";
import { Provider } from "../components/types";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  ForwardedIconComponent: ({
    name,
    className,
  }: {
    name: string;
    className?: string;
  }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

const mockEnabledProvider: Provider = {
  provider: "OpenAI",
  icon: "Bot",
  is_enabled: true,
  model_count: 5,
  models: [],
};

const mockDisabledProvider: Provider = {
  provider: "Anthropic",
  icon: "Brain",
  is_enabled: false,
  model_count: 3,
  models: [],
};

const mockProviderNoModels: Provider = {
  provider: "Empty",
  icon: "Bot",
  is_enabled: true,
  model_count: 0,
  models: [],
};

describe("ProviderListItem", () => {
  const defaultProps = {
    provider: mockEnabledProvider,
    onSelect: jest.fn(),
    isSelected: false,
    showIcon: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render the provider item", () => {
      render(<ProviderListItem {...defaultProps} />);

      expect(screen.getByTestId("provider-item-OpenAI")).toBeInTheDocument();
    });

    it("should display provider name", () => {
      render(<ProviderListItem {...defaultProps} />);

      expect(screen.getByText("OpenAI")).toBeInTheDocument();
    });

    it("should display model count badge for enabled provider", () => {
      render(<ProviderListItem {...defaultProps} />);

      expect(screen.getByText("5 models")).toBeInTheDocument();
    });

    it("should display singular 'model' for count of 1", () => {
      const providerWithOneModel = {
        ...mockEnabledProvider,
        model_count: 1,
      };

      render(
        <ProviderListItem {...defaultProps} provider={providerWithOneModel} />,
      );

      expect(screen.getByText("1 model")).toBeInTheDocument();
    });

    it("should not display model count for disabled provider", () => {
      render(
        <ProviderListItem {...defaultProps} provider={mockDisabledProvider} />,
      );

      expect(screen.queryByText(/models?$/)).not.toBeInTheDocument();
    });
  });

  describe("Selection State", () => {
    it("should apply selected styling when isSelected is true", () => {
      render(<ProviderListItem {...defaultProps} isSelected={true} />);

      const item = screen.getByTestId("provider-item-OpenAI");
      expect(item).toHaveClass("bg-muted/50");
    });

    it("should call onSelect when clicked", async () => {
      const onSelect = jest.fn();
      const user = userEvent.setup();

      render(<ProviderListItem {...defaultProps} onSelect={onSelect} />);

      const item = screen.getByTestId("provider-item-OpenAI");
      await user.click(item);

      expect(onSelect).toHaveBeenCalledWith(mockEnabledProvider);
    });
  });

  describe("Enabled/Disabled State", () => {
    it("should show check icon for enabled provider when showIcon is false", () => {
      render(<ProviderListItem {...defaultProps} />);

      expect(screen.getByTestId("icon-check")).toBeInTheDocument();
    });

    it("should show Plus icon for disabled provider when showIcon is false", () => {
      render(
        <ProviderListItem {...defaultProps} provider={mockDisabledProvider} />,
      );

      expect(screen.getByTestId("icon-Plus")).toBeInTheDocument();
    });

    it("should not show status icon when showIcon is true", () => {
      render(<ProviderListItem {...defaultProps} showIcon={true} />);

      expect(screen.queryByTestId("icon-check")).not.toBeInTheDocument();
      expect(screen.queryByTestId("icon-Plus")).not.toBeInTheDocument();
    });
  });

  describe("Cursor State", () => {
    it("should have pointer cursor for provider with models", () => {
      render(<ProviderListItem {...defaultProps} />);

      const item = screen.getByTestId("provider-item-OpenAI");
      expect(item).toHaveClass("cursor-pointer");
    });

    it("should have not-allowed cursor for provider without models", () => {
      render(
        <ProviderListItem {...defaultProps} provider={mockProviderNoModels} />,
      );

      const item = screen.getByTestId("provider-item-Empty");
      expect(item).toHaveClass("cursor-not-allowed");
    });
  });
});
