import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SigningSecretDialog from "../SigningSecretDialog";
import { makeTrigger } from "./fixtures";

const mockRotate = jest.fn();
const mockReset = jest.fn();
let mockRevealed: unknown;
let mockHasSecret = false;

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock("@/controllers/API/queries/triggers", () => ({
  useTriggerIngressQuery: () => ({
    data: {
      trigger_id: "trg-1",
      public_id: "wh_1",
      ingress_url: "https://lf.example/api/v1/triggers/ingress/webhook/wh_1",
      has_signing_secret: mockHasSecret,
    },
    isLoading: false,
  }),
  useRotateSigningSecretMutation: () => ({
    mutate: mockRotate,
    reset: mockReset,
    data: mockRevealed,
    isPending: false,
    isError: false,
  }),
}));

const webhook = makeTrigger({ kind: "inbound_webhook", provider: null });

describe("SigningSecretDialog", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRevealed = undefined;
    mockHasSecret = false;
  });

  it("never shows a secret before one is created", () => {
    render(<SigningSecretDialog trigger={webhook} onOpenChange={jest.fn()} />);

    expect(screen.queryByTestId("trigger-secret-value")).toBeNull();
    expect(screen.getByTestId("trigger-secret-url")).toHaveValue(
      "https://lf.example/api/v1/triggers/ingress/webhook/wh_1",
    );
  });

  it("warns that rotation replaces the secret immediately", async () => {
    mockHasSecret = true;
    render(<SigningSecretDialog trigger={webhook} onOpenChange={jest.fn()} />);

    expect(screen.getByText(/stop working/)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("trigger-secret-rotate"));
    expect(mockRotate).toHaveBeenCalledWith("trg-1");
  });

  it("shows the secret once, from the rotation response", () => {
    mockRevealed = {
      trigger_id: "trg-1",
      ingress_url: "https://lf.example/x",
      has_signing_secret: true,
      signing_secret: "whsec_test",
    };
    render(<SigningSecretDialog trigger={webhook} onOpenChange={jest.fn()} />);

    expect(screen.getByTestId("trigger-secret-value")).toHaveValue(
      "whsec_test",
    );
    expect(
      screen.getByText(/won't be able to view it again/),
    ).toBeInTheDocument();
  });

  it("drops the plaintext when the dialog closes", () => {
    const { rerender } = render(
      <SigningSecretDialog trigger={webhook} onOpenChange={jest.fn()} />,
    );
    rerender(<SigningSecretDialog trigger={null} onOpenChange={jest.fn()} />);

    expect(mockReset).toHaveBeenCalled();
  });
});
