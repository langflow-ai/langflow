import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type {
  ConnectionPollBaseline,
  ConnectionRead,
  IntegrationProviderRead,
  OAuthRegistrationRead,
} from "@/controllers/API/queries/connections";
import type { APIDataType } from "@/types/api";
import AddConnectionDialog from "../components/AddConnectionDialog";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

type RegistrationsState = {
  data: OAuthRegistrationRead[] | null | undefined;
  isSuccess: boolean;
  isLoading: boolean;
};

const mockStartOAuth = jest.fn();
const mockCreate = jest.fn();
const mockRemove = jest.fn();
let mockRegistrations: RegistrationsState;
let mockTypes: APIDataType = {};
let mockPolledConnection: ConnectionRead | undefined;

jest.mock("@/controllers/API/queries/connections", () => ({
  CONNECTION_NAME_PATTERN: /^[a-z0-9][a-z0-9_-]*$/,
  CONNECTION_NAME_MAX_LENGTH: 64,
  hasConsentLanded: (
    row: ConnectionRead | undefined,
    baseline: ConnectionPollBaseline | null,
  ) => !!row && !!baseline && row.updated_at !== baseline.updatedAt,
  useCreateConnectionMutation: () => ({
    mutateAsync: mockCreate,
    isPending: false,
  }),
  useDeleteConnectionMutation: () => ({ mutate: mockRemove }),
  useStartOAuthMutation: () => ({ mutateAsync: mockStartOAuth }),
  useOAuthRegistrationsQuery: () => mockRegistrations,
  usePendingConnectionPoll: () => ({ data: mockPolledConnection }),
}));

