import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ModelProviderEdit from "../components/ModelProviderEdit";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

// Mock PROVIDER_VARIABLE_MAPPING
jest.mock("@/constants/providerConstants", () => ({
  PROVIDER_VARIABLE_MAPPING: {
    OpenAI: "OPENAI_API_KEY",
    Anthropic: "ANTHROPIC_API_KEY",
    Cohere: "COHERE_API_KEY",
  },
}));

const defaultProps = {
  authName: "",
  onAuthNameChange: jest.fn(),
  apiKey: "",
  onApiKeyChange: jest.fn(),
  apiBase: "",
  onApiBaseChange: jest.fn(),
};

describe("ModelProviderEdit", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render the component container", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      expect(screen.getByTestId("model-provider-edit")).toBeInTheDocument();
    });

    it("should render Authorization Name input", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      // Check for the label (may have multiple due to placeholder)
      expect(screen.getByTestId("auth-name-input")).toBeInTheDocument();
    });

    it("should render API Key input with required indicator", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      expect(screen.getByText("API Key")).toBeInTheDocument();
      expect(screen.getByText("*")).toBeInTheDocument();
      expect(screen.getByTestId("api-key-input")).toBeInTheDocument();
    });

    it("should render API Base input", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      expect(screen.getByText("API Base")).toBeInTheDocument();
      expect(screen.getByTestId("api-base-input")).toBeInTheDocument();
    });

    it("should render Find your API key link", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      expect(screen.getByText(/Find your API key/)).toBeInTheDocument();
    });

    it("should display provider-specific variable name when providerName is set", () => {
      render(<ModelProviderEdit {...defaultProps} providerName="OpenAI" />);

      const authInput = screen.getByTestId("auth-name-input");
      expect(authInput).toHaveValue("OPENAI_API_KEY");
    });

    it("should display UNKNOWN_API_KEY when providerName is not set", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      const authInput = screen.getByTestId("auth-name-input");
      expect(authInput).toHaveValue("UNKNOWN_API_KEY");
    });
  });

  describe("Input Interactions", () => {
    it("should call onApiKeyChange when API key is entered", async () => {
      const onApiKeyChange = jest.fn();
      const user = userEvent.setup();

      render(
        <ModelProviderEdit {...defaultProps} onApiKeyChange={onApiKeyChange} />,
      );

      const apiKeyInput = screen.getByTestId("api-key-input");
      await user.type(apiKeyInput, "sk-test-key");

      expect(onApiKeyChange).toHaveBeenCalled();
    });

    it("should call onApiBaseChange when API base is entered", async () => {
      const onApiBaseChange = jest.fn();
      const user = userEvent.setup();

      render(
        <ModelProviderEdit
          {...defaultProps}
          onApiBaseChange={onApiBaseChange}
        />,
      );

      const apiBaseInput = screen.getByTestId("api-base-input");
      await user.type(apiBaseInput, "https://api.example.com");

      expect(onApiBaseChange).toHaveBeenCalled();
    });

    it("should display provided values in inputs", () => {
      render(
        <ModelProviderEdit
          {...defaultProps}
          apiKey="my-api-key"
          apiBase="https://custom.api.com"
        />,
      );

      expect(screen.getByTestId("api-key-input")).toHaveValue("my-api-key");
      expect(screen.getByTestId("api-base-input")).toHaveValue(
        "https://custom.api.com",
      );
    });
  });

  describe("Input States", () => {
    it("should have auth name input disabled", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      const authInput = screen.getByTestId("auth-name-input");
      expect(authInput).toBeDisabled();
    });

    it("should have API key input as password type", () => {
      render(<ModelProviderEdit {...defaultProps} />);

      const apiKeyInput = screen.getByTestId("api-key-input");
      expect(apiKeyInput).toHaveAttribute("type", "password");
    });
  });
});
