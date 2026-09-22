import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type {
  ConnectionRead,
  IntegrationProviderRead,
} from "@/controllers/API/queries/connections";
import AddConnectionDialog from "../components/AddConnectionDialog";

const mockCreate = jest.fn();
// Stable references, as React Query and Zustand hand back in the app. The
// dialog memoizes on these and resets its selected scopes whenever they change,
// so a fresh array or object per render would loop forever.
const mockRegistrations = {
  data: [
    {
      id: "google-demo",
      provider: "google",
      profile: "user",
      context: "self_managed",
      client_type: "confidential",
      scopes: [],
      allowed_tenants: [],
    },
  ],
  isSuccess: true,
};
const mockTypesState = { data: {} };
const mockPoll = { data: undefined };

jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useCreateConnectionMutation: () => ({
    mutateAsync: mockCreate,
    isPending: false,
  }),
  useStartOAuthMutation: () => ({
    mutateAsync: jest
      .fn()
      .mockResolvedValue({ authorization_url: "https://idp.test/consent" }),
  }),
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
  resolveRegistrationId: () => "google-demo",
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const google: IntegrationProviderRead = {
  provider_id: "google",
  display_name: "Google",
  approved: true,
  enabled: true,
  connection_count: 0,
  capabilities: [],
};

const createdRow = (ownership: "user" | "instance"): ConnectionRead => ({
  id: "conn-1",
  owner_id: ownership === "user" ? "user-admin" : null,
  ownership_mode: ownership,
  provider_key: "google",
  name: "team_calendar",
  display_name: "Team calendar",
  status: "pending",
  status_reason: null,
  health: "unknown",
  granted_scopes: [],
  executing_identity: { identity: "user_delegated" },
  allow_non_interactive: false,
  has_credentials: false,
  health_checked_at: null,
  created_at: "2026-09-18T00:00:00Z",
  updated_at: "2026-09-18T00:00:00Z",
});

const fillDetails = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.type(screen.getByTestId("connection-name"), "team_calendar");
  await user.type(
    screen.getByTestId("connection-display-name"),
    "Team calendar",
  );
};

describe("AddConnectionDialog ownership", () => {
  beforeEach(() => {
    mockCreate.mockReset();
    // Consent opens in a popup the dialog creates on the click itself.
    jest.spyOn(window, "open").mockReturnValue({
      close: jest.fn(),
      closed: false,
    } as unknown as Window);
  });

  afterEach(() => jest.restoreAllMocks());

  it.each([
    "gmail-qa",
    "g-1",
    "my-gmail-connection",
    "a_b-c",
    "gmail_",
    "a__b",
    "_gmail",
    "Gmail",
    "gmail qa",
    "a".repeat(65),
  ])("blocks invalid handle %s before creating a connection", async (name) => {
    render(
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[google]}
        canCreateInstance={false}
      />,
    );
    fireEvent.change(screen.getByTestId("connection-name"), {
      target: { value: name },
    });
    fireEvent.change(screen.getByTestId("connection-display-name"), {
      target: { value: "Gmail" },
    });
    expect(screen.getByTestId("connection-name")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByTestId("connection-name")).toHaveAccessibleDescription(
      /lowercase letters and numbers/,
    );
    expect(screen.getByTestId("connection-continue")).toBeDisabled();
    await userEvent.click(screen.getByTestId("connection-continue"));
    expect(mockCreate).not.toHaveBeenCalled();
    expect(window.open).not.toHaveBeenCalled();
  });

  it.each(["gmail_qa", "g1", "a".repeat(64)])(
    "accepts valid handle %s",
    (name) => {
      render(
        <AddConnectionDialog
          open
          onOpenChange={jest.fn()}
          providers={[google]}
          canCreateInstance={false}
        />,
      );
      fireEvent.change(screen.getByTestId("connection-name"), {
        target: { value: name },
      });
      fireEvent.change(screen.getByTestId("connection-display-name"), {
        target: { value: "Gmail" },
      });
      expect(screen.getByTestId("connection-continue")).toBeEnabled();
    },
  );

  it("renders a server validation error as text and keeps the dialog usable", async () => {
    mockCreate.mockRejectedValueOnce({
      isAxiosError: true,
      response: {
        data: {
          detail: [
            {
              type: "string_pattern_mismatch",
              loc: ["body", "name"],
              msg: "Invalid connection handle",
              input: "gmail-qa",
            },
          ],
        },
      },
    });
    const user = userEvent.setup();
    render(
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[google]}
        canCreateInstance={false}
      />,
    );
    await fillDetails(user);
    await user.click(screen.getByTestId("connection-continue"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid connection handle",
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByTestId("connection-continue")).toBeEnabled();
    expect(window.open).toHaveReturnedWith(
      expect.objectContaining({ close: expect.any(Function) }),
    );
    const popup = (window.open as jest.Mock).mock.results[0].value;
    expect(popup.close).toHaveBeenCalled();
  });

  it("creates an instance-owned connection when a superuser ticks the share box", async () => {
    mockCreate.mockResolvedValue(createdRow("instance"));
    const user = userEvent.setup();
    render(
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[google]}
        canCreateInstance
      />,
    );

    await fillDetails(user);
    await user.click(screen.getByTestId("connection-instance-owned"));
    await user.click(screen.getByTestId("connection-continue"));

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        provider_key: "google",
        name: "team_calendar",
        ownership_mode: "instance",
      }),
    );
  });

  it("creates a user-owned connection when the share box is left unticked", async () => {
    mockCreate.mockResolvedValue(createdRow("user"));
    const user = userEvent.setup();
    render(
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[google]}
        canCreateInstance
      />,
    );

    await fillDetails(user);
    expect(screen.getByTestId("connection-instance-owned")).not.toBeChecked();
    await user.click(screen.getByTestId("connection-continue"));

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ ownership_mode: "user" }),
    );
  });

  it("offers a non-superuser no share box and always creates user-owned", async () => {
    mockCreate.mockResolvedValue(createdRow("user"));
    const user = userEvent.setup();
    render(
      <AddConnectionDialog
        open
        onOpenChange={jest.fn()}
        providers={[google]}
        canCreateInstance={false}
      />,
    );

    expect(
      screen.queryByTestId("connection-instance-owned"),
    ).not.toBeInTheDocument();
    await fillDetails(user);
    await user.click(screen.getByTestId("connection-continue"));

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ ownership_mode: "user" }),
    );
  });
});
