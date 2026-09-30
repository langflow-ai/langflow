import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FormEventHandler, ReactNode } from "react";
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
});