jest.mock("@/controllers/API/queries/flows/use-get-types", () => ({
  useGetTypes: jest.fn(),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: <T,>(selector: (state: { data: APIDataType }) => T): T =>
    selector({ data: mockTypes }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: <T,>(selector: (state: { setErrorData: jest.Mock }) => T): T =>
    selector({ setErrorData: jest.fn() }),
}));

const CALENDAR = "https://www.googleapis.com/auth/calendar.events";
const GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send";
const MAIL_SEND = "https://graph.microsoft.com/Mail.Send";
const AUTHORIZATION_URL = "https://accounts.example.com/consent";

const capability = (
  id: string,
  componentRef: string,
): IntegrationProviderRead["capabilities"][number] => ({
  id,
  display_name: id,
  policy_keys: [`integrations.${id}`],
  risk: "write",
  maturity: "ga",
  substrate: "sdk",
  identity: "user_delegated",
  auth_profile_id: "user",
  deployment_contexts: ["self_managed"],
  component_ref: componentRef,
  allowed: true,
});

const connectionField = (requiredScopes: string[]) => ({
  template: {
    connection: { type: "connection_ref", required_scopes: requiredScopes },
  },
});

const GOOGLE: IntegrationProviderRead = {
  provider_id: "google",
  display_name: "Google",
  approved: true,
  enabled: true,
  connection_count: 1,
  capabilities: [
    capability("google.calendar.list", "CalendarListComponent"),
    capability("google.gmail.send", "GmailSendComponent"),
  ],
};

const MICROSOFT: IntegrationProviderRead = {
  provider_id: "microsoft",
  display_name: "Microsoft",
  approved: true,
  enabled: true,
  connection_count: 1,
  capabilities: [capability("microsoft.outlook.send", "OutlookSendComponent")],
};

const TYPES = {
  google: {
    "ext:google:CalendarListComponent@official": connectionField([CALENDAR]),
    "ext:google:GmailSendComponent@official": connectionField([GMAIL_SEND]),
  },
  microsoft: {
    "ext:microsoft:OutlookSendComponent@official": connectionField([MAIL_SEND]),
  },
} as unknown as APIDataType;

const registration = (
  overrides: Partial<OAuthRegistrationRead>,
): OAuthRegistrationRead => ({
  id: "google-work",
  provider: "google",
  profile: "user",
  context: "self_managed",
  client_type: "confidential",
  scopes: [CALENDAR, GMAIL_SEND],
  allowed_tenants: [],
  ...overrides,
});

const connection = (
  overrides: Partial<ConnectionRead> = {},
): ConnectionRead => ({
  id: "c1",
  owner_id: "u1",
  ownership_mode: "user",
  provider_key: "google",
  name: "work",
  display_name: "Work Google",
  status: "ready",
  health: "healthy",
  granted_scopes: [CALENDAR],
  executing_identity: { identity: "user_delegated" },
  allow_non_interactive: false,
  has_credentials: true,
  health_checked_at: null,
  created_at: "2026-09-16T10:00:00",
  updated_at: "2026-09-16T10:00:00",
  ...overrides,
});

const popup = {
  closed: false,
  close: jest.fn(),
  focus: jest.fn(),
  location: { href: "" },
};

function setRegistrations(data: OAuthRegistrationRead[] | null | undefined) {
  mockRegistrations = {
    data,
    isSuccess: data !== undefined,
    isLoading: data === undefined,
  };
}

function dialog(reauthorize?: ConnectionRead, providers = [GOOGLE, MICROSOFT]) {
  return (
    <TooltipProvider>
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={providers}
        canCreateInstance={false}
        reauthorize={reauthorize}
      />
    </TooltipProvider>
  );
}

const scopeBox = (scope: string) =>
  screen.getByTestId(`connection-scope-${scope}`);

describe("AddConnectionDialog re-authorize", () => {
  let openSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockTypes = TYPES;
    mockPolledConnection = undefined;
    popup.closed = false;
    popup.location.href = "";
    setRegistrations([registration({})]);
    mockStartOAuth.mockResolvedValue({ authorization_url: AUTHORIZATION_URL });
    openSpy = jest
      .spyOn(window, "open")
      .mockReturnValue(popup as unknown as Window);
  });

  afterEach(() => openSpy.mockRestore());

  it("asks which scopes to request before starting consent", () => {
    render(dialog(connection()));

    expect(screen.getByTestId("connection-authorize")).toBeInTheDocument();
    expect(mockStartOAuth).not.toHaveBeenCalled();
    expect(openSpy).not.toHaveBeenCalled();
  });

  it("checks the granted scopes and leaves the others for the user to add", () => {
    render(dialog(connection()));

    expect(scopeBox(CALENDAR)).toHaveAttribute("aria-checked", "true");
    expect(scopeBox(GMAIL_SEND)).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("Granted")).toBeInTheDocument();
  });

  it("adds a scope to a connection without revoking it first", async () => {
    render(dialog(connection()));

    await userEvent.click(scopeBox(GMAIL_SEND));
    await userEvent.click(screen.getByTestId("connection-authorize"));

    await waitFor(() =>
      expect(mockStartOAuth).toHaveBeenCalledWith({
        id: "c1",
        registrationId: "google-work",
        scopes: [CALENDAR, GMAIL_SEND],
      }),
    );
    await waitFor(() => expect(popup.location.href).toBe(AUTHORIZATION_URL));
  });

  it.each(["create", "reauthorize"])(
    "closes the consent window only after successful %s authorization",
    async (mode) => {
      const initial = connection(
        mode === "create" ? { status: "pending", has_credentials: false } : {},
      );
      const reauthorize = mode === "reauthorize" ? initial : undefined;
      mockCreate.mockResolvedValue(initial);
      mockPolledConnection = initial;
      const { rerender } = render(dialog(reauthorize));

      if (mode === "create") {
        await userEvent.type(screen.getByTestId("connection-name"), "work");
        await userEvent.type(
          screen.getByTestId("connection-display-name"),
          "Work Google",
        );
        await userEvent.click(screen.getByTestId("connection-continue"));
      } else {
        await userEvent.click(screen.getByTestId("connection-authorize"));
      }

      await waitFor(() => expect(popup.location.href).toBe(AUTHORIZATION_URL));
      expect(popup.close).not.toHaveBeenCalled();
      expect(screen.queryByText("Connected")).not.toBeInTheDocument();

      mockPolledConnection = connection({
        updated_at: "2026-09-16T10:01:00",
      });
      rerender(dialog(reauthorize));

      expect(await screen.findByText("Connected")).toBeInTheDocument();
      expect(screen.getByText("calendar.events")).toBeInTheDocument();
      expect(popup.close).toHaveBeenCalledTimes(1);
      expect(mockRemove).not.toHaveBeenCalled();

      await userEvent.click(screen.getByTestId("connection-done"));
      expect(popup.close).toHaveBeenCalledTimes(1);
      expect(mockRemove).not.toHaveBeenCalled();
    },
  );

  it("reports a denied callback from the changed row even when old credentials remain ready", async () => {
    const initial = connection();
    mockPolledConnection = initial;
    const { rerender } = render(dialog(initial));

    await userEvent.click(screen.getByTestId("connection-authorize"));
    await waitFor(() => expect(popup.location.href).toBe(AUTHORIZATION_URL));

    mockPolledConnection = connection({
      updated_at: "2026-09-16T10:01:00",
      status_reason: "oauth-denied",
    });
    rerender(dialog(initial));

    expect(
      await screen.findByText("The provider denied authorization."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });

  it("opens the consent window on the click, before the start request returns", async () => {
    let resolveStart: (value: { authorization_url: string }) => void = () => {};
    mockStartOAuth.mockReturnValue(
      new Promise((resolve) => {
        resolveStart = resolve;
      }),
    );
    render(dialog(connection()));

    await userEvent.click(screen.getByTestId("connection-authorize"));

    expect(openSpy).toHaveBeenCalledWith(
      "about:blank",
      "langflow-oauth-consent",
      "width=520,height=700",
    );
    expect(mockStartOAuth).toHaveBeenCalledTimes(1);
    expect(popup.location.href).toBe("");

    await act(async () =>
      resolveStart({ authorization_url: AUTHORIZATION_URL }),
    );
    expect(popup.location.href).toBe(AUTHORIZATION_URL);
  });

  it("drops a granted scope only when the user clears it", async () => {
    render(dialog(connection()));

    await userEvent.click(scopeBox(CALENDAR));
    await userEvent.click(scopeBox(GMAIL_SEND));
    await userEvent.click(screen.getByTestId("connection-authorize"));

    await waitFor(() =>
      expect(mockStartOAuth).toHaveBeenCalledWith(
        expect.objectContaining({ scopes: [GMAIL_SEND] }),
      ),
    );
  });

  it("retries with the same selection, even after the scope list recomputes", async () => {
    mockStartOAuth.mockRejectedValueOnce(new Error("start refused"));
    const { rerender } = render(dialog(connection()));

    await userEvent.click(scopeBox(GMAIL_SEND));
    await userEvent.click(screen.getByTestId("connection-authorize"));
    expect(
      await screen.findByText("Authorization did not complete."),
    ).toBeInTheDocument();

    // A registrations refetch hands back an equal list under a new identity.
    setRegistrations([registration({})]);
    rerender(dialog(connection()));

    openSpy.mockClear();
    await userEvent.click(screen.getByTestId("connection-try-again"));

    expect(openSpy).toHaveBeenCalledWith(
      "about:blank",
      "langflow-oauth-consent",
      "width=520,height=700",
    );
    await waitFor(() => expect(mockStartOAuth).toHaveBeenCalledTimes(2));
    expect(mockStartOAuth.mock.calls[1][0].scopes).toEqual([
      CALENDAR,
      GMAIL_SEND,
    ]);
  });

  it("checks a requestable Graph scope the connection holds in its short form", async () => {
    setRegistrations([
      registration({
        id: "microsoft-work",
        provider: "microsoft",
        scopes: [MAIL_SEND],
      }),
    ]);
    render(
      dialog(
        connection({
          provider_key: "microsoft",
          name: "outlook",
          display_name: "Outlook",
          granted_scopes: ["Mail.Send", "User.Read"],
        }),
      ),
    );

    expect(scopeBox(MAIL_SEND)).toHaveAttribute("aria-checked", "true");
    // Not in the registration in any spelling, so it cannot be asked for again.
    expect(
      screen.getByText(
        "This registration does not allow User.Read, so those are not requested.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("connection-authorize"));
    await waitFor(() =>
      expect(mockStartOAuth).toHaveBeenCalledWith({
        id: "c1",
        registrationId: "microsoft-work",
        scopes: [MAIL_SEND],
      }),
    );
  });

  it("keeps a granted scope no action declares, so re-authorizing does not drop it", async () => {
    setRegistrations([
      registration({ scopes: [CALENDAR, GMAIL_SEND, "openid"] }),
    ]);
    render(dialog(connection({ granted_scopes: [CALENDAR, "openid"] })));

    expect(scopeBox("openid")).toHaveAttribute("aria-checked", "true");

    await userEvent.click(screen.getByTestId("connection-authorize"));
    await waitFor(() =>
      expect(mockStartOAuth).toHaveBeenCalledWith(
        expect.objectContaining({ scopes: [CALENDAR, "openid"] }),
      ),
    );
  });

  it("lets re-authorization add registration scopes no component declares", async () => {
    setRegistrations([
      registration({
        id: "microsoft-work",
        provider: "microsoft",
        scopes: [
          MAIL_SEND,
          "User.Read",
          "offline_access",
          "openid",
          "email",
          "profile",
        ],
      }),
    ]);
    render(
      dialog(
        connection({
          provider_key: "microsoft",
          granted_scopes: [MAIL_SEND],
        }),
      ),
    );

    for (const scope of ["offline_access", "openid", "email", "profile"]) {
      expect(scopeBox(scope)).toHaveAttribute("aria-checked", "false");
      await userEvent.click(scopeBox(scope));
    }
    expect(scopeBox("User.Read")).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByTestId("connection-authorize"));

    await waitFor(() =>
      expect(mockStartOAuth).toHaveBeenCalledWith({
        id: "c1",
        registrationId: "microsoft-work",
        scopes: [MAIL_SEND, "offline_access", "openid", "email", "profile"],
      }),
    );
  });

  it("does not authorize with nothing selected", async () => {
    render(dialog(connection()));

    await userEvent.click(scopeBox(CALENDAR));

    expect(screen.getByTestId("connection-authorize")).toBeDisabled();
  });

  it("waits for the registration listing before it can authorize", () => {
    setRegistrations(undefined);
    render(dialog(connection()));

    expect(screen.getByTestId("connection-authorize")).toBeDisabled();
  });

  it("explains a provider with no registration instead of starting consent", () => {
    setRegistrations([]);
    render(dialog(connection()));

    expect(screen.getByTestId("connection-authorize")).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "No OAuth registration is configured for this provider.",
    );
  });
});

