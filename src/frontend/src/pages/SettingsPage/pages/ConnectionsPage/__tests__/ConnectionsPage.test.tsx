import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { I18nextProvider } from "react-i18next";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import type { ConnectionsTabDefinition } from "@/customization/components/custom-connections-tabs";
import i18n, { loadLanguage } from "@/i18n";
import ConnectionsPage from "../index";

jest.unmock("react-i18next");

const SUPERUSER_ID = "user-admin";
const REGULAR_ID = "user-regular";
const OTHER_ID = "user-bob";

let mockUser: { id: string; is_superuser: boolean };
let mockConnections: ConnectionRead[];
let mockIntegrations: Record<string, unknown> = { data: { providers: [] } };
const mockMutation = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockSetNoticeData = jest.fn();
const mockCreate = jest.fn();
const mockPoll: { data: ConnectionRead | undefined } = { data: undefined };
const mockRegistrations = {
  data: [
    {
      id: "google-demo",
      provider: "google",
      profile: "user",
      context: "self_managed",
      client_type: "confidential",
      scopes: [] as string[],
    },
  ],
  isSuccess: true,
};
let mockExtraTabs: ConnectionsTabDefinition[] = [];

jest.mock("@/controllers/API/queries/connections", () => {
  const mutation = () => ({ mutate: jest.fn(), mutateAsync: mockMutation });
  return {
    ...jest.requireActual("@/controllers/API/queries/connections"),
    useGetConnections: () => ({ data: mockConnections, isLoading: false }),
    useIntegrationsQuery: () => mockIntegrations,
    useEffectiveIntegrationPolicyQuery: () => ({ data: undefined }),
    useTestConnectionMutation: mutation,
    useUpdateConnectionMutation: mutation,
    useRevokeConnectionMutation: mutation,
    useDeleteConnectionMutation: mutation,
    useCreateConnectionMutation: () => ({ mutateAsync: mockCreate }),
    useRenewConnectionTokenMutation: mutation,
    useStartOAuthMutation: () => ({
      mutateAsync: jest.fn().mockResolvedValue({
        authorization_url: "https://idp.test/consent",
      }),
    }),
    usePendingConnectionPoll: () => mockPoll,
    useOAuthRegistrationsQuery: () => mockRegistrations,
  };
});

jest.mock("@/controllers/API/queries/flows/use-get-types", () => ({
  useGetTypes: jest.fn(),
}));

jest.mock("@/customization/components/custom-connection-authorization", () => ({
  ...jest.requireActual(
    "@/customization/components/custom-connection-authorization",
  ),
  openAuthorizationUrl: jest.fn(),
}));

