import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ProviderAccount, ProviderCredentials } from "../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockSetSelectedProvider = jest.fn();
const mockSetSelectedInstance = jest.fn();
const mockSetCredentials = jest.fn();

let mockProviderAccountsData:
  | { provider_accounts: ProviderAccount[] }
  | undefined;

jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-get-provider-accounts",
  () => ({
    useGetProviderAccounts: () => ({
      data: mockProviderAccountsData,
    }),
  }),
);

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: () => ({
    setSelectedProvider: mockSetSelectedProvider,
    selectedInstance: null,
    setSelectedInstance: mockSetSelectedInstance,
    credentials: {
      name: "",
      provider_key: "watsonx-orchestrate",
      url: "",
      api_key: "",
    } as ProviderCredentials,
    setCredentials: mockSetCredentials,
  }),
}));

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import StepProvider from "../components/step-provider";

const makeEnvironment = (
  overrides: Partial<ProviderAccount> = {},
): ProviderAccount => ({
  id: "env-1",
  name: "Prod Environment",
  provider_key: "watsonx-orchestrate",
  provider_data: { url: "https://api.prod.example.com" },
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-05-01T00:00:00Z",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockProviderAccountsData = undefined;
});

// ---------------------------------------------------------------------------
// Basic rendering
// ---------------------------------------------------------------------------

describe("Basic rendering", () => {
  it("renders the Provider heading", () => {
    render(<StepProvider />);
    expect(screen.getByText("Provider")).toBeInTheDocument();
  });

  it("displays the watsonx Orchestrate provider card", () => {
    render(<StepProvider />);
    expect(screen.getByText("watsonx Orchestrate")).toBeInTheDocument();
  });

  it("calls setSelectedProvider on mount", () => {
    render(<StepProvider />);
    expect(mockSetSelectedProvider).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "watsonx",
        type: "watsonx",
        name: "watsonx Orchestrate",
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// No existing environments
// ---------------------------------------------------------------------------

describe("No existing environments", () => {
  it("shows the credentials form directly", () => {
    mockProviderAccountsData = { provider_accounts: [] };
    render(<StepProvider />);
    expect(screen.getByPlaceholderText("e.g. Production")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter your API key"),
    ).toBeInTheDocument();
  });

  it("does not show the environment tab toggle", () => {
    mockProviderAccountsData = { provider_accounts: [] };
    render(<StepProvider />);
    expect(
      screen.queryByText("Choose existing environment"),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// With existing environments
// ---------------------------------------------------------------------------

describe("With existing environments", () => {
  beforeEach(() => {
    mockProviderAccountsData = {
      provider_accounts: [
        makeEnvironment({ id: "env-1", name: "Prod Environment" }),
        makeEnvironment({
          id: "env-2",
          name: "Staging",
          provider_data: { url: "https://api.staging.example.com" },
        }),
      ],
    };
  });

  it("shows environment tab toggle with both tabs", () => {
    render(<StepProvider />);
    expect(screen.getByText("Choose existing environment")).toBeInTheDocument();
    expect(screen.getByText("Add new environment")).toBeInTheDocument();
  });

  it("auto-switches to existing tab when environments available", async () => {
    render(<StepProvider />);
    // The existing tab should be active, showing the environment list
    await waitFor(() => {
      expect(
        screen.getByText("Select from your existing environments"),
      ).toBeInTheDocument();
    });
  });

  it("renders environment radio items", async () => {
    render(<StepProvider />);
    await waitFor(() => {
      expect(screen.getByText("Prod Environment")).toBeInTheDocument();
      expect(screen.getByText("Staging")).toBeInTheDocument();
    });
  });

  it("shows environment URLs", async () => {
    render(<StepProvider />);
    await waitFor(() => {
      expect(
        screen.getByText("https://api.prod.example.com"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("https://api.staging.example.com"),
      ).toBeInTheDocument();
    });
  });

  it("calls setSelectedInstance when an environment is selected", async () => {
    const user = userEvent.setup();
    render(<StepProvider />);

    await waitFor(() => {
      expect(screen.getByText("Prod Environment")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Prod Environment"));
    expect(mockSetSelectedInstance).toHaveBeenCalledWith(
      expect.objectContaining({ id: "env-1", name: "Prod Environment" }),
    );
  });

  it("switches to credentials form when 'Add new environment' tab is clicked", async () => {
    const user = userEvent.setup();
    render(<StepProvider />);

    await user.click(screen.getByText("Add new environment"));
    expect(screen.getByPlaceholderText("e.g. Production")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter your API key"),
    ).toBeInTheDocument();
  });

  it("has radiogroup role for environment selection", async () => {
    render(<StepProvider />);
    await waitFor(() => {
      expect(
        screen.getByRole("radiogroup", { name: "Existing environments" }),
      ).toBeInTheDocument();
    });
  });
});
