import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { I18nextProvider } from "react-i18next";
import type { IntegrationProviderRead } from "@/controllers/API/queries/connections";
import i18n from "@/i18n";
import manifest from "../../../../../../../bundles/github/src/lfx_github/components/github/capabilities.v1.json";
import dialogPayload from "../../../../../../../bundles/github/tests/fixtures/manual-token-dialog.json";
import AddConnectionDialog from "../components/AddConnectionDialog";

jest.unmock("react-i18next");
const mockCreate = jest.fn();
const mockRegistrations = { data: [], isSuccess: true };
const mockTypesState = { data: {} };
jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useCreateConnectionMutation: () => ({
    mutateAsync: mockCreate,
    isPending: false,
  }),
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

const provider = {
  provider_id: manifest.provider_id,
  display_name: manifest.display_name,
  approved: true,
  enabled: false,
  connection_count: 0,
  capabilities: manifest.capabilities.map((capability) => ({
    ...capability,
    allowed: true,
  })),
  manual_token_profiles: [
    {
      id: manifest.auth_profiles[0].id,
      identity: "service",
      required_scopes: [],
      requires_expiry: true,
    },
  ],
} as IntegrationProviderRead;

function renderDialog() {
  return render(
    <I18nextProvider i18n={i18n}>
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[provider]}
        canCreateInstance={false}
        deploymentContext="self_managed"
      />
    </I18nextProvider>,
  );
}

it("offers only the installation token method supported by GitHub", () => {
  renderDialog();
  expect(screen.getByTestId("connection-token")).toBeVisible();
  expect(screen.queryByTestId("connection-method")).not.toBeInTheDocument();
  expect(screen.queryByText(/Sign in with/)).not.toBeInTheDocument();
  expect(
    screen.queryByTestId("connection-callback-url"),
  ).not.toBeInTheDocument();
});

it("submits the GitHub installation payload accepted by the backend validator", async () => {
  mockCreate.mockResolvedValue({ id: "github-connection", ...dialogPayload });
  const user = userEvent.setup();
  renderDialog();
  await user.type(screen.getByTestId("connection-name"), dialogPayload.name);
  await user.type(
    screen.getByTestId("connection-display-name"),
    dialogPayload.display_name,
  );
  await user.type(
    screen.getByTestId("connection-token"),
    dialogPayload.credentials.access_token,
  );
  expect(screen.getByTestId("connection-continue")).toBeDisabled();
  const date = new Date(dialogPayload.credentials.expires_at);
  const pad = (value: number) => String(value).padStart(2, "0");
  const local = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  fireEvent.change(screen.getByLabelText("Token expiration"), {
    target: { value: local },
  });
  await user.click(screen.getByTestId("connection-allow-background-runs"));
  await user.click(screen.getByTestId("connection-continue"));
  expect(mockCreate).toHaveBeenCalledWith(dialogPayload);
});
