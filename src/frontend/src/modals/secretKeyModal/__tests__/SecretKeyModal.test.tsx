import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FormEventHandler, ReactNode } from "react";
import type { ApiKeyPermissionOptions } from "@/types/api-key-permissions";
import SecretKeyModal from "../index";

// This value matches the en.json translation that the global i18n mock resolves.
const PRESET_YEAR = "1 year from today";

// Override the global Form.Root mock so BaseModal renders a real <form> element,
// allowing submit-button-triggered form submissions to work in jsdom.
jest.mock("@radix-ui/react-form", () => ({
  __esModule: true,
  Root: ({
    children,
    onSubmit,
    className,
  }: {
    children: ReactNode;
    onSubmit?: FormEventHandler<HTMLFormElement>;
    className?: string;
  }) => (
    <form onSubmit={onSubmit} className={className}>
      {children}
    </form>
  ),
  Field: ({ children }: { children: ReactNode }) => <>{children}</>,
  Label: ({ children }: { children: ReactNode }) => <>{children}</>,
  Control: ({ children }: { children: ReactNode }) => <>{children}</>,
  Message: ({ children }: { children: ReactNode }) => <>{children}</>,
  Submit: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
}));

jest.mock("@/customization/hooks/use-custom-generate-token", () => ({
  useGenerateToken: () => jest.fn(),
}));

jest.mock(
  "@/controllers/API/queries/api-keys/use-get-api-key-permission-targets",
  () => ({
    useGetApiKeyPermissionTargets: () => ({
      data: [],
      isLoading: false,
      isError: false,
    }),
  }),
);

const mockCreateApiKey = jest.fn();
jest.mock("../../../controllers/API", () => ({
  createApiKey: (...args: unknown[]) => mockCreateApiKey(...args),
}));

const mockSetSuccessData = jest.fn();
jest.mock("../../../stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (s: { setSuccessData: typeof mockSetSuccessData }) => unknown,
  ) => selector({ setSuccessData: mockSetSuccessData }),
}));

const defaultModalProps = {
  title: "Create API Key",
  description: "Generate a new secret key",
  inputLabel: "Key name",
  inputPlaceholder: "my-key",
  buttonText: "Generate Key",
  generatedKeyMessage: "Copy your key now — it won't be shown again.",
  showIcon: true,
};

const permissionOptions: ApiKeyPermissionOptions = {
  supported: true,
  roles: [{ id: "viewer", name: "Viewer", permissions: ["flow:read"] }],
  resource_actions: { flow: ["read", "execute"] },
  scope_types: { flow: ["global", "project"] },
};

const renderModal = (overrides: Record<string, unknown> = {}) =>
  render(
    <SecretKeyModal
      data={{ apikeyname: "" }}
      onCloseModal={jest.fn()}
      modalProps={defaultModalProps}
      {...overrides}
    >
      <button>Open</button>
    </SecretKeyModal>,
  );