jest.mock("@/customization/components/custom-connections-tabs", () => ({
  __esModule: true,
  default: () => mockExtraTabs,
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ userData: mockUser }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
      setNoticeData: mockSetNoticeData,
    }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const connection = (
  overrides: Partial<ConnectionRead> & Pick<ConnectionRead, "id">,
): ConnectionRead => ({
  owner_id: null,
  ownership_mode: "user",
  provider_key: "google",
  name: overrides.id.replace(/-/g, "_"),
  display_name: overrides.id,
  status: "ready",
  status_reason: null,
  health: "healthy",
  granted_scopes: [],
  executing_identity: { identity: "user_delegated" },
  allow_non_interactive: false,
  has_credentials: true,
  health_checked_at: null,
  created_at: "2026-09-18T00:00:00Z",
  updated_at: "2026-09-18T00:00:00Z",
  ...overrides,
});

const panel = () => screen.getByTestId("connections-list");

const filterByOwner = async (name: string) => {
  const user = userEvent.setup();
  await user.click(screen.getByRole("combobox", { name: "Owner" }));
  await user.click(screen.getByRole("option", { name }));
};

describe("ConnectionsPage", () => {
  beforeAll(() => {
    // Radix Select uses browser APIs that jsdom does not implement.
    Element.prototype.hasPointerCapture ??= jest.fn(() => false);
    Element.prototype.setPointerCapture ??= jest.fn();
    Element.prototype.releasePointerCapture ??= jest.fn();
    Element.prototype.scrollIntoView ??= jest.fn();
  });

  beforeEach(() => {
    mockMutation.mockReset();
    mockSetErrorData.mockReset();
    mockSetSuccessData.mockReset();
    mockSetNoticeData.mockReset();
    mockCreate.mockReset();
    mockPoll.data = undefined;
    mockRegistrations.data[0].scopes = [];
    mockExtraTabs = [];
  });

  afterEach(async () => {
    jest.restoreAllMocks();
    await act(() => i18n.changeLanguage("en"));
  });

  it.each(["instance", "user"] as const)(
    "reveals a newly authorized %s connection and clears the old search",
    async (ownership) => {
      mockUser = { id: SUPERUSER_ID, is_superuser: true };
      mockConnections = [];
      mockIntegrations = {
        data: {
          providers: [
            {
              provider_id: "google",
              display_name: "Google",
              capabilities: [],
            },
          ],
        },
        isSuccess: true,
      };
      const ready = connection({
        id: "new-connection",
        owner_id: ownership === "user" ? SUPERUSER_ID : null,
        ownership_mode: ownership,
        display_name: "New connection",
        updated_at: "2026-09-18T00:01:00Z",
      });
      mockCreate.mockResolvedValue({
        ...ready,
        status: "pending",
        has_credentials: false,
        updated_at: "2026-09-18T00:00:00Z",
      });
      jest.spyOn(window, "open").mockReturnValue({
        close: jest.fn(),
        closed: false,
      } as unknown as Window);
      const { rerender } = render(<ConnectionsPage />);
      const user = userEvent.setup();
      if (ownership === "user") await filterByOwner("Instance");
      await user.type(screen.getByTestId("connections-search"), "old search");
      await user.click(screen.getByTestId("add-connection"));
      await user.type(screen.getByTestId("connection-name"), "new_connection");
      if (ownership === "instance") {
        await user.click(screen.getByTestId("connection-instance-owned"));
      }
      await user.click(screen.getByTestId("connection-continue"));
      mockConnections = [ready];
      mockPoll.data = ready;
      rerender(<ConnectionsPage />);
      expect(await screen.findByText("Connected")).toBeVisible();
      await user.click(screen.getByTestId("connection-done"));
      expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent(
        ownership === "instance" ? "Instance" : "Mine",
      );
      expect(screen.getByTestId("connections-search")).toHaveValue("");
      expect(screen.getByTestId("connection-row-new_connection")).toBeVisible();
      mockIntegrations = { data: { providers: [] } };
    },
  );

  it("keeps a superuser's reauthorized connection visible under Other users", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    const previous = connection({
      id: "other",
      owner_id: OTHER_ID,
      granted_scopes: ["openid"],
    });
    const ready = { ...previous, updated_at: "2026-09-18T00:01:00Z" };
    mockConnections = [previous];
    mockRegistrations.data[0].scopes = ["openid"];
    jest.spyOn(window, "open").mockReturnValue({
      close: jest.fn(),
      closed: false,
    } as unknown as Window);
    const { rerender } = render(<ConnectionsPage />);
    const user = userEvent.setup();
    await filterByOwner("Other users");
    await user.click(screen.getByTestId("connection-menu-other"));
    await user.click(screen.getByRole("menuitem", { name: "Reconnect" }));
    await user.click(screen.getByTestId("connection-authorize"));
    mockConnections = [ready];
    mockPoll.data = ready;
    rerender(<ConnectionsPage />);
    expect(await screen.findByText("Connected")).toBeVisible();
    await user.click(screen.getByTestId("connection-done"));
    expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent(
      "Other users",
    );
    expect(screen.getByTestId("connection-row-other")).toBeVisible();
  });

  it.each(["ready", "pending", "expired", "revoked", "error"] as const)(
    "shows another user's %s ServiceNow connection as unavailable",
    async (status) => {
      mockUser = { id: SUPERUSER_ID, is_superuser: true };
      mockConnections = [
        connection({
          id: "other_servicenow",
          provider_key: "servicenow",
          owner_id: OTHER_ID,
          status,
        }),
      ];
      const user = userEvent.setup();
      render(<ConnectionsPage />);

      await filterByOwner("Other users");
      const row = screen.getByTestId("connection-row-other_servicenow");
      expect(within(row).getByText("Unavailable")).toBeVisible();
      expect(
        within(row).getByText(
          "Only the connection owner can authorize and use this ServiceNow connection.",
        ),
      ).toBeVisible();
      expect(
        screen.queryByTestId("authorize-other_servicenow"),
      ).not.toBeInTheDocument();
      await user.click(screen.getByTestId("connection-menu-other_servicenow"));

      expect(
        screen.queryByRole("menuitem", { name: /^(Authorize|Reconnect)$/ }),
      ).not.toBeInTheDocument();
      expect(screen.getByRole("menuitem", { name: "Rename" })).toBeVisible();
    },
  );

  it("does not offer authorization for a legacy instance ServiceNow connection", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "instance_servicenow",
        provider_key: "servicenow",
        ownership_mode: "instance",
        status: "pending",
      }),
    ];
    const user = userEvent.setup();
    render(<ConnectionsPage />);

    await filterByOwner("Instance");
    expect(
      within(
        screen.getByTestId("connection-row-instance_servicenow"),
      ).getByText("Unavailable"),
    ).toBeVisible();
    expect(
      screen.queryByTestId("authorize-instance_servicenow"),
    ).not.toBeInTheDocument();
    await user.click(screen.getByTestId("connection-menu-instance_servicenow"));

    expect(
      screen.queryByRole("menuitem", { name: "Authorize" }),
    ).not.toBeInTheDocument();
  });

  it.each(["menu", "status"] as const)(
    "lets a ServiceNow owner open authorization from the %s action",
    async (entryPoint) => {
      mockUser = { id: SUPERUSER_ID, is_superuser: true };
      mockConnections = [
        connection({
          id: "my_servicenow",
          provider_key: "servicenow",
          owner_id: SUPERUSER_ID,
          status: "pending",
        }),
      ];
      const user = userEvent.setup();
      render(<ConnectionsPage />);

      expect(
        within(screen.getByTestId("connection-row-my_servicenow")).getByText(
          "Pending",
        ),
      ).toBeVisible();

      if (entryPoint === "menu") {
        await user.click(screen.getByTestId("connection-menu-my_servicenow"));
        await user.click(screen.getByRole("menuitem", { name: "Authorize" }));
      } else {
        await user.click(screen.getByTestId("authorize-my_servicenow"));
      }

      expect(screen.getByRole("dialog")).toBeVisible();
      expect(screen.getByTestId("connection-authorize")).toBeInTheDocument();
    },
  );

  it("disables Add connection and explains why when policy leaves no provider", () => {
    mockIntegrations = { data: { providers: [] }, isSuccess: true };
    mockUser = { id: SUPERUSER_ID, is_superuser: false };
    mockConnections = [];
    try {
      render(<ConnectionsPage />);
      expect(screen.getByTestId("add-connection")).toBeDisabled();
      expect(screen.getByTestId("connections-no-providers")).toHaveTextContent(
        /administrator controls/i,
      );
      expect(screen.getByRole("status")).toHaveTextContent(
        /administrator controls/i,
      );
    } finally {
      mockIntegrations = { data: { providers: [] } };
    }
  });

  it.each([
    ["loading", { data: undefined, isLoading: true }],
    ["failed", { data: undefined, isError: true }],
  ])(
    "keeps Add connection disabled without blaming policy while the provider list is %s",
    (_state, query) => {
      mockIntegrations = query;
      mockUser = { id: SUPERUSER_ID, is_superuser: false };
      mockConnections = [];
      try {
        render(<ConnectionsPage />);
        expect(screen.getByTestId("add-connection")).toBeDisabled();
        expect(
          screen.getByTestId("connections-no-providers"),
        ).toBeEmptyDOMElement();
      } finally {
        mockIntegrations = { data: { providers: [] } };
      }
    },
  );

  it("shows the initial empty state only when there are no connections", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [];
    render(<ConnectionsPage />);

    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No connections yet.",
    );
  });

  it.each([
    ["Mine", "No connections match this owner filter.", "instance"],
    ["Instance", "No instance connections yet.", "user"],
    ["Other users", "No connections from other users yet.", "user"],
  ] as const)(
    "describes an empty %s filter",
    async (owner, message, ownership) => {
      mockUser = { id: SUPERUSER_ID, is_superuser: true };
      mockConnections = [
        connection({
          id: "existing",
          owner_id: SUPERUSER_ID,
          ownership_mode: ownership,
        }),
      ];
      render(<ConnectionsPage />);
      await filterByOwner(owner);

      expect(screen.getByTestId("connections-empty")).toHaveTextContent(
        message,
      );
    },
  );

  it("distinguishes search misses from an empty owner filter and restores rows when cleared", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [connection({ id: "my-gmail", owner_id: SUPERUSER_ID })];
    const user = userEvent.setup();
    render(<ConnectionsPage />);

    await user.type(screen.getByTestId("connections-search"), "unmatched");
    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No connections match your search.",
    );

    await filterByOwner("Instance");
    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No instance connections yet.",
    );

    await filterByOwner("Mine");
    await user.clear(screen.getByTestId("connections-search"));
    expect(within(panel()).getByText("my-gmail")).toBeInTheDocument();
    expect(screen.queryByTestId("connections-empty")).not.toBeInTheDocument();
  });

  it("keeps other users' private connections out of a superuser's Mine filter", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({ id: "admin-gmail", owner_id: SUPERUSER_ID }),
      connection({ id: "bob-slack", owner_id: OTHER_ID }),
      connection({ id: "team-calendar", ownership_mode: "instance" }),
    ];
    render(<ConnectionsPage />);

    // Mine is the superuser's own rows only. Before the fix every other
    // user's private connection landed here too, because a superuser's list is
    // unfiltered and Mine was simply "anything not instance-owned".
    expect(within(panel()).getByText("admin-gmail")).toBeInTheDocument();
    expect(within(panel()).queryByText("bob-slack")).not.toBeInTheDocument();
    expect(
      within(panel()).queryByText("team-calendar"),
    ).not.toBeInTheDocument();

    await filterByOwner("Other users");
    expect(within(panel()).getByText("bob-slack")).toBeInTheDocument();
    expect(within(panel()).getByText("Other user")).toBeInTheDocument();
    expect(within(panel()).queryByText("Shared")).not.toBeInTheDocument();
    expect(within(panel()).queryByText("admin-gmail")).not.toBeInTheDocument();

    await filterByOwner("Instance");
    expect(within(panel()).getByText("team-calendar")).toBeInTheDocument();
    expect(within(panel()).queryByText("bob-slack")).not.toBeInTheDocument();
  });

  it("distinguishes bot and user identities with the same provider account", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "slack-user",
        owner_id: SUPERUSER_ID,
        executing_identity: {
          identity: "user_delegated",
          account: { id: "workspace", display: "Team workspace" },
        },
      }),
      connection({
        id: "slack-bot",
        owner_id: SUPERUSER_ID,
        executing_identity: {
          identity: "bot",
          account: { id: "workspace", display: "Team workspace" },
        },
      }),
    ];
    render(<ConnectionsPage />);

    expect(
      within(screen.getByTestId("connection-row-slack_user")).getByText(
        "The signed-in user",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("connection-row-slack_bot")).getByText("A bot"),
    ).toBeInTheDocument();
  });

  it("shows a captured Microsoft account and an accurate fallback for older connections", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "microsoft-new",
        provider_key: "microsoft",
        owner_id: SUPERUSER_ID,
        executing_identity: {
          identity: "user_delegated",
          account: { id: "user-object-id", display: "user@example.com" },
        },
      }),
      connection({
        id: "microsoft-old",
        provider_key: "microsoft",
        owner_id: SUPERUSER_ID,
      }),
    ];
    render(<ConnectionsPage />);

    expect(
      within(screen.getByTestId("connection-row-microsoft_new")).getByText(
        "user@example.com",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("connection-row-microsoft_old")).getByText(
        "Account unavailable",
      ),
    ).toBeInTheDocument();
  });

  it("shows the GitHub installation account and App-managed permissions without changing OAuth scope labels", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "github-work",
        provider_key: "github",
        owner_id: SUPERUSER_ID,
        executing_identity: {
          identity: "service",
          account: { id: "80", display: "installation-owner" },
        },
      }),
      connection({ id: "google-empty", owner_id: SUPERUSER_ID }),
      connection({
        id: "google-scoped",
        owner_id: SUPERUSER_ID,
        granted_scopes: ["https://www.googleapis.com/auth/drive.readonly"],
      }),
    ];
    mockIntegrations = {
      data: {
        providers: [
          {
            provider_id: "github",
            display_name: "GitHub",
            approved: true,
            enabled: true,
            connection_count: 1,
            capabilities: [],
            manual_token_profiles: [
              {
                id: "github-installation",
                identity: "service",
                required_scopes: [],
              },
            ],
          },
        ],
      },
    };
    try {
      render(<ConnectionsPage />);

      const github = within(screen.getByTestId("connection-row-github_work"));
      expect(github.getByText("installation-owner")).toBeInTheDocument();
      expect(github.getByText("Ready")).toBeInTheDocument();
      expect(github.getByText("Managed by the GitHub App")).toBeInTheDocument();
      expect(github.queryByText("No scopes granted")).not.toBeInTheDocument();
      expect(
        within(screen.getByTestId("connection-row-google_empty")).getByText(
          "No scopes granted",
        ),
      ).toBeInTheDocument();
      expect(
        within(screen.getByTestId("connection-row-google_scoped")).getByText(
          "1 scope",
        ),
      ).toBeInTheDocument();
    } finally {
      mockIntegrations = { data: { providers: [] } };
    }
  });

  it("shows a denied reauthorization without hiding a still-ready credential", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "slack-ready",
        owner_id: SUPERUSER_ID,
        status_reason: "oauth-denied",
      }),
    ];
    render(<ConnectionsPage />);

    const row = within(screen.getByTestId("connection-row-slack_ready"));
    expect(row.getByText("Ready")).toBeInTheDocument();
    expect(
      row.getByText("The provider denied authorization."),
    ).toBeInTheDocument();
  });

  it("can delete a failed connection that has no credential", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "slack-failed",
        owner_id: SUPERUSER_ID,
        status: "error",
        status_reason: "oauth-denied",
        has_credentials: false,
      }),
    ];
    render(<ConnectionsPage />);

    await userEvent.click(screen.getByTestId("connection-menu-slack_failed"));
    expect(screen.getByRole("menuitem", { name: "Delete" })).toBeEnabled();
  });

  it("explains missing Jira refresh access while preserving a ready connection", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "jira-ready",
        owner_id: SUPERUSER_ID,
        provider_key: "jira",
        status_reason: "oauth-refresh-token-missing",
      }),
    ];
    render(<ConnectionsPage />);
    const row = within(screen.getByTestId("connection-row-jira_ready"));
    expect(row.getByText("Ready")).toBeVisible();
    expect(
      row.getByText(/Every Jira connection requires offline_access/),
    ).toBeVisible();
  });

  it.each(["confluence", "salesforce", "servicenow"])(
    "explains a missing refresh token for %s without Jira-specific advice",
    (provider) => {
      mockUser = { id: SUPERUSER_ID, is_superuser: true };
      mockConnections = [
        connection({
          id: "provider-ready",
          owner_id: SUPERUSER_ID,
          provider_key: provider,
          status_reason: "oauth-refresh-token-missing",
        }),
      ];
      render(<ConnectionsPage />);
      const row = within(screen.getByTestId("connection-row-provider_ready"));
      expect(row.getByText("Ready")).toBeVisible();
      expect(row.getByText(/did not return a refresh token/)).toBeVisible();
      expect(row.queryByText(/Jira|offline_access/)).not.toBeInTheDocument();
    },
  );

  it("gives a regular user no Other users filter and keeps shared rows under Mine", async () => {
    mockUser = { id: REGULAR_ID, is_superuser: false };
    // A regular user only ever receives another user's row when it was shared
    // with them, so it belongs with their own.
    mockConnections = [
      connection({ id: "my-drive", owner_id: REGULAR_ID }),
      connection({ id: "shared-outlook", owner_id: OTHER_ID }),
      connection({ id: "team-calendar", ownership_mode: "instance" }),
    ];
    render(<ConnectionsPage />);

    expect(
      screen.queryByRole("tab", { name: "Other users" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: "Manage providers" }),
    ).not.toBeInTheDocument();
    expect(within(panel()).getByText("my-drive")).toBeInTheDocument();
    expect(within(panel()).getByText("shared-outlook")).toBeInTheDocument();
    expect(
      within(panel()).queryByText("team-calendar"),
    ).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("combobox", { name: "Owner" }));
    expect(
      screen.queryByRole("option", { name: "Other users" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Instance" }));
    expect(within(panel()).getByText("team-calendar")).toBeInTheDocument();
  });

  it("shows a single list without ownership tabs", () => {
    mockUser = { id: REGULAR_ID, is_superuser: false };
    mockConnections = [];
    render(<ConnectionsPage />);

    expect(screen.queryByRole("tablist")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent(
      "Mine",
    );
    expect(screen.getByRole("textbox", { name: /search name/i })).toBeVisible();
  });

  it("preserves separate policy tabs and restores the list's search and owner filter", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [connection({ id: "bob-slack", owner_id: OTHER_ID })];
    const renderPolicy = jest.fn(() => <p>Integration policy</p>);
    mockExtraTabs = [
      { value: "policy", label: "Policy", render: renderPolicy },
    ];
    const user = userEvent.setup();
    const { container } = render(<ConnectionsPage />);

    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Connections",
      "Manage providers",
      "Policy",
    ]);
    for (const tab of screen.getAllByRole("tab")) {
      const controls = tab.getAttribute("aria-controls");
      expect(controls).toBeTruthy();
      expect(
        container.ownerDocument.getElementById(controls as string),
      ).not.toBeNull();
    }
    expect(renderPolicy).not.toHaveBeenCalled();
    await filterByOwner("Other users");
    await user.type(
      screen.getByRole("textbox", { name: /search name/i }),
      "slack",
    );
    await user.click(screen.getByRole("tab", { name: "Policy" }));
    expect(screen.getByText("Integration policy")).toBeVisible();
    expect(
      screen.queryByRole("combobox", { name: "Owner" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Connections" }));
    expect(screen.getByRole("combobox", { name: "Owner" })).toHaveTextContent(
      "Other users",
    );
    expect(screen.getByRole("textbox", { name: /search name/i })).toHaveValue(
      "slack",
    );
    expect(within(panel()).getByText("bob-slack")).toBeVisible();
  });

  it("sorts other users' connections by status and actual health-check time using the keyboard", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "alpha",
        owner_id: OTHER_ID,
        status: "ready",
        health_checked_at: "2026-09-21T09:00:00Z",
      }),
      connection({
        id: "bravo",
        owner_id: OTHER_ID,
        status: "expired",
        health_checked_at: null,
      }),
      connection({
        id: "charlie",
        owner_id: OTHER_ID,
        status: "pending",
        health_checked_at: "2026-09-21T09:30:00+02:00",
      }),
    ];
    const original = [...mockConnections];
    const user = userEvent.setup();
    render(<ConnectionsPage />);
    await filterByOwner("Other users");
    const order = () =>
      within(panel())
        .getAllByTestId(/^connection-row-/)
        .map((row) => row.getAttribute("data-testid"));
    expect(order()).toEqual([
      "connection-row-alpha",
      "connection-row-bravo",
      "connection-row-charlie",
    ]);

    const status = within(panel()).getByRole("button", {
      name: "Status",
    });
    status.focus();
    await user.keyboard("{Enter}");
    expect(order()).toEqual([
      "connection-row-bravo",
      "connection-row-charlie",
      "connection-row-alpha",
    ]);
    expect(status.closest("th")).toHaveAttribute("aria-sort", "ascending");
    await user.keyboard("{Enter}");
    expect(order()).toEqual([
      "connection-row-alpha",
      "connection-row-charlie",
      "connection-row-bravo",
    ]);
    expect(status.closest("th")).toHaveAttribute("aria-sort", "descending");

    const lastCheck = within(panel()).getByTestId("connections-sort-lastCheck");
    await user.click(lastCheck);
    expect(order()).toEqual([
      "connection-row-charlie",
      "connection-row-alpha",
      "connection-row-bravo",
    ]);
    await user.click(lastCheck);
    expect(order()).toEqual([
      "connection-row-alpha",
      "connection-row-charlie",
      "connection-row-bravo",
    ]);
    expect(mockConnections).toEqual(original);

    await user.type(screen.getByTestId("connections-search"), "unmatched");
    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No connections match your search.",
    );
    await user.clear(screen.getByTestId("connections-search"));
    expect(order()).toEqual([
      "connection-row-alpha",
      "connection-row-charlie",
      "connection-row-bravo",
    ]);
    expect(
      screen.getByTestId("connections-sort-lastCheck").closest("th"),
    ).toHaveAttribute("aria-sort", "descending");

    await filterByOwner("Instance");
    await filterByOwner("Other users");
    expect(order()).toEqual([
      "connection-row-alpha",
      "connection-row-charlie",
      "connection-row-bravo",
    ]);
    expect(
      screen.getByTestId("connections-sort-lastCheck").closest("th"),
    ).toHaveAttribute("aria-sort", "descending");
  });

  it("breaks owner-label ties by connection name instead of owner ID", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({ id: "alpha", owner_id: "user-z" }),
      connection({ id: "bravo", owner_id: "user-a" }),
    ];
    const user = userEvent.setup();
    render(<ConnectionsPage />);
    await filterByOwner("Other users");
    const ownerSort = screen.getByTestId("connections-sort-owner");
    for (const direction of ["ascending", "descending"]) {
      await user.click(ownerSort);
      expect(ownerSort.closest("th")).toHaveAttribute("aria-sort", direction);
      expect(
        screen
          .getAllByTestId(/^connection-row-/)
          .map((row) => row.dataset.testid),
      ).toEqual(["connection-row-alpha", "connection-row-bravo"]);
    }
  });

  it.each([
    ["revoked", "Connection revoked and token revoked at the provider."],
    [
      "failed",
      "Credential removed from Langflow, but provider revocation failed. Revoke the token in the provider's settings.",
    ],
    [
      "unsupported",
      "Credential removed from Langflow. The token may still be valid at the provider. Revoke it in the provider's settings.",
    ],
    [
      "not_applicable",
      "Credential removed from Langflow. The token may still be valid at the provider. Revoke it in the provider's settings.",
    ],
  ])("reports the provider revocation outcome %s", async (outcome, title) => {
    mockUser = { id: REGULAR_ID, is_superuser: false };
    mockConnections = [connection({ id: "slack", owner_id: REGULAR_ID })];
    mockMutation.mockResolvedValueOnce({ provider_revocation: outcome });
    const user = userEvent.setup();
    render(<ConnectionsPage />);
    await user.click(screen.getByTestId("connection-menu-slack"));
    await user.click(screen.getByRole("menuitem", { name: "Revoke" }));
    const expectedAlert =
      outcome === "revoked" ? mockSetSuccessData : mockSetNoticeData;
    await waitFor(() => expect(expectedAlert).toHaveBeenCalledWith({ title }));
    expect(mockMutation).toHaveBeenCalledWith("slack");
    expect(mockSetErrorData).not.toHaveBeenCalled();
    if (outcome !== "revoked") {
      expect(mockSetSuccessData).not.toHaveBeenCalled();
    }
  });

  it.each([
    ["Test", "ready", "Network Error"],
    ["Test", "ready", "timeout of 30000ms exceeded"],
    ["Revoke", "ready", "Network Error"],
    ["Revoke", "ready", "timeout of 30000ms exceeded"],
    ["Delete", "revoked", "Network Error"],
    ["Delete", "revoked", "timeout of 30000ms exceeded"],
  ] as const)(
    "shows a Portuguese fallback when %s fails with %s / %s",
    async (action, status, message) => {
      await loadLanguage("pt");
      await act(() => i18n.changeLanguage("pt"));
      mockUser = { id: REGULAR_ID, is_superuser: false };
      mockConnections = [
        connection({ id: "gmail", owner_id: REGULAR_ID, status }),
      ];
      mockMutation.mockRejectedValueOnce(new AxiosError(message));
      const user = userEvent.setup();
      render(
        <I18nextProvider i18n={i18n}>
          <ConnectionsPage />
        </I18nextProvider>,
      );
      await user.click(screen.getByTestId("connection-menu-gmail"));
      await user.click(
        screen.getByRole("menuitem", {
          name: i18n.t(`connections.actions.${action.toLowerCase()}`),
        }),
      );
      await waitFor(() =>
        expect(mockSetErrorData).toHaveBeenCalledWith({
          title: "Não foi possível concluir",
          list: ["O servidor recusou a solicitação."],
        }),
      );
      expect(mockMutation).toHaveBeenCalledTimes(1);
    },
  );
});
