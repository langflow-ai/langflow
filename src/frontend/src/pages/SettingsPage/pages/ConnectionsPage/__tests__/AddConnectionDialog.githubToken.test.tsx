import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import i18n from "@/i18n";
import { axe } from "@/utils/a11y-test";
import manifest from "../../../../../../../bundles/github/src/lfx_github/components/github/capabilities.v1.json";
import dialogPayload from "../../../../../../../bundles/github/tests/fixtures/manual-token-dialog.json";
import AddConnectionDialog from "../components/AddConnectionDialog";

jest.unmock("react-i18next");
const mockCreate = jest.fn();
const mockRenew = jest.fn();
const mockStartOAuth = jest.fn();
const mockRemove = jest.fn();
const mockRegistrations = { data: [], isSuccess: true };
const mockTypesState = { data: {} };
jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useCreateConnectionMutation: () => ({
    mutateAsync: mockCreate,
    isPending: false,
  }),
  useRenewConnectionTokenMutation: () => ({
    mutateAsync: mockRenew,
    isPending: false,
  }),
  useStartOAuthMutation: () => ({ mutateAsync: mockStartOAuth }),
  useDeleteConnectionMutation: () => ({ mutate: mockRemove }),
  useOAuthRegistrationsQuery: () => mockRegistrations,
  usePendingConnectionPoll: () => ({ data: undefined }),
}));
jest.mock("@/controllers/API/queries/flows/use-get-types", () => ({
  useGetTypes: jest.fn(),
}));
jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (state: unknown) => unknown) =>
    selector(mockTypesState),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));
jest.mock("@/customization/components/custom-connection-authorization", () => ({
  openAuthorizationUrl: jest.fn(),
  resolveRegistrationId: () => null,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const provider = {
  provider_id: manifest.provider_id,
  display_name: manifest.display_name,
  approved: true,
  enabled: false,
  connection_count: 0,
  capabilities: manifest.capabilities.map((capability) => ({
    ...capability,
    allowed: true,
  })),
  manual_token_profiles: [
    {
      id: manifest.auth_profiles[0].id,
      identity: "service",
      required_scopes: [],
      requires_expiry: true,
    },
  ],
} as IntegrationProviderRead;

const revokedConnection = {
  id: "github-connection",
  ...dialogPayload,
  status: "revoked",
  has_credentials: false,
} as unknown as ConnectionRead;

function renderDialog(reauthorize?: ConnectionRead) {
  return render(
    <I18nextProvider i18n={i18n}>
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[provider]}
        canCreateInstance={false}
        deploymentContext="self_managed"
        reauthorize={reauthorize}
      />
    </I18nextProvider>,
  );
}

beforeEach(() => {
  mockCreate.mockReset();
  mockRenew.mockReset();
  mockStartOAuth.mockReset();
  mockRemove.mockReset();
});

it("keeps the existing connection when token renewal is canceled", async () => {
  const user = userEvent.setup();
  renderDialog(revokedConnection);
  await user.type(
    screen.getByTestId("connection-token"),
    "unsaved-installation",
  );
  await user.click(screen.getByRole("button", { name: "Cancel" }));

  expect(mockRemove).not.toHaveBeenCalled();
  expect(mockRenew).not.toHaveBeenCalled();
  expect(mockCreate).not.toHaveBeenCalled();
});

it("has no axe violations in the manual token reconnect form", async () => {
  renderDialog(revokedConnection);

  expect(await axe(screen.getByRole("dialog"))).toHaveNoViolations();
});

it.each([true, false])(
  "preserves existing background consent %s on renewal",
  async (consent) => {
    const connection = { ...revokedConnection, allow_non_interactive: consent };
    mockRenew.mockResolvedValue({ ...connection, status: "ready" });
    const user = userEvent.setup();
    renderDialog(connection);
    expect(
      screen.getByTestId("connection-allow-background-runs"),
    ).toHaveAttribute("data-state", consent ? "checked" : "unchecked");
    await user.type(
      screen.getByTestId("connection-token"),
      "replacement-installation",
    );
    fireEvent.change(screen.getByLabelText("Token expiration"), {
      target: { value: "2030-06-01T12:00" },
    });
    await user.click(screen.getByTestId("connection-continue"));
    expect(mockRenew).toHaveBeenCalledWith(
      expect.objectContaining({
        payload: expect.objectContaining({ allow_non_interactive: consent }),
      }),
    );
  },
);

it("lets the owner turn background consent off during renewal", async () => {
  mockRenew.mockResolvedValue({ ...revokedConnection, status: "ready" });
  const user = userEvent.setup();
  renderDialog({ ...revokedConnection, allow_non_interactive: true });
  await user.click(screen.getByTestId("connection-allow-background-runs"));
  await user.type(
    screen.getByTestId("connection-token"),
    "replacement-installation",
  );
  fireEvent.change(screen.getByLabelText("Token expiration"), {
    target: { value: "2030-06-01T12:00" },
  });
  await user.click(screen.getByTestId("connection-continue"));
  expect(mockRenew).toHaveBeenCalledWith(
    expect.objectContaining({
      payload: expect.objectContaining({ allow_non_interactive: false }),
    }),
  );
});

it("renews a revoked GitHub connection without creating another row or starting OAuth", async () => {
  mockRenew.mockResolvedValue({ ...revokedConnection, status: "ready" });
  const user = userEvent.setup();
  renderDialog(revokedConnection);

  expect(screen.getByTestId("connection-token")).toHaveValue("");
  expect(screen.queryByTestId("connection-name")).not.toBeInTheDocument();
  expect(screen.queryByText(/No OAuth registration/)).not.toBeInTheDocument();
  expect(screen.getByTestId("connection-continue")).toBeDisabled();
  await user.type(
    screen.getByTestId("connection-token"),
    "replacement-installation",
  );
  expect(screen.getByTestId("connection-continue")).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Token expiration"), {
    target: { value: "2030-06-01T12:00" },
  });
  expect(screen.getByTestId("connection-allow-background-runs")).toBeChecked();
  await user.click(screen.getByTestId("connection-continue"));

  expect(mockRenew).toHaveBeenCalledWith({
    id: revokedConnection.id,
    payload: {
      credentials: {
        access_token: "replacement-installation",
        expires_at: new Date("2030-06-01T12:00").toISOString(),
      },
      allow_non_interactive: true,
    },
  });
  expect(await screen.findByTestId("connection-done")).toHaveTextContent(
    "Done",
  );
  expect(mockCreate).not.toHaveBeenCalled();
  expect(mockStartOAuth).not.toHaveBeenCalled();
});