describe("SecretKeyModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCreateApiKey.mockResolvedValue({ api_key: "sk-test-abc123" }); // pragma: allowlist secret
  });

  it("renders the trigger child", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Open" })).toBeInTheDocument();
  });

  it("opens the modal when the trigger is clicked", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => {
      expect(screen.getByText("Create API Key")).toBeInTheDocument();
    });
  });

  it("shows the key name input when the modal is open", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => {
      expect(screen.getByPlaceholderText("my-key")).toBeInTheDocument();
    });
  });

  it("calls createApiKey without expires_at when no date is set", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() =>
      expect(screen.getByPlaceholderText("my-key")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByPlaceholderText("my-key"), {
      target: { value: "test-key" },
    });
    const submitBtn = screen.getByTestId("secret_key_modal_submit_button");
    fireEvent.submit(submitBtn.closest("form")!);
    await waitFor(() => {
      expect(mockCreateApiKey).toHaveBeenCalledWith("test-key", null);
    });
  });

  it("calls createApiKey with ISO expires_at when a preset date is set", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() =>
      expect(screen.getByPlaceholderText("my-key")).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByPlaceholderText("my-key"), {
      target: { value: "expiring-key" },
    });
    // Select the "1 year" preset and submit the form
    fireEvent.click(screen.getByText(PRESET_YEAR));
    const submitBtn2 = screen.getByTestId("secret_key_modal_submit_button");
    fireEvent.submit(submitBtn2.closest("form")!);
    await waitFor(() => {
      expect(mockCreateApiKey).toHaveBeenCalledWith(
        "expiring-key",
        expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
      );
    });
  });

  it("defaults supported creation to full owner access", async () => {
    const user = userEvent.setup();
    renderModal({ permissionOptions });
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(
      screen.getByRole("radio", { name: "Full owner access" }),
    ).toBeChecked();
    expect(screen.getByTestId("secret_key_modal_submit_button")).toBeEnabled();
    await user.click(screen.getByTestId("secret_key_modal_submit_button"));
    await waitFor(() =>
      expect(mockCreateApiKey).toHaveBeenCalledWith("", null, null),
    );
  });

  it("requires a permission selection after opting into restricted access", async () => {
    const user = userEvent.setup();
    renderModal({ permissionOptions });
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("radio", { name: "Restricted access" }));
    expect(screen.getByTestId("secret_key_modal_submit_button")).toBeDisabled();
    fireEvent.submit(
      screen.getByTestId("secret_key_modal_submit_button").closest("form")!,
    );
    expect(mockCreateApiKey).not.toHaveBeenCalled();
  });

  it("submits the selected live role", async () => {
    const user = userEvent.setup();
    renderModal({ permissionOptions });
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("radio", { name: "Restricted access" }));
    await user.click(screen.getByRole("button", { name: /^Use a role$/i }));
    await user.selectOptions(screen.getByLabelText("Role 1"), "viewer");
    await user.click(screen.getByTestId("secret_key_modal_submit_button"));
    await waitFor(() =>
      expect(mockCreateApiKey).toHaveBeenCalledWith("", null, {
        roles: [{ role_id: "viewer", domain_type: "global", domain_id: null }],
        restrictions: [],
      }),
    );
  });

  it("does not fall back to full access when permission metadata fails", async () => {
    const user = userEvent.setup();
    renderModal({ permissionsError: true });
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Could not load permission options",
    );
    expect(screen.getByTestId("secret_key_modal_submit_button")).toBeDisabled();
    expect(mockCreateApiKey).not.toHaveBeenCalled();
  });

  it("does not downgrade an open restricted form when scope support disappears", async () => {
    const user = userEvent.setup();
    const result = renderModal({ permissionOptions });
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("radio", { name: "Restricted access" }));
    result.rerender(
      <SecretKeyModal
        data={{ apikeyname: "" }}
        modalProps={defaultModalProps}
        permissionOptions={{ ...permissionOptions, supported: false }}
      >
        <button>Open</button>
      </SecretKeyModal>,
    );
    expect(screen.getByTestId("secret_key_modal_submit_button")).toBeDisabled();
    fireEvent.submit(
      screen.getByTestId("secret_key_modal_submit_button").closest("form")!,
    );
    expect(mockCreateApiKey).not.toHaveBeenCalled();
  });

  it("retains the policy after a server refuses key creation", async () => {
    const user = userEvent.setup();
    mockCreateApiKey.mockRejectedValue({
      response: {
        status: 403,
        data: { detail: "Permission selection refused" },
      },
    });
    renderModal({ permissionOptions });
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(screen.getByRole("radio", { name: "Restricted access" }));
    await user.click(screen.getByRole("button", { name: /^Use a role$/i }));
    await user.selectOptions(screen.getByLabelText("Role 1"), "viewer");
    await user.click(screen.getByTestId("secret_key_modal_submit_button"));
    await waitFor(() =>
      expect(screen.getByLabelText("Role 1")).toHaveValue("viewer"),
    );
    expect(
      screen.getByRole("radio", { name: "Restricted access" }),
    ).toBeChecked();
  });
});
