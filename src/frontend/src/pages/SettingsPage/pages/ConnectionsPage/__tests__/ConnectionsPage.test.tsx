import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionRead } from "@/controllers/API/queries/connections";
import ConnectionsPage from "../index";

const SUPERUSER_ID = "user-admin";
const REGULAR_ID = "user-regular";
const OTHER_ID = "user-bob";

let mockUser: { id: string; is_superuser: boolean };
let mockConnections: ConnectionRead[];

jest.mock("@/controllers/API/queries/connections", () => {
  const mutation = () => ({ mutate: jest.fn(), mutateAsync: jest.fn() });
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
    selector({ setErrorData: jest.fn(), setSuccessData: jest.fn() }),
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
    expect(within(panel()).queryByText("admin-gmail")).not.toBeInTheDocument();

    await openTab("Instance");
    expect(within(panel()).getByText("team-calendar")).toBeInTheDocument();
    expect(within(panel()).queryByText("bob-slack")).not.toBeInTheDocument();
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
});
