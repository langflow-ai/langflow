import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import type {
  ConnectionRead,
  DeploymentContext,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import i18n from "@/i18n";
import { axe } from "@/utils/a11y-test";
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
  useRenewConnectionTokenMutation: () => ({
    mutateAsync: jest.fn(),
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

const pilot: IntegrationProviderRead = {
  ...google,
  provider_id: "pilot",
  display_name: "Pilot",
  capabilities: [
    {
      ...capability(
        "pilot.trigger.item",
        "bot",
        "pilot-token",
        "PilotOnItemTriggerComponent",
      ),
      identity: "service",
    },
  ],
  manual_token_profiles: [
    { id: "pilot-token", identity: "service", required_scopes: [] },
  ],
};

const expiringPilot = (): IntegrationProviderRead => ({
  ...pilot,
  manual_token_profiles: pilot.manual_token_profiles?.map((profile) => ({
    ...profile,
    requires_expiry: true,
  })),
});

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

const dialog = (
  providers: IntegrationProviderRead[],
  deploymentContext: DeploymentContext | undefined,
  open = true,
) => (
  <I18nextProvider i18n={i18n}>
    <AddConnectionDialog
      open={open}
      onOpenChange={jest.fn()}
      providers={providers}
      canCreateInstance={false}
      deploymentContext={deploymentContext}
    />
  </I18nextProvider>
);

const renderDialog = (
  providers: IntegrationProviderRead[],
  deploymentContext: DeploymentContext | undefined = "desktop",
) => render(dialog(providers, deploymentContext));

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

  it("creates a provider-validated service token without an OAuth registration", async () => {
    const user = userEvent.setup();
    mockCreate.mockResolvedValue(
      created({
        provider_key: "pilot",
        executing_identity: { identity: "service" },
      }),
    );
    renderDialog([pilot], "self_managed");
    expect(await screen.findByTestId("connection-token")).toBeInTheDocument();
    expect(screen.getByTestId("connection-token-help")).toHaveTextContent(
      "Langflow checks the token",
    );
    await user.type(screen.getByTestId("connection-name"), "work");
    await user.type(
      screen.getByTestId("connection-display-name"),
      "Pilot work",
    );
    await user.type(screen.getByTestId("connection-token"), "provider-token");
    expect(await axe(document.body)).toHaveNoViolations();
    await user.click(screen.getByTestId("connection-continue"));
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        provider_key: "pilot",
        name: "work",
        executing_identity: { identity: "service" },
        granted_scopes: [],
        allow_non_interactive: false,
        credentials: { access_token: "provider-token" },
      }),
    );
  });

  it("restores the provider's token default when the mounted dialog reopens", async () => {
    const user = userEvent.setup();
    const view = renderDialog([pilot], "self_managed");
    await user.type(
      await screen.findByTestId("connection-token"),
      "discarded-token",
    );
    await user.click(screen.getByTestId("connection-allow-background-runs"));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    view.rerender(dialog([pilot], "self_managed", false));
    view.rerender(dialog([pilot], "self_managed"));
    expect(await screen.findByTestId("connection-token")).toHaveValue("");
    expect(screen.queryByTestId("connection-method")).not.toBeInTheDocument();
    expect(
      screen.getByTestId("connection-allow-background-runs"),
    ).not.toBeChecked();
  });

  it("selects the identity and scopes of an advertised manual token profile", async () => {
    const user = userEvent.setup();
    const provider: IntegrationProviderRead = {
      ...pilot,
      capabilities: [
        ...pilot.capabilities,
        capability(
          "pilot.user.read",
          "user_delegated",
          "pilot-user",
          "PilotReadComponent",
        ),
      ],
      manual_token_profiles: [
        {
          id: "pilot-token",
          identity: "service",
          required_scopes: ["items:read"],
        },
        {
          id: "pilot-user",
          identity: "user_delegated",
          required_scopes: ["profile:read"],
        },
      ],
    };
    mockCreate.mockResolvedValue(created({ provider_key: "pilot" }));
    const view = renderDialog([provider], "self_managed");
    const identity = await screen.findByLabelText("Runs as");
    await user.selectOptions(identity, "service");
    await user.selectOptions(identity, "user_delegated");
    view.rerender(
      dialog(
        [
          {
            ...provider,
            manual_token_profiles: provider.manual_token_profiles?.map(
              (profile) => ({ ...profile }),
            ),
          },
        ],
        "self_managed",
      ),
    );
    expect(identity).toHaveValue("user_delegated");
    await user.type(screen.getByTestId("connection-name"), "work");
    await user.type(
      screen.getByTestId("connection-display-name"),
      "Pilot user",
    );
    await user.type(screen.getByTestId("connection-token"), "provider-token");
    expect(await axe(document.body)).toHaveNoViolations();
    await user.click(screen.getByTestId("connection-continue"));
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        executing_identity: { identity: "user_delegated" },
        granted_scopes: ["profile:read"],
      }),
    );
  });

  it("preserves an explicit OAuth choice after the provider catalog refetches", async () => {
    const user = userEvent.setup();
    const provider = {
      ...pilot,
      capabilities: [
        ...pilot.capabilities,
        capability(
          "pilot.user.read",
          "user_delegated",
          "pilot-user-oauth",
          "PilotReadComponent",
        ),
      ],
    };
    const view = renderDialog([provider], "self_managed");
    await screen.findByTestId("connection-token");
    expect(
      screen.getByRole("option", { name: "Sign in with Pilot" }),
    ).toBeInTheDocument();
    await user.selectOptions(screen.getByTestId("connection-method"), "oauth");
    view.rerender(
      dialog(
        [
          {
            ...provider,
            manual_token_profiles: provider.manual_token_profiles?.map(
              (profile) => ({ ...profile }),
            ),
          },
        ],
        "self_managed",
      ),
    );
    expect(screen.getByTestId("connection-method")).toHaveValue("oauth");
    expect(screen.queryByTestId("connection-token")).not.toBeInTheDocument();
  });

  it("requires future token expiration and sends the local time as UTC", async () => {
    const user = userEvent.setup();
    mockCreate.mockResolvedValue(created({ provider_key: "pilot" }));
    renderDialog([expiringPilot()], "self_managed");
    await user.type(screen.getByTestId("connection-name"), "work");
    await user.type(
      screen.getByTestId("connection-display-name"),
      "Pilot work",
    );
    await user.type(screen.getByTestId("connection-token"), "provider-token");
    const expiration = screen.getByLabelText("Token expiration");
    expect(expiration).toBeRequired();
    expect(screen.getByTestId("connection-continue")).toBeDisabled();
    fireEvent.change(expiration, { target: { value: "2000-06-15T12:30" } });
    expect(expiration).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByTestId("connection-continue")).toBeDisabled();
    fireEvent.change(expiration, { target: { value: "2100-06-15T12:30" } });
    expect(expiration).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByTestId("connection-continue")).toBeEnabled();
    expect(await axe(document.body)).toHaveNoViolations();
    await user.click(screen.getByTestId("connection-continue"));
    const sent = mockCreate.mock.calls[0][0].credentials.expires_at;
    expect(sent).toMatch(/Z$/);
    const localTime = new Date(sent);
    expect(localTime.getFullYear()).toBe(2100);
    expect(localTime.getMonth()).toBe(5);
    expect(localTime.getDate()).toBe(15);
    expect(localTime.getHours()).toBe(12);
    expect(localTime.getMinutes()).toBe(30);
  });

  it("clears expiration when the token dialog closes and reopens", async () => {
    const user = userEvent.setup();
    const provider = expiringPilot();
    const view = renderDialog([provider], "self_managed");
    fireEvent.change(screen.getByLabelText("Token expiration"), {
      target: { value: "2100-06-15T12:30" },
    });
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    view.rerender(dialog([provider], "self_managed", false));
    view.rerender(dialog([provider], "self_managed"));
    expect(screen.getByLabelText("Token expiration")).toHaveValue("");
    expect(screen.getByTestId("connection-token")).toHaveValue("");
    expect(screen.getByTestId("connection-continue")).toBeDisabled();
  });

  it("rejects a nonexistent local expiration instead of shifting it across a DST gap", async () => {
    // Jest normally uses Sao Paulo. Also exercise the reported Los Angeles
    // transition when this suite is run with the targeted timezone config.
    const gap =
      Intl.DateTimeFormat().resolvedOptions().timeZone === "America/Los_Angeles"
        ? "2027-03-14T02:30"
        : "2018-11-04T00:30";
    jest.spyOn(Date, "now").mockReturnValue(Date.parse("2018-10-01T00:00:00Z"));
    const user = userEvent.setup();
    renderDialog([expiringPilot()], "self_managed");
    await user.type(screen.getByTestId("connection-name"), "work");
    await user.type(
      screen.getByTestId("connection-display-name"),
      "Pilot work",
    );
    await user.type(screen.getByTestId("connection-token"), "provider-token");
    const expiration = screen.getByLabelText("Token expiration");
    fireEvent.change(expiration, { target: { value: gap } });
    expect(expiration).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByTestId("connection-continue")).toBeDisabled();
    await user.click(screen.getByTestId("connection-continue"));
    expect(mockCreate).not.toHaveBeenCalled();
    expect(await axe(document.body)).toHaveNoViolations();
    fireEvent.change(expiration, { target: { value: "2027-03-14T03:30" } });
    expect(expiration).toHaveAttribute("aria-invalid", "false");
    expect(screen.getByTestId("connection-continue")).toBeEnabled();
  });

  it("clears provider expiration when switching the selected provider", async () => {
    const user = userEvent.setup();
    renderDialog([expiringPilot(), slack], "self_managed");
    fireEvent.change(screen.getByLabelText("Token expiration"), {
      target: { value: "2100-06-15T12:30" },
    });
    await user.selectOptions(
      screen.getByTestId("connection-provider"),
      "slack",
    );
    expect(screen.queryByLabelText("Token expiration")).not.toBeInTheDocument();
    await user.selectOptions(
      screen.getByTestId("connection-provider"),
      "pilot",
    );
    expect(screen.getByLabelText("Token expiration")).toHaveValue("");
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

  it("switches setup guidance with the Slack connection method", async () => {
    const user = userEvent.setup();
    renderDialog([slack]);
    expect(screen.getByTestId("connection-callback-url")).toBeVisible();
    await user.selectOptions(screen.getByTestId("connection-method"), "token");
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      "https://docs.langflow.org/bundles-slack#two-executing-identities",
    );
    expect(
      screen.queryByTestId("connection-callback-url"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not offer a pasted token before the deployment says what it is", () => {
    // Not ``renderDialog``: its default would stand in for the missing context.
    render(dialog([slack], undefined));

    expect(screen.queryByTestId("connection-method")).not.toBeInTheDocument();
  });

  it("does not let pasted tokens claim scopes from checkboxes", async () => {
    mockCreate.mockResolvedValueOnce(created({ granted_scopes: [] }));
    const user = userEvent.setup();
    renderDialog([slack]);

    await choosePastedToken(user, "xoxb-1111-2222-secret");
    expect(
      screen.queryByTestId("connection-scope-chat:write"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByTestId("connection-continue"));
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ granted_scopes: [] }),
    );
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

  it("shows the server-verified scopes after connecting a bot token", async () => {
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
        granted_scopes: [],
        credentials: { access_token: "xoxb-1111-2222-secret" },
      }),
    );
    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("chat:write")).toBeInTheDocument();
    expect(screen.queryByText("search:read")).not.toBeInTheDocument();
  });

  it("keeps a rejected bot token out of the connected step", async () => {
    mockCreate.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        data: {
          detail:
            "Slack rejected this token. Paste a valid token and try again.",
        },
      },
    });
    const user = userEvent.setup();
    renderDialog([slack]);
    await choosePastedToken(user, "xoxb-123");
    await user.click(screen.getByTestId("connection-continue"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Slack rejected this token",
    );
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
    expect(screen.getByTestId("connection-continue")).toBeEnabled();
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

  it("clears the server's refusal once the person edits the token", async () => {
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
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.type(screen.getByTestId("connection-token"), "2");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