describe("AddConnectionDialog create flow", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockTypes = TYPES;
    mockPolledConnection = undefined;
    setRegistrations([registration({})]);
  });

  it("still starts on the details step with every requestable scope checked", () => {
    render(dialog(undefined, [GOOGLE]));

    expect(screen.getByTestId("connection-continue")).toBeInTheDocument();
    expect(
      screen.queryByTestId("connection-authorize"),
    ).not.toBeInTheDocument();
    expect(scopeBox(CALENDAR)).toHaveAttribute("aria-checked", "true");
    expect(scopeBox(GMAIL_SEND)).toHaveAttribute("aria-checked", "true");
  });

  it("can request Microsoft identity and refresh scopes on first consent", async () => {
    setRegistrations([
      registration({
        id: "microsoft-work",
        provider: "microsoft",
        scopes: [
          MAIL_SEND,
          "User.Read",
          "offline_access",
          "openid",
          "email",
          "profile",
        ],
      }),
    ]);
    mockCreate.mockResolvedValue(
      connection({ provider_key: "microsoft", status: "pending" }),
    );
    mockStartOAuth.mockResolvedValue({ authorization_url: AUTHORIZATION_URL });
    const openSpy = jest
      .spyOn(window, "open")
      .mockReturnValue(popup as unknown as Window);
    try {
      render(dialog(undefined, [MICROSOFT]));
      expect(scopeBox("User.Read")).toHaveAttribute("aria-checked", "false");
      for (const scope of ["offline_access", "openid", "email", "profile"]) {
        expect(scopeBox(scope)).toHaveAttribute("aria-checked", "true");
      }

      await userEvent.type(screen.getByTestId("connection-name"), "outlook");
      await userEvent.type(
        screen.getByTestId("connection-display-name"),
        "Outlook",
      );
      await userEvent.click(screen.getByTestId("connection-continue"));
      await waitFor(() =>
        expect(mockStartOAuth).toHaveBeenCalledWith({
          id: "c1",
          registrationId: "microsoft-work",
          scopes: [MAIL_SEND, "offline_access", "openid", "email", "profile"],
        }),
      );
    } finally {
      openSpy.mockRestore();
    }
  });
});
