import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import {
  listConnections,
  listIntegrations,
} from "@/controllers/API/queries/connections/api";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections/types";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import ConnectionRefComponent from "../index";

jest.mock("@/controllers/API/queries/connections/api", () => ({
  listConnections: jest.fn(),
  listIntegrations: jest.fn(),
}));

// The shared dialog owns authorization and already tests its OAuth/token
// lifecycle. Keep the real dialog primitives here to exercise the canvas
// handoff and focus restoration around its public completion callback.
jest.mock(
  "@/pages/SettingsPage/pages/ConnectionsPage/components/AddConnectionDialog",
  () => ({
    __esModule: true,
    default: (
      props: import("@/pages/SettingsPage/pages/ConnectionsPage/components/AddConnectionDialog").AddConnectionDialogProps,
    ) => {
      const { Dialog, DialogContent, DialogTitle } = jest.requireActual(
        "@/components/ui/dialog",
      );
      return (
        <Dialog open={props.open} onOpenChange={props.onOpenChange}>
          <DialogContent>
            <DialogTitle>Add connection</DialogTitle>
            <p>
              {props.providers
                .map((provider) => provider.provider_id)
                .join(", ")}
            </p>
            <p>{props.deploymentContext}</p>
            {props.canCreateInstance && <p>Instance sharing available</p>}
            <button type="button" onClick={() => props.onOpenChange(false)}>
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                props.onConnected?.(mockCreatedConnection);
                props.onOpenChange(false);
              }}
            >
              Finish authorization
            </button>
          </DialogContent>
        </Dialog>
      );
    },
  }),
);

const mockListConnections = jest.mocked(listConnections);
const mockListIntegrations = jest.mocked(listIntegrations);
const GOOGLE_SEND = "https://www.googleapis.com/auth/gmail.send";

const google: IntegrationProviderRead = {
  provider_id: "google",
  display_name: "Google",
  approved: true,
  enabled: false,
  connection_count: 0,
  capabilities: [],
};

function connection(overrides: Partial<ConnectionRead> = {}): ConnectionRead {
  return {
    id: "new-connection",
    owner_id: "user-1",
    ownership_mode: "user",
    provider_key: "google",
    name: "new",
    display_name: "New Google",
    status: "ready",
    health: "healthy",
    granted_scopes: [GOOGLE_SEND],
    executing_identity: { identity: "user_delegated" },
    allow_non_interactive: false,
    has_credentials: true,
    health_checked_at: null,
    created_at: "2026-11-10T00:00:00Z",
    updated_at: "2026-11-10T00:00:00Z",
    ...overrides,
  };
}

let mockCreatedConnection = connection();

function renderPicker(props: Record<string, unknown> = {}) {
  const handleOnNewValue = jest.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Picker() {
    const [value, setValue] = useState(
      (props.value as string | undefined) ?? "",
    );
    return (
      <ConnectionRefComponent
        id="canvas-connection"
        editNode={false}
        disabled={false}
        provider="google"
        requiredScopes={[GOOGLE_SEND]}
        {...props}
        value={value}
        handleOnNewValue={(update) => {
          handleOnNewValue(update);
          setValue(update.value);
        }}
      />
    );
  }
  const result = render(
    <QueryClientProvider client={client}>
      <Picker />
    </QueryClientProvider>,
  );
  return { ...result, client, handleOnNewValue };
}

async function openCreation(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox"));
  const add = await screen.findByRole("button", { name: "Add connection" });
  await waitFor(() => expect(add).toBeEnabled());
  await user.click(add);
  return screen.findByRole("dialog", { name: "Add connection" });
}

