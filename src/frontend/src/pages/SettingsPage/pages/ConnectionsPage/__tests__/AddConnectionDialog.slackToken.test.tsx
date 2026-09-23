import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import i18n from "@/i18n";
import AddConnectionDialog from "../components/AddConnectionDialog";

jest.unmock("react-i18next");

const mockCreate = jest.fn();
// Stable references: the dialog memoizes on these.
const mockRegistrations = { data: [], isSuccess: true };
const mockTypesState = {
  data: {
    slack: {
      SlackPostAsAppComponent: {
        display_name: "Slack: Post Message (as app)",
        template: {
          connection: {
            type: "connection_ref",
            provider: "slack",
            required_scopes: ["chat:write"],
            conditional_scopes: [],
          },
        },
      },
      SlackSearchComponent: {
        display_name: "Slack: Search (as user)",
        template: {
          connection: {
            type: "connection_ref",
            provider: "slack",
            required_scopes: ["search:read"],
            conditional_scopes: [],
          },
        },
      },
    },
  },
};
const mockPoll = { data: undefined };

jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useCreateConnectionMutation: () => ({
    mutateAsync: mockCreate,
    isPending: false,
  }),
  useStartOAuthMutation: () => ({ mutateAsync: jest.fn() }),
  useDeleteConnectionMutation: () => ({ mutate: jest.fn() }),
  useOAuthRegistrationsQuery: () => mockRegistrations,
  usePendingConnectionPoll: () => mockPoll,
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
  // Desktop and most self-managed installs have no Slack bot registration.
  resolveRegistrationId: () => null,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const capability = (
  id: string,
  identity: "bot" | "user_delegated",
  auth_profile_id: string,
  component_ref: string,
) => ({
  id,
  display_name: id,
  policy_keys: [],
  risk: "read",
  maturity: "ga",
  substrate: "rest",
  identity,
  auth_profile_id,
  deployment_contexts: ["self_managed", "desktop"],
  component_ref,
  allowed: true,
});

const slack: IntegrationProviderRead = {
  provider_id: "slack",
  display_name: "Slack",
  approved: true,
  enabled: true,
  connection_count: 0,
  capabilities: [
    capability(
      "slack.bot.post",
      "bot",
      "slack-bot-install",
      "SlackPostAsAppComponent",
    ),
    capability(
      "slack.user.search",
      "user_delegated",
      "slack-user-oauth",
      "SlackSearchComponent",
    ),
  ],
};

const google: IntegrationProviderRead = {
  provider_id: "google",
  display_name: "Google",
  approved: true,
  enabled: true,
  connection_count: 0,
  capabilities: [],
};

const created = (overrides: Partial<ConnectionRead> = {}): ConnectionRead => ({
  id: "conn-1",
  owner_id: "user-1",
  ownership_mode: "user",
  provider_key: "slack",
  name: "socket_app",
  display_name: "Socket app",
  status: "ready",
  status_reason: null,
  health: "unknown",
  granted_scopes: ["connections:write"],
  executing_identity: { identity: "bot" },
  allow_non_interactive: false,
  has_credentials: true,
  health_checked_at: null,
  created_at: "2026-09-23T00:00:00Z",
  updated_at: "2026-09-23T00:00:00Z",
  ...overrides,
});

const renderDialog = (
  providers: IntegrationProviderRead[],
  deploymentContext = "desktop",
) =>
  render(
    <I18nextProvider i18n={i18n}>
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={providers}
        canCreateInstance={false}
        deploymentContext={deploymentContext}
      />
    </I18nextProvider>,
  );

const choosePastedToken = async (
  user: ReturnType<typeof userEvent.setup>,
  token: string,
) => {
  await user.selectOptions(screen.getByTestId("connection-method"), "token");
  await user.type(screen.getByTestId("connection-name"), "socket_app");
  await user.type(screen.getByTestId("connection-display-name"), "Socket app");
  await user.type(screen.getByTestId("connection-token"), token);
};

