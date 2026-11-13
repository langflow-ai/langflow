import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections/types";
import { useGetTypes } from "@/controllers/API/queries/flows/use-get-types";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import ConnectionRefComponent from "../index";

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
  },
}));

const FLOW_ID = "telegram-flow";
const palette = {
  telegram: {
    TelegramSendComponent: {
      display_name: "Telegram: Send Message",
      description: "Send a message",
      documentation: "",
      template: {},
    },
  },
};
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
  created_at: "2026-11-12T00:00:00Z",
  updated_at: "2026-11-12T00:00:00Z",
};

function Canvas({ onChange }: { onChange: jest.Mock }) {
  useGetTypes({ flowId: FLOW_ID });
  const types = useTypesStore((state) => state.types);
  const templates = useTypesStore((state) => state.templates);
  const [value, setValue] = useState("");

  // Match the canvas's palette prerequisite while keeping the real picker,
  // dialog, query hooks, and Zustand stores together.
  if (Object.keys(types).length === 0 || Object.keys(templates).length === 0) {
    return <p>Loading canvas...</p>;
  }

  return (
    <section aria-label="Flow canvas">
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
    </section>
  );
}

describe("canvas connection creation with the real component palette", () => {
  let client: QueryClient;

  beforeAll(() => {
    Element.prototype.scrollIntoView = jest.fn();
  });

  beforeEach(() => {
    jest.clearAllMocks();
    client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    client.setQueryData(["useGetTypes", FLOW_ID, undefined], palette);
    useTypesStore.setState({
      activeScopeKey: null,
      types: {},
      templates: {},
      data: {},
      ComponentFields: new Set(),
      componentDisplayNames: {},
    });
    useAuthStore.setState({ userData: { id: "user-1" } as never });
    useFlowsManagerStore.setState({ currentFlowId: FLOW_ID });
    useFlowStore.setState({ nodes: [], currentFlow: undefined });
    mockApiGet.mockImplementation((url: string) => {
      if (url.includes("/all?")) {
        // A dialog must not replace the flow palette while an unrelated
        // global palette request is still pending.
        return new Promise(() => {});
      }
      if (url.includes("/oauth/registrations")) {
        return Promise.resolve({ data: { registrations: [] } });
      }
      if (url.includes("/integrations")) {
        return Promise.resolve({
          data: {
            providers: [telegram],
            deployment_context: "self_managed",
          },
        });
      }
      if (url.includes("/connections")) {
        return Promise.resolve({ data: [] });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    mockApiPost.mockResolvedValue({ data: ready });
  });

  afterEach(() => client.clear());

  async function openDialog(user: ReturnType<typeof userEvent.setup>) {
    const onChange = jest.fn();
    render(
      <QueryClientProvider client={client}>
        <Canvas onChange={onChange} />
      </QueryClientProvider>,
    );
    await user.click(await screen.findByRole("combobox"));
    expect(
      await screen.findByText("No telegram connections yet."),
    ).toBeVisible();
    const add = screen.getByRole("button", { name: "Add connection" });
    await waitFor(() => expect(add).toBeEnabled());
    await user.click(add);
    const dialog = await screen.findByRole("dialog", {
      name: "Add connection",
    });
    expect(within(dialog).getByTestId("connection-provider")).toHaveTextContent(
      "Telegram",
    );
    expect(screen.queryByText("Loading canvas...")).not.toBeInTheDocument();
    return { onChange };
  }

  it("keeps an empty Telegram picker usable when creation is canceled", async () => {
    const user = userEvent.setup();
    const { onChange } = await openDialog(user);

    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByRole("region", { name: "Flow canvas" })).toBeVisible();
    expect(screen.getByRole("combobox")).toHaveTextContent(
      "Select a telegram connection",
    );
    expect(onChange).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveFocus());
  });

  it("selects the validated Telegram connection without replacing the canvas", async () => {
    const user = userEvent.setup();
    const { onChange } = await openDialog(user);
    await user.type(screen.getByTestId("connection-name"), "new");
    await user.type(
      screen.getByTestId("connection-token"),
      "example-provider-token",
    );

    await user.click(screen.getByTestId("connection-continue"));
    await user.click(await screen.findByTestId("connection-done"));

    expect(onChange).toHaveBeenCalledWith({ value: "telegram/new" });
    expect(screen.getByRole("combobox")).toHaveTextContent("telegram/new");
    expect(screen.getByRole("region", { name: "Flow canvas" })).toBeVisible();
  });
});
