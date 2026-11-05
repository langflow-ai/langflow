import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import type {
  ConnectionRead,
  IntegrationIdentity,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import i18n from "@/i18n";
import AddConnectionDialog from "../components/AddConnectionDialog";

jest.unmock("react-i18next");
const mockCreate = jest.fn();
const mockRenew = jest.fn();
const mockStartOAuth = jest.fn();
const mockRemove = jest.fn();
const mockTypesState = { data: {} };
const mockRegistrations = { data: [], isSuccess: true };
jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useCreateConnectionMutation: () => ({ mutateAsync: mockCreate }),
  useRenewConnectionTokenMutation: () => ({ mutateAsync: mockRenew }),
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

const profiles: [string, IntegrationIdentity, string[]][] = [
  ["gitlab", "user_delegated", ["api"]],
  ["whatsapp", "service", ["whatsapp_business_messaging"]],
  ["discord", "bot", []],
  ["telegram", "bot", []],
];
const providers: IntegrationProviderRead[] = profiles.map(
  ([id, identity, scopes]) => ({
    provider_id: id,
    display_name: id,
    docs_url: `https://docs.example.com/${id}/setup`,
    approved: true,
    enabled: true,
    connection_count: 0,
    capabilities: [
      {
        id: `${id}.read`,
        display_name: "Read",
        policy_keys: [],
        risk: "read",
        maturity: "preview",
        substrate: "rest",
        identity,
        auth_profile_id: `${id}-token`,
        deployment_contexts: ["self_managed"],
        allowed: true,
      },
    ],
    manual_token_profiles: [
      {
        id: `${id}-token`,
        identity,
        required_scopes: scopes,
        requires_expiry: false,
      },
    ],
  }),
);

function existingConnection(
  provider: IntegrationProviderRead,
  consent: boolean,
): ConnectionRead {
  return {
    id: `${provider.provider_id}-existing`,
    provider_key: provider.provider_id,
    name: "work",
    display_name: "Work",
    owner_id: "owner",
    ownership_mode: "user",
    status: "revoked",
    health: "unknown",
    executing_identity: {
      identity: provider.capabilities[0].identity,
    },
    granted_scopes: [],
    allow_non_interactive: consent,
    has_credentials: false,
    health_checked_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function renderDialog(
  provider: IntegrationProviderRead,
  reauthorize?: ConnectionRead,
) {
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

beforeEach(() => jest.clearAllMocks());

describe.each(providers)("$provider_id manual connections", (provider) => {
  it("shows setup documentation during creation", () => {
    renderDialog(provider);
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      provider.docs_url,
    );
    expect(screen.queryByText(/No OAuth registration/)).not.toBeInTheDocument();
  });

  it.each([true, false])(
    "renews the existing connection and preserves background consent %s",
    async (consent) => {
      const connection = existingConnection(provider, consent);
      mockRenew.mockResolvedValue({ ...connection, status: "ready" });
      const user = userEvent.setup();
      renderDialog(provider, connection);
      expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
        "href",
        provider.docs_url,
      );
      expect(
        screen.queryByLabelText("Token expiration"),
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId("connection-name")).not.toBeInTheDocument();
      expect(
        screen.getByTestId("connection-allow-background-runs"),
      ).toHaveAttribute("data-state", consent ? "checked" : "unchecked");
      await user.type(
        screen.getByTestId("connection-token"),
        "replacement-provider-token",
      );
      await user.click(screen.getByTestId("connection-continue"));
      expect(mockRenew).toHaveBeenCalledWith({
        id: connection.id,
        payload: {
          credentials: { access_token: "replacement-provider-token" },
          allow_non_interactive: consent,
        },
      });
      expect(await screen.findByTestId("connection-done")).toBeVisible();
      expect(mockCreate).not.toHaveBeenCalled();
      expect(mockStartOAuth).not.toHaveBeenCalled();
    },
  );

  it("keeps the existing connection when replacement is canceled", async () => {
    const user = userEvent.setup();
    renderDialog(provider, existingConnection(provider, true));
    await user.type(
      screen.getByTestId("connection-token"),
      "unsaved-provider-token",
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mockRemove).not.toHaveBeenCalled();
    expect(mockRenew).not.toHaveBeenCalled();
    expect(mockCreate).not.toHaveBeenCalled();
    expect(mockStartOAuth).not.toHaveBeenCalled();
  });
});