describe("AddConnectionDialog: pasted Slack tokens", () => {
  beforeEach(() => {
    mockCreate.mockReset();
    jest.spyOn(window, "open").mockReturnValue(null);
  });

  afterEach(async () => {
    jest.restoreAllMocks();
    await act(() => i18n.changeLanguage("en"));
  });

  it("offers a pasted token for Slack off hosted, and only for Slack", () => {
    const { unmount } = renderDialog([slack], "desktop");
    expect(screen.getByTestId("connection-method")).toBeInTheDocument();
    unmount();

    renderDialog([google], "desktop");
    expect(screen.queryByTestId("connection-method")).not.toBeInTheDocument();
  });

  it("never offers a pasted token on hosted", () => {
    renderDialog([slack], "hosted");

    expect(screen.queryByTestId("connection-method")).not.toBeInTheDocument();
  });

  it("stores an app-level token without a consent window, and without claiming its scope", async () => {
    mockCreate.mockResolvedValueOnce(created());
    const user = userEvent.setup();
    renderDialog([slack]);

    await choosePastedToken(user, "xapp-1-A0APP-1-secret");
    expect(screen.getByTestId("connection-token-help")).toHaveTextContent(
      /App-level token/,
    );
    await user.click(screen.getByTestId("connection-continue"));

    expect(mockCreate).toHaveBeenCalledWith({
      provider_key: "slack",
      name: "socket_app",
      display_name: "Socket app",
      ownership_mode: "user",
      executing_identity: { identity: "bot" },
      granted_scopes: [],
      allow_non_interactive: false,
      credentials: { access_token: "xapp-1-A0APP-1-secret" },
    });
    expect(window.open).not.toHaveBeenCalled();
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });

  it("asks for background runs explicitly rather than assuming them", async () => {
    mockCreate.mockResolvedValueOnce(created({ allow_non_interactive: true }));
    const user = userEvent.setup();
    renderDialog([slack]);

    await choosePastedToken(user, "xapp-1-A0APP-1-secret");
    const consent = screen.getByTestId("connection-allow-background-runs");
    expect(consent).not.toBeChecked();
    await user.click(consent);
    await user.click(screen.getByTestId("connection-continue"));

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ allow_non_interactive: true }),
    );
  });

  it("records the bot actions' scopes for a bot token, never the user actions'", async () => {
    mockCreate.mockResolvedValueOnce(
      created({ granted_scopes: ["chat:write"] }),
    );
    const user = userEvent.setup();
    renderDialog([slack]);

    await choosePastedToken(user, "xoxb-1111-2222-secret");
    expect(screen.getByTestId("connection-token-help")).toHaveTextContent(
      /Bot token/,
    );
    await user.click(screen.getByTestId("connection-continue"));

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        granted_scopes: ["chat:write"],
        credentials: { access_token: "xoxb-1111-2222-secret" },
      }),
    );
  });

  it("refuses anything that is not a Slack app-level or bot token", async () => {
    const user = userEvent.setup();
    renderDialog([slack]);

    await choosePastedToken(user, "xoxp-user-token");

    expect(screen.getByTestId("connection-token")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByTestId("connection-continue")).toBeDisabled();
    await user.click(screen.getByTestId("connection-continue"));
    expect(mockCreate).not.toHaveBeenCalled();
  });

  it("shows the server's refusal and keeps the dialog usable", async () => {
    mockCreate.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        data: {
          detail: "Slack app-level tokens neither expire nor refresh.",
        },
      },
    });
    const user = userEvent.setup();
    renderDialog([slack]);

    await choosePastedToken(user, "xapp-1-A0APP-1-secret");
    await user.click(screen.getByTestId("connection-continue"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "neither expire nor refresh",
    );
    expect(screen.getByTestId("connection-continue")).toBeEnabled();
  });
});
