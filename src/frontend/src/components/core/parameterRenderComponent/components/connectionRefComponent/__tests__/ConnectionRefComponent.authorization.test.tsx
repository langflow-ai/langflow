import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import {
  listConnections,
  listIntegrations,
} from "@/controllers/API/queries/connections/api";
import useAuthStore from "@/stores/authStore";
import ConnectionRefComponent from "../index";

const mockCreate = jest.fn();
const mockTypesState = { data: {} };
const mockRegistrations = { data: [], isSuccess: true };

jest.mock("@/controllers/API/queries/connections/api", () => ({
  listConnections: jest.fn(),
  listIntegrations: jest.fn(),
}));
jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useCreateConnectionMutation: () => ({ mutateAsync: mockCreate }),
  useRenewConnectionTokenMutation: () => ({ mutateAsync: jest.fn() }),
  useStartOAuthMutation: () => ({ mutateAsync: jest.fn() }),
  useDeleteConnectionMutation: () => ({ mutate: jest.fn() }),
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
jest.mock("@/customization/components/custom-connection-authorization", () => ({
  openAuthorizationUrl: jest.fn(),
  resolveRegistrationId: () => null,
}));

const telegram: IntegrationProviderRead = {
  provider_id: "telegram",
  display_name: "Telegram",
  approved: true,
  enabled: false,
  connection_count: 0,
  capabilities: [
    {
      id: "telegram.send",
      display_name: "Send",
      policy_keys: [],
      risk: "write",
      maturity: "preview",
      substrate: "rest",
      identity: "bot",
      auth_profile_id: "telegram-token",
      deployment_contexts: ["self_managed"],
      allowed: true,
    },
  ],
  manual_token_profiles: [
    { id: "telegram-token", identity: "bot", required_scopes: [] },
  ],
};
const ready: ConnectionRead = {
  id: "telegram-new",
  provider_key: "telegram",
  name: "new",
  display_name: "New Telegram",
  owner_id: "user-1",
  ownership_mode: "user",
  status: "ready",
  health: "healthy",
  executing_identity: { identity: "bot" },
  granted_scopes: [],
  allow_non_interactive: false,
  has_credentials: true,
  health_checked_at: null,
  created_at: "2026-11-10T00:00:00Z",
  updated_at: "2026-11-10T00:00:00Z",
};

function renderPicker() {
  const onChange = jest.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Picker() {
    const [value, setValue] = useState("telegram/work");
    return (
      <ConnectionRefComponent
        id="telegram-picker"
        editNode={false}
        disabled={false}
        provider="telegram"
        requiredScopes={[]}
        identityKind="instance"
        ownershipMode="user"
        value={value}
        handleOnNewValue={(update) => {
          onChange(update);
          setValue(update.value);
        }}
      />
    );
  }
  render(
    <QueryClientProvider client={client}>
      <Picker />
    </QueryClientProvider>,
  );
  return onChange;
}

async function fillConnection(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox"));
  const add = await screen.findByRole("button", { name: "Add connection" });
  await waitFor(() => expect(add).toBeEnabled());
  await user.click(add);
  await user.type(screen.getByTestId("connection-name"), "new");
  await user.type(
    screen.getByTestId("connection-token"),
    "example-provider-token",
  );
}

describe("shared connection dialog on the canvas", () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = jest.fn();
  });
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({ userData: { id: "user-1" } as never });
    jest
      .mocked(listConnections)
      .mockResolvedValue([{ ...ready, id: "telegram-work", name: "work" }]);
    jest.mocked(listIntegrations).mockResolvedValue({
      providers: [telegram],
      deployment_context: "self_managed",
    });
    mockCreate.mockResolvedValue(ready);
  });

  it("selects a validated connection only after completing the real dialog", async () => {
    const user = userEvent.setup();
    const onChange = renderPicker();
    await fillConnection(user);
    expect(screen.getByTestId("connection-provider")).toHaveTextContent(
      "Telegram",
    );

    await user.click(screen.getByTestId("connection-continue"));

    expect(await screen.findByTestId("connection-done")).toBeVisible();
    expect(onChange).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("connection-done"));
    expect(onChange).toHaveBeenCalledWith({ value: "telegram/new" });
    expect(screen.getByRole("combobox")).toHaveTextContent("telegram/new");
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus());
  });

  it("leaves the original connection selected when validation fails", async () => {
    const user = userEvent.setup();
    mockCreate.mockRejectedValue({
      isAxiosError: true,
      response: {
        data: { detail: "Provider rejected this token" },
        status: 400,
      },
    });
    const onChange = renderPicker();
    await fillConnection(user);

    await user.click(screen.getByTestId("connection-continue"));

    expect(
      await screen.findByText("Provider rejected this token"),
    ).toBeVisible();
    expect(onChange).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("combobox")).toHaveTextContent("telegram/work");
  });
});