describe("canvas connection creation", () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = jest.fn();
  });

  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({
      userData: { id: "user-1", is_superuser: false } as never,
    });
    useAlertStore.setState({ errorData: { title: "", list: [] } });
    mockCreatedConnection = connection();
    mockListConnections.mockResolvedValue([]);
    mockListIntegrations.mockResolvedValue({
      providers: [google],
      deployment_context: "hosted",
    });
  });

  it("offers Add connection when the provider has no connections", async () => {
    const user = userEvent.setup();
    renderPicker();

    const dialog = await openCreation(user);

    expect(within(dialog).getByText("google")).toBeVisible();
    expect(within(dialog).getByText("hosted")).toBeVisible();
    expect(
      within(dialog).queryByText("Instance sharing available"),
    ).not.toBeInTheDocument();
    expect(mockListIntegrations).toHaveBeenCalledWith({
      provider: "google",
      includeBlocked: undefined,
    });
  });

  it("selects the authorized handle and immediately lists the new connection", async () => {
    const user = userEvent.setup();
    const { handleOnNewValue } = renderPicker();
    await openCreation(user);

    await user.click(
      screen.getByRole("button", { name: "Finish authorization" }),
    );

    expect(handleOnNewValue).toHaveBeenCalledWith({ value: "google/new" });
    expect(screen.getByRole("combobox")).toHaveTextContent("google/new");
    expect(screen.getByRole("combobox")).not.toHaveTextContent("not found");
    await user.click(screen.getByRole("combobox"));
    expect(
      await screen.findByTestId("connection-option-google/new"),
    ).toBeVisible();
  });

  it("preserves the selected handle when creation is canceled", async () => {
    const user = userEvent.setup();
    mockListConnections.mockResolvedValue([
      connection({ id: "existing", name: "work" }),
    ]);
    const { handleOnNewValue } = renderPicker({ value: "google/work" });
    await openCreation(user);

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(handleOnNewValue).not.toHaveBeenCalled();
    expect(screen.getByRole("combobox")).toHaveTextContent("google/work");
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus());
  });

  it("does not offer blocked providers even when a stale component remains", async () => {
    const user = userEvent.setup();
    mockListIntegrations.mockResolvedValue({ providers: [] });
    renderPicker();

    await user.click(screen.getByRole("combobox"));

    expect(
      await screen.findByRole("button", { name: "Add connection" }),
    ).toBeDisabled();
    expect(
      await screen.findByText(
        "This integration is unavailable. An administrator controls which providers and actions can be used.",
      ),
    ).toBeVisible();
  });

  it("does not open creation while provider availability is loading", async () => {
    const user = userEvent.setup();
    mockListIntegrations.mockReturnValue(new Promise(() => {}));
    renderPicker();

    await user.click(screen.getByRole("combobox"));

    expect(
      screen.getByRole("button", { name: "Add connection" }),
    ).toBeDisabled();
  });

  it("explains a failed provider lookup and refresh retries it", async () => {
    const user = userEvent.setup();
    mockListIntegrations.mockRejectedValue(new Error("network unavailable"));
    renderPicker();
    await user.click(screen.getByRole("combobox"));

    expect(
      await screen.findByText(
        "Could not load integration availability. Refresh to try again.",
        {},
        { timeout: 4000 },
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Add connection" }),
    ).toBeDisabled();
    mockListIntegrations.mockResolvedValue({ providers: [google] });
    await user.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Add connection" }),
      ).toBeEnabled(),
    );
  });

  it.each([
    { status: "pending" as const },
    { granted_scopes: [] },
    { executing_identity: { identity: "bot" as const } },
    { ownership_mode: "instance" as const, owner_id: null },
  ])(
    "preserves the selection when an authorized row does not meet node requirements %j",
    async (overrides) => {
      const user = userEvent.setup();
      mockCreatedConnection = connection(overrides);
      const { handleOnNewValue } = renderPicker({
        value: "google/work",
        identityKind: "user",
        ownershipMode: "user",
      });
      await openCreation(user);

      await user.click(
        screen.getByRole("button", { name: "Finish authorization" }),
      );

      expect(handleOnNewValue).not.toHaveBeenCalled();
      expect(screen.getByRole("combobox")).toHaveTextContent("google/work");
      expect(useAlertStore.getState().errorData.title).toBe(
        "The connection was created, but it cannot be used by this component.",
      );
    },
  );

  it("supports opening creation from the keyboard and restores focus after Escape", async () => {
    const user = userEvent.setup();
    renderPicker();
    screen.getByRole("combobox").focus();
    await user.keyboard("{Enter}");
    const add = await screen.findByRole("button", { name: "Add connection" });
    await waitFor(() => expect(add).toBeEnabled());
    add.focus();
    await user.keyboard("{Enter}");
    expect(
      await screen.findByRole("dialog", { name: "Add connection" }),
    ).toBeVisible();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus());
  });

  it("does not request provider availability for a disabled node", () => {
    renderPicker({ disabled: true });

    expect(screen.getByRole("combobox")).toBeDisabled();
    expect(mockListIntegrations).not.toHaveBeenCalled();
  });
});