it("keeps a rejected replacement editable without showing a successful reconnect", async () => {
  const detail =
    "GitHub rejected this token. Paste a valid GitHub App installation token and try again.";
  mockRenew.mockRejectedValue({
    isAxiosError: true,
    response: { status: 422, data: { detail } },
  });
  const user = userEvent.setup();
  renderDialog(revokedConnection);
  await user.type(
    screen.getByTestId("connection-token"),
    "rejected-installation",
  );
  fireEvent.change(screen.getByLabelText("Token expiration"), {
    target: { value: "2030-06-01T12:00" },
  });
  await user.click(screen.getByTestId("connection-continue"));

  expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  expect(screen.queryByTestId("connection-done")).not.toBeInTheDocument();
  await user.type(screen.getByTestId("connection-token"), "-corrected");
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(mockCreate).not.toHaveBeenCalled();
});

it("offers only the installation token method supported by GitHub", () => {
  renderDialog();
  expect(
    screen.getByTestId("connection-allow-background-runs"),
  ).not.toBeChecked();
  expect(screen.getByTestId("connection-token")).toBeVisible();
  expect(screen.queryByTestId("connection-method")).not.toBeInTheDocument();
  expect(screen.queryByText(/Sign in with/)).not.toBeInTheDocument();
  expect(
    screen.queryByTestId("connection-callback-url"),
  ).not.toBeInTheDocument();
});

it("submits the GitHub installation payload accepted by the backend validator", async () => {
  mockCreate.mockResolvedValue({ id: "github-connection", ...dialogPayload });
  const user = userEvent.setup();
  renderDialog();
  await user.type(screen.getByTestId("connection-name"), dialogPayload.name);
  await user.type(
    screen.getByTestId("connection-display-name"),
    dialogPayload.display_name,
  );
  await user.type(
    screen.getByTestId("connection-token"),
    dialogPayload.credentials.access_token,
  );
  expect(screen.getByTestId("connection-continue")).toBeDisabled();
  const date = new Date(dialogPayload.credentials.expires_at);
  const pad = (value: number) => String(value).padStart(2, "0");
  const local = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  fireEvent.change(screen.getByLabelText("Token expiration"), {
    target: { value: local },
  });
  await user.click(screen.getByTestId("connection-allow-background-runs"));
  await user.click(screen.getByTestId("connection-continue"));
  expect(mockCreate).toHaveBeenCalledWith(dialogPayload);
});

it.each([
  "GitHub rejected this token. Paste a valid GitHub App installation token and try again.",
  "GitHub rejected this token. Use a GitHub App installation token with repository access.",
  "GitHub rate limited this token check. Wait and try again.",
  "GitHub could not check this token. Try again.",
])(
  "shows the validation reason and permits correction for %s",
  async (detail) => {
    mockCreate.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 422, data: { detail } },
    });
    const user = userEvent.setup();
    renderDialog();
    await user.type(screen.getByTestId("connection-name"), dialogPayload.name);
    await user.type(
      screen.getByTestId("connection-display-name"),
      dialogPayload.display_name,
    );
    await user.type(
      screen.getByTestId("connection-token"),
      dialogPayload.credentials.access_token,
    );
    fireEvent.change(screen.getByLabelText("Token expiration"), {
      target: { value: "2030-06-01T12:00" },
    });
    await user.click(screen.getByTestId("connection-continue"));

    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
    expect(screen.getByTestId("connection-continue")).toBeEnabled();
    await user.type(screen.getByTestId("connection-token"), "-corrected");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  },
);
