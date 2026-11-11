import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ProviderVariable } from "@/constants/providerConstants";
import ProviderConfigurationForm, {
  type ProviderConfigurationFormProps,
} from "../components/ProviderConfigurationForm";

const apiKeyVariable: ProviderVariable = {
  variable_name: "API Key",
  variable_key: "WATSONX_APIKEY",
  required: true,
  is_secret: true,
  is_list: false,
  options: [],
};
const projectVariable: ProviderVariable = {
  ...apiKeyVariable,
  variable_name: "Project ID",
  variable_key: "WATSONX_PROJECT_ID",
  is_secret: false,
};

const defaultProps: ProviderConfigurationFormProps = {
  selectedProvider: { provider: "IBM watsonx", is_enabled: false },
  providerVariables: [apiKeyVariable, projectVariable],
  variableValues: {},
  isVariableConfigured: () => false,
  getConfiguredValue: () => null,
  onVariableChange: jest.fn(),
  onSave: jest.fn(),
  onActivate: jest.fn(),
  onDisconnect: jest.fn(),
  isSaving: false,
  isPending: false,
  isDeleting: false,
  isFetchingModels: false,
  validationFailed: false,
  validationState: "idle",
  validationError: null,
  canSave: true,
  requiresConfiguration: true,
  isFetchingAfterDisconnect: false,
};

function ConfigurationHarness({
  isConfigured = false,
  providerVariables = defaultProps.providerVariables,
}: {
  isConfigured?: boolean;
  providerVariables?: ProviderVariable[];
}) {
  const [variableValues, setVariableValues] = useState<Record<string, string>>(
    {},
  );
  return (
    <TooltipProvider>
      <ProviderConfigurationForm
        {...defaultProps}
        providerVariables={providerVariables}
        isVariableConfigured={() => isConfigured}
        variableValues={variableValues}
        onVariableChange={(key, value) =>
          setVariableValues((previous) => ({ ...previous, [key]: value }))
        }
      />
    </TooltipProvider>
  );
}

const renderForm = (props: Partial<ProviderConfigurationFormProps> = {}) =>
  render(
    <TooltipProvider>
      <ProviderConfigurationForm {...defaultProps} {...props} />
    </TooltipProvider>,
  );

describe("ProviderConfigurationForm disclosure", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Element.prototype.scrollIntoView = jest.fn();
  });

  it("should render nothing when no provider is selected", () => {
    renderForm({ selectedProvider: null });

    expect(
      screen.queryByTestId("provider-configuration-disclosure"),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/API Key/)).not.toBeInTheDocument();
  });

  it("should expand configuration fields by default", () => {
    renderForm();

    expect(
      screen.getByTestId("provider-configuration-disclosure"),
    ).toHaveAttribute("open");
    expect(
      screen.getByTestId("provider-configuration-summary"),
    ).toHaveTextContent("IBM watsonx Configuration");
    expect(screen.getByLabelText(/API Key/)).toBeVisible();
    expect(screen.getByLabelText(/Project ID/)).toBeVisible();
  });

  it("should retain unsaved values when configuration is collapsed and reopened", async () => {
    const user = userEvent.setup();
    render(<ConfigurationHarness />);
    await user.type(screen.getByLabelText(/Project ID/), "unsaved-project");

    await user.click(screen.getByTestId("provider-configuration-summary"));
    expect(screen.getByLabelText(/Project ID/)).not.toBeVisible();
    await user.click(screen.getByTestId("provider-configuration-summary"));

    expect(screen.getByLabelText(/Project ID/)).toBeVisible();
    expect(screen.getByLabelText(/Project ID/)).toHaveValue("unsaved-project");
    expect(defaultProps.onSave).not.toHaveBeenCalled();
  });

  it("should retain a replacement credential when configuration is reopened", async () => {
    const user = userEvent.setup();
    render(<ConfigurationHarness isConfigured />);
    const input = screen.getByLabelText(/API Key/);
    await user.click(input);
    await user.type(input, "replacement-credential");

    await user.click(screen.getByTestId("provider-configuration-summary"));
    await user.click(screen.getByTestId("provider-configuration-summary"));

    expect(screen.getByLabelText(/API Key/)).toHaveValue(
      "replacement-credential",
    );
    expect(screen.getByLabelText(/API Key/)).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("should keep the single credential input named by the section heading", () => {
    renderForm({ providerVariables: [apiKeyVariable] });

    expect(screen.getByLabelText(/API Key/)).toBeVisible();
    expect(
      screen.getByTestId("provider-configuration-summary"),
    ).toHaveTextContent("API Key");
  });

  it("should keep activation available for providers with no configuration fields", async () => {
    const user = userEvent.setup();
    renderForm({
      selectedProvider: { provider: "Local Provider", is_enabled: false },
      providerVariables: [],
      requiresConfiguration: false,
    });
    await user.click(screen.getByTestId("provider-configuration-summary"));
    expect(
      screen.getByRole("button", {
        name: /Activate Local Provider/,
        hidden: true,
      }),
    ).not.toBeVisible();

    await user.click(screen.getByTestId("provider-configuration-summary"));
    await user.click(
      screen.getByRole("button", { name: /Activate Local Provider/ }),
    );

    expect(defaultProps.onActivate).toHaveBeenCalledTimes(1);
  });

  it("should retain validation errors when invalid configuration is reopened", async () => {
    const user = userEvent.setup();
    renderForm({
      providerVariables: [
        apiKeyVariable,
        { ...projectVariable, required: false },
      ],
      selectedProvider: {
        ...defaultProps.selectedProvider!,
        api_docs_url: "https://example.com/credentials",
      },
      validationState: "invalid",
      validationFailed: true,
      validationError: "Invalid provider credentials",
    });

    await user.click(screen.getByTestId("provider-configuration-summary"));
    expect(screen.getByRole("alert", { hidden: true })).not.toBeVisible();
    await user.click(screen.getByTestId("provider-configuration-summary"));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Invalid provider credentials",
    );
    expect(screen.getByLabelText(/API Key/)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByLabelText(/API Key/)).toHaveAccessibleDescription(
      "Invalid provider credentials",
    );
    expect(screen.getByLabelText(/Project ID/)).not.toHaveAttribute(
      "aria-invalid",
    );
    expect(screen.getByTestId("provider-save-button")).toHaveTextContent(
      "Retry",
    );
  });

  it("should retain a dropdown selection when configuration is reopened", async () => {
    const user = userEvent.setup();
    const regionVariable: ProviderVariable = {
      ...projectVariable,
      variable_name: "Region",
      variable_key: "AWS_REGION",
      options: ["us-east-1", "us-west-2"],
    };
    render(
      <ConfigurationHarness
        providerVariables={[apiKeyVariable, regionVariable]}
      />,
    );
    await user.click(screen.getByRole("combobox", { name: /Region/ }));
    await user.click(screen.getByTestId("us-west-2-AWS_REGION-option"));

    await user.click(screen.getByTestId("provider-configuration-summary"));
    await user.click(screen.getByTestId("provider-configuration-summary"));

    expect(screen.getByRole("combobox", { name: /Region/ })).toHaveTextContent(
      "us-west-2",
    );
    expect(defaultProps.onSave).not.toHaveBeenCalled();
  });

  it("should expose the configuration summary in the keyboard tab order", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.tab();

    expect(screen.getByTestId("provider-configuration-summary")).toHaveFocus();
  });
});
