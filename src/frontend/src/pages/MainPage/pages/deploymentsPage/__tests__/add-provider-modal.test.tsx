import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";

const mockMutateAsync = jest.fn();

jest.mock(
  "@/controllers/API/queries/deployment-provider-accounts/use-post-provider-account",
  () => ({
    usePostProviderAccount: () => ({
      mutateAsync: mockMutateAsync,
    }),
  }),
);

jest.mock("../hooks/use-error-alert", () => ({
  useErrorAlert: () => jest.fn(),
}));

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import AddProviderModal from "../components/add-provider-modal";

function renderModal(open = true) {
  const setOpen = jest.fn();
  const result = render(
    <TooltipProvider>
      <AddProviderModal open={open} setOpen={setOpen} />
    </TooltipProvider>,
  );
  return { setOpen, ...result };
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe("Rendering", () => {
  it("renders modal title and description", () => {
    renderModal();
    expect(screen.getByText("Add Environment")).toBeInTheDocument();
    expect(
      screen.getByText(/Configure your watsonx Orchestrate credentials/),
    ).toBeInTheDocument();
  });

  it("shows watsonx Orchestrate provider badge", () => {
    renderModal();
    expect(screen.getByText("watsonx Orchestrate")).toBeInTheDocument();
  });

  it("renders signup and credentials help links", () => {
    renderModal();

    expect(
      screen.getByRole("link", { name: "Sign up for watsonx Orchestrate" }),
    ).toHaveAttribute(
      "href",
      "https://www.ibm.com/products/watsonx-orchestrate#pricing",
    );
    expect(
      screen.getByRole("link", { name: "Find your credentials" }),
    ).toHaveAttribute(
      "href",
      "https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=api-getting-started",
    );
  });

  it("renders form fields: Name, API Key, Service Instance URL", () => {
    renderModal();
    expect(screen.getByPlaceholderText("e.g. Production")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Enter your API key"),
    ).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("https://api.example.com"),
    ).toBeInTheDocument();
  });

  it("renders Cancel and Save buttons", () => {
    renderModal();
    expect(screen.getByTestId("add-provider-cancel")).toBeInTheDocument();
    expect(screen.getByTestId("add-provider-save")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Form validation
// ---------------------------------------------------------------------------

describe("Form validation", () => {
  it("Save is disabled when all fields are empty", () => {
    renderModal();
    expect(screen.getByTestId("add-provider-save")).toBeDisabled();
  });

  it("Save is disabled when only name is filled", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByPlaceholderText("e.g. Production"), "My Env");
    expect(screen.getByTestId("add-provider-save")).toBeDisabled();
  });

  it("Save is disabled when api_key is missing", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByPlaceholderText("e.g. Production"), "My Env");
    await user.type(
      screen.getByPlaceholderText("https://api.example.com"),
      "https://prod.example.com",
    );
    expect(screen.getByTestId("add-provider-save")).toBeDisabled();
  });

  it("Save is enabled when all required fields are filled", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByPlaceholderText("e.g. Production"), "My Env");
    await user.type(
      screen.getByPlaceholderText("Enter your API key"),
      "sk-test-123", // pragma: allowlist secret
    );
    await user.type(
      screen.getByPlaceholderText("https://api.example.com"),
      "https://prod.example.com",
    );
    expect(screen.getByTestId("add-provider-save")).not.toBeDisabled();
  });

  it("Save is disabled when fields are whitespace-only", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByPlaceholderText("e.g. Production"), "   ");
    await user.type(screen.getByPlaceholderText("Enter your API key"), "   ");
    await user.type(
      screen.getByPlaceholderText("https://api.example.com"),
      "   ",
    );
    expect(screen.getByTestId("add-provider-save")).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Submit behavior
// ---------------------------------------------------------------------------

describe("Submit behavior", () => {
  async function fillForm() {
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("e.g. Production"), " My Env ");
    await user.type(
      screen.getByPlaceholderText("Enter your API key"),
      " sk-test-123 ", // pragma: allowlist secret
    );
    await user.type(
      screen.getByPlaceholderText("https://api.example.com"),
      " https://prod.example.com ",
    );
    return user;
  }

  it("calls createProviderAccount with trimmed values", async () => {
    mockMutateAsync.mockResolvedValue({ id: "new-prov" });
    const { setOpen } = renderModal();
    const user = await fillForm();

    await user.click(screen.getByTestId("add-provider-save"));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        name: "My Env",
        provider_key: "watsonx-orchestrate",
        provider_data: {
          url: "https://prod.example.com",
          api_key: "sk-test-123", // pragma: allowlist secret
        },
      });
    });
    expect(setOpen).toHaveBeenCalledWith(false);
  });

  it("shows Saving... text during submission", async () => {
    let resolveCreate!: () => void;
    mockMutateAsync.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveCreate = resolve;
      }),
    );
    renderModal();
    const user = await fillForm();

    await user.click(screen.getByTestId("add-provider-save"));

    await waitFor(() => {
      expect(screen.getByText("Saving...")).toBeInTheDocument();
    });

    resolveCreate();
  });

  it("does not close modal on API error", async () => {
    mockMutateAsync.mockRejectedValue(new Error("Network error"));
    const { setOpen } = renderModal();
    const user = await fillForm();

    await user.click(screen.getByTestId("add-provider-save"));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalled();
    });
    // setOpen(false) should NOT have been called
    expect(setOpen).not.toHaveBeenCalledWith(false);
  });
});

// ---------------------------------------------------------------------------
// Cancel behavior
// ---------------------------------------------------------------------------

describe("Cancel behavior", () => {
  it("calls setOpen(false) when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const { setOpen } = renderModal();

    await user.click(screen.getByTestId("add-provider-cancel"));
    expect(setOpen).toHaveBeenCalledWith(false);
  });
});
