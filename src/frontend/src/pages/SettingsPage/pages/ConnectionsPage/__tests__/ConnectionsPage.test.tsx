import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError } from "axios";
import { I18nextProvider } from "react-i18next";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import i18n, { loadLanguage } from "@/i18n";
import ConnectionsPage from "../index";

jest.unmock("react-i18next");

const SUPERUSER_ID = "user-admin";
const REGULAR_ID = "user-regular";
const OTHER_ID = "user-bob";

let mockUser: { id: string; is_superuser: boolean };
let mockConnections: ConnectionRead[];
const mockMutation = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@/controllers/API/queries/connections", () => {
  const mutation = () => ({ mutate: jest.fn(), mutateAsync: mockMutation });
  return {
    ...jest.requireActual("@/controllers/API/queries/connections"),
    useGetConnections: () => ({ data: mockConnections, isLoading: false }),
    useIntegrationsQuery: () => ({ data: { providers: [] } }),
    useEffectiveIntegrationPolicyQuery: () => ({ data: undefined }),
    useTestConnectionMutation: mutation,
    useUpdateConnectionMutation: mutation,
    useRevokeConnectionMutation: mutation,
    useDeleteConnectionMutation: mutation,
  };
});

jest.mock("@/customization/components/custom-connections-tabs", () => ({
  __esModule: true,
  default: () => [],
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ userData: mockUser }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: mockSetErrorData, setSuccessData: jest.fn() }),
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

const panel = () => screen.getByRole("tabpanel");

const openTab = async (name: string) => {
  await userEvent.setup().click(screen.getByRole("tab", { name }));
};

describe("ConnectionsPage tabs", () => {
  beforeEach(() => {
    mockMutation.mockReset();
    mockSetErrorData.mockReset();
  });

  afterEach(async () => {
    await act(() => i18n.changeLanguage("en"));
  });

  it("shows the initial empty state only when there are no connections", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [];
    render(<ConnectionsPage />);

    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No connections yet.",
    );
  });

  it.each([
    ["Mine", "No connections in this tab yet.", "instance"],
    ["Instance", "No instance connections yet.", "user"],
    ["Other users", "No connections from other users yet.", "user"],
  ] as const)("describes an empty %s tab", async (tab, message, ownership) => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [
      connection({
        id: "existing",
        owner_id: SUPERUSER_ID,
        ownership_mode: ownership,
      }),
    ];
    render(<ConnectionsPage />);
    await openTab(tab);

    expect(screen.getByTestId("connections-empty")).toHaveTextContent(message);
  });

  it("distinguishes search misses from an empty tab and restores rows when cleared", async () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [connection({ id: "my-gmail", owner_id: SUPERUSER_ID })];
    const user = userEvent.setup();
    render(<ConnectionsPage />);

    await user.type(screen.getByTestId("connections-search"), "unmatched");
    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No connections match your search.",
    );

    await openTab("Instance");
    expect(screen.getByTestId("connections-empty")).toHaveTextContent(
      "No instance connections yet.",
    );

    await openTab("Mine");
    await user.clear(screen.getByTestId("connections-search"));
    expect(within(panel()).getByText("my-gmail")).toBeInTheDocument();
    expect(screen.queryByTestId("connections-empty")).not.toBeInTheDocument();
  });

  it("keeps other users' private connections out of a superuser's Mine tab", async () => {
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

    await openTab("Other users");
    expect(within(panel()).getByText("bob-slack")).toBeInTheDocument();
    expect(within(panel()).getByText("Other user")).toBeInTheDocument();
    expect(within(panel()).queryByText("Shared")).not.toBeInTheDocument();
    expect(within(panel()).queryByText("admin-gmail")).not.toBeInTheDocument();

    await openTab("Instance");
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

  it("gives a regular user no Other users tab and keeps shared rows under Mine", async () => {
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
    expect(within(panel()).getByText("my-drive")).toBeInTheDocument();
    expect(within(panel()).getByText("shared-outlook")).toBeInTheDocument();
    expect(
      within(panel()).queryByText("team-calendar"),
    ).not.toBeInTheDocument();

    await openTab("Instance");
    expect(within(panel()).getByText("team-calendar")).toBeInTheDocument();
  });

  it("gives every tab trigger a mounted panel so aria-controls resolves", () => {
    mockUser = { id: SUPERUSER_ID, is_superuser: true };
    mockConnections = [];
    const { container } = render(<ConnectionsPage />);

    for (const tab of screen.getAllByRole("tab")) {
      const controls = tab.getAttribute("aria-controls");
      expect(controls).toBeTruthy();
      expect(
        container.ownerDocument.getElementById(controls as string),
      ).not.toBeNull();
    }
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
    await openTab("Other users");
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

    await openTab("Instance");
    await openTab("Other users");
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
    await openTab("Other users");
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
