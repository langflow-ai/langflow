import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { IntegrationProviderRead } from "@/controllers/API/queries/connections";
import "@/i18n";
import ManageProvidersPanel from "../components/ManageProvidersPanel";

jest.unmock("react-i18next");

let mockSaved: Record<string, unknown>[] = [];
let mockActive: Record<string, unknown>[] = [];
let mockSavedState: Record<string, unknown> = {};
let mockActiveState: Record<string, unknown> = {};
const mockSave = jest.fn();
const mockDelete = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@/controllers/API/queries/connections", () => ({
  ...jest.requireActual("@/controllers/API/queries/connections"),
  useSavedOAuthRegistrationsQuery: () => ({
    data: mockSaved,
    ...mockSavedState,
  }),
  useOAuthRegistrationsQuery: () => ({ data: mockActive, ...mockActiveState }),
  useSaveOAuthRegistrationMutation: () => ({ mutateAsync: mockSave }),
  useDeleteSavedOAuthRegistrationMutation: () => ({
    mutateAsync: mockDelete,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

const google: IntegrationProviderRead = {
  provider_id: "google",
  display_name: "Google Workspace",
  approved: true,
  enabled: false,
  connection_count: 0,
  capabilities: [
    {
      id: "google.drive.list",
      display_name: "List files",
      policy_keys: [],
      risk: "read",
      required_scopes: ["https://www.googleapis.com/auth/drive.readonly"],
      maturity: "preview",
      substrate: "api",
      identity: "user_delegated",
      auth_profile_id: "user",
      deployment_contexts: ["self_managed"],
      allowed: true,
    },
  ],
};

const servicenow: IntegrationProviderRead = {
  ...google,
  provider_id: "servicenow",
  display_name: "ServiceNow",
  capabilities: [
    {
      ...google.capabilities[0],
      id: "servicenow.table.read",
      required_scopes: ["langflow_table_read"],
    },
  ],
};

function renderPanel(providers: IntegrationProviderRead[]) {
  return render(
    <TooltipProvider>
      <ManageProvidersPanel providers={providers} />
    </TooltipProvider>,
  );
}

const active = (id: string) => ({
  id,
  provider: "google",
  profile: "user",
  context: "self_managed",
  client_type: "confidential",
  scopes: [],
  allowed_tenants: [],
});

describe("ManageProvidersPanel", () => {
  beforeEach(() => {
    mockSaved = [];
    mockActive = [];
    mockSavedState = {};
    mockActiveState = {};
    mockSave.mockReset().mockResolvedValue(undefined);
    mockDelete.mockReset().mockResolvedValue(undefined);
    mockSetErrorData.mockReset();
    mockSetSuccessData.mockReset();
  });

  it("saves a new registration in the server's registration shape", async () => {
    const user = userEvent.setup();
    renderPanel([google]);

    await user.click(screen.getByTestId("manage-providers-add"));
    await user.type(screen.getByLabelText("Client ID"), "client-1");
    await user.type(screen.getByLabelText("Client secret"), "s3cret");
    await user.click(screen.getByTestId("manage-providers-save"));

    await waitFor(() => expect(mockSave).toHaveBeenCalledTimes(1));
    const { id, registration } = mockSave.mock.calls[0][0];
    expect(id).toBe("google-work");
    expect(registration).toMatchObject({
      provider: "google",
      profile: "user",
      owner: "customer",
      context: "self_managed",
      client_type: "confidential",
      client_id: "client-1",
      client_secret: "s3cret",
      scopes: ["https://www.googleapis.com/auth/drive.readonly"],
    });
    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "Provider saved. Restart Langflow to finish applying it.",
    });
  });

  it("opens the form in a dialog and closes it on cancel", async () => {
    const user = userEvent.setup();
    renderPanel([google]);

    await user.click(screen.getByTestId("manage-providers-add"));
    expect(screen.getByRole("dialog")).toHaveTextContent("Add provider");
    expect(
      screen.getByTestId("manage-providers-restart-note"),
    ).toHaveTextContent("Some features need a restart");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("names a new registration after the selected provider without reusing an ID", async () => {
    mockSaved = [
      {
        id: "google-work",
        registration: { provider: "google" },
        has_secret: true,
        saved_by: "other-admin",
        status: "active",
      },
    ];
    const user = userEvent.setup();
    renderPanel([google, servicenow]);

    await user.click(screen.getByTestId("manage-providers-add"));
    expect(screen.getByLabelText("Registration ID")).toHaveValue(
      "google-work-2",
    );
    await user.selectOptions(screen.getByLabelText("Provider"), "servicenow");
    expect(screen.getByLabelText("Registration ID")).toHaveValue(
      "servicenow-work",
    );

    await user.clear(screen.getByLabelText("Registration ID"));
    await user.type(screen.getByLabelText("Registration ID"), "google-work");
    await user.selectOptions(screen.getByLabelText("Provider"), "google");
    expect(screen.getByLabelText("Registration ID")).toHaveValue("google-work");
    await user.type(screen.getByLabelText("Client ID"), "client-1");
    await user.type(screen.getByLabelText("Client secret"), "s3cret");
    await user.click(screen.getByTestId("manage-providers-save"));

    expect(mockSave).not.toHaveBeenCalled();
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title:
        "The registration ID google-work is already in use. Choose another ID.",
    });
  });

  it("requires the instance URL as ServiceNow's tenant", async () => {
    const user = userEvent.setup();
    renderPanel([servicenow]);

    await user.click(screen.getByTestId("manage-providers-add"));
    expect(screen.getByLabelText("Tenant")).toHaveAttribute(
      "placeholder",
      "https://<instance>.service-now.com",
    );
    // Every provider's callback is the broker's, so it is filled in.
    expect(screen.getByLabelText("Redirect URI")).toHaveValue(
      "http://localhost/api/v1/connections/oauth/servicenow/callback",
    );
    await user.type(screen.getByLabelText("Client ID"), "client-1");
    await user.type(screen.getByLabelText("Client secret"), "s3cret");
    await user.click(screen.getByTestId("manage-providers-save"));

    expect(mockSave).not.toHaveBeenCalled();
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title:
        "ServiceNow needs a tenant, for example https://<instance>.service-now.com.",
    });

    await user.type(
      screen.getByLabelText("Tenant"),
      "https://dev1.service-now.com/",
    );
    await user.click(screen.getByTestId("manage-providers-save"));

    await waitFor(() => expect(mockSave).toHaveBeenCalledTimes(1));
    expect(mockSave.mock.calls[0][0].registration).toMatchObject({
      tenant: "https://dev1.service-now.com",
      allowed_tenants: ["https://dev1.service-now.com"],
      scopes: ["langflow_table_read"],
    });
  });

  it("names the failed save and shows the server's reason", async () => {
    mockSave.mockRejectedValue({
      isAxiosError: true,
      response: { status: 422, data: { detail: "Bad registration." } },
    });
    const user = userEvent.setup();
    renderPanel([google]);

    await user.click(screen.getByTestId("manage-providers-add"));
    await user.type(screen.getByLabelText("Client ID"), "client-1");
    await user.type(screen.getByLabelText("Client secret"), "s3cret");
    await user.click(screen.getByTestId("manage-providers-save"));

    await waitFor(() =>
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Could not save the provider",
        list: ["Bad registration."],
      }),
    );
  });

  it("refuses a new confidential client without a secret", async () => {
    const user = userEvent.setup();
    renderPanel([google]);

    await user.click(screen.getByTestId("manage-providers-add"));
    await user.type(screen.getByLabelText("Client ID"), "client-1");
    await user.click(screen.getByTestId("manage-providers-save"));

    expect(mockSave).not.toHaveBeenCalled();
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "A confidential client needs a client secret.",
    });
  });

  it("lists another admin's registration and replaces it without retyping the secret", async () => {
    mockSaved = [
      {
        id: "google-work",
        registration: {
          provider: "google",
          client_type: "confidential",
          client_id: "client-1",
          redirect_uri:
            "http://localhost/api/v1/connections/oauth/google/callback",
          scopes: ["https://www.googleapis.com/auth/drive.readonly"],
        },
        has_secret: true,
        saved_by: "other-admin",
        status: "active",
      },
      {
        id: "google-new",
        registration: { provider: "google" },
        has_secret: true,
        saved_by: "other-admin",
        status: "pending",
      },
      {
        id: "google-shadowed",
        registration: { provider: "google" },
        has_secret: true,
        saved_by: "other-admin",
        status: "overridden",
      },
      {
        id: "google-old",
        registration: { provider: "google" },
        has_secret: true,
        saved_by: "other-admin",
        status: "removed",
      },
    ];
    mockActive = [
      active("google-work"),
      active("from-env"),
      active("google-shadowed"),
    ];
    const user = userEvent.setup();
    renderPanel([google]);

    // The server's status, not mere presence in the running list.
    const status = (id: string) =>
      screen.getByText(id).closest("tr")?.querySelectorAll("td")[2];
    expect(status("google-work")).toHaveTextContent("Active");
    expect(status("google-new")).toHaveTextContent(
      "Saved. Restart Langflow to finish applying it",
    );
    // A removal is listed until the restart, with nothing left to do on it.
    expect(status("google-old")).toHaveTextContent(
      "Removed. Restart Langflow to finish removing it",
    );
    expect(
      screen.getByText("google-old").closest("tr")?.querySelector("button"),
    ).toBeNull();
    expect(status("google-shadowed")).toHaveTextContent(
      "Not in use: the server environment defines this ID",
    );
    expect(status("from-env")).toHaveTextContent("Active");
    expect(screen.getByText("Server environment")).toBeInTheDocument();
    expect(screen.getAllByText("other-admin")).toHaveLength(4);

    // Rows are sorted: from-env and google-old (no actions), google-new, google-shadowed, google-work.
    await user.click(screen.getAllByRole("button", { name: "Replace" })[2]);
    expect(screen.getByRole("dialog")).toHaveTextContent("Replace google-work");
    expect(screen.getByLabelText("Client ID")).toHaveValue("client-1");
    await user.clear(screen.getByLabelText("Client ID"));
    await user.type(screen.getByLabelText("Client ID"), "client-2");
    await user.click(screen.getByTestId("manage-providers-save"));

    await waitFor(() => expect(mockSave).toHaveBeenCalledTimes(1));
    const { id, registration } = mockSave.mock.calls[0][0];
    expect(id).toBe("google-work");
    expect(registration.client_id).toBe("client-2");
    expect(registration).not.toHaveProperty("client_secret");
  });

  it("removes a saved registration by ID", async () => {
    mockSaved = [
      {
        id: "google-work",
        registration: { provider: "google" },
        has_secret: true,
        saved_by: "other-admin",
        status: "active",
      },
    ];
    const user = userEvent.setup();
    renderPanel([google]);

    await user.click(screen.getByRole("button", { name: "Remove" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("google-work"));
    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "Provider removed. Restart Langflow to finish removing it.",
    });
  });

  it("keeps tenant restrictions and other unedited registration fields when replacing", async () => {
    mockSaved = [
      {
        id: "google-work",
        registration: {
          provider: "google",
          profile: "user",
          owner: "customer",
          context: "self_managed",
          client_type: "confidential",
          client_id: "client-1",
          redirect_uri:
            "http://localhost/api/v1/connections/oauth/google/callback",
          scopes: ["openid", "email"],
          allowed_tenants: ["example.com", "other.example.com"],
        },
        has_secret: true,
        saved_by: "other-admin",
        status: "active",
      },
    ];
    const user = userEvent.setup();
    renderPanel([google]);

    await user.click(screen.getByRole("button", { name: "Replace" }));
    await user.clear(screen.getByLabelText("Client ID"));
    await user.type(screen.getByLabelText("Client ID"), "client-2");
    await user.click(screen.getByTestId("manage-providers-save"));

    await waitFor(() => expect(mockSave).toHaveBeenCalledTimes(1));
    expect(mockSave.mock.calls[0][0].registration).toMatchObject({
      client_id: "client-2",
      allowed_tenants: ["example.com", "other.example.com"],
      profile: "user",
      owner: "customer",
      context: "self_managed",
    });
  });

  it.each(["keep", "rotate", "public"])(
    "handles certificate credentials when replacing with %s",
    async (mode) => {
      const tenant = "00000000-0000-0000-0000-000000000000";
      const thumbprint = "a".repeat(64);
      mockSaved = [
        {
          id: "microsoft-work",
          registration: {
            provider: "microsoft",
            profile: "user",
            owner: "customer",
            context: "self_managed",
            client_type: "confidential",
            client_id: "client-1",
            redirect_uri:
              "http://localhost/api/v1/connections/oauth/microsoft/callback",
            tenant,
            allowed_tenants: [tenant],
            scopes: ["User.Read"],
            certificate_thumbprint: thumbprint,
          },
          has_secret: true,
          saved_by: "other-admin",
          status: "active",
        },
      ];
      const user = userEvent.setup();
      renderPanel([
        { ...google, provider_id: "microsoft", display_name: "Microsoft" },
      ]);

      await user.click(screen.getByRole("button", { name: "Replace" }));
      if (mode === "rotate")
        await user.type(screen.getByLabelText("Client secret"), "new-secret");
      if (mode === "public")
        await user.selectOptions(
          screen.getByLabelText("Client type"),
          "public",
        );
      await user.click(screen.getByTestId("manage-providers-save"));

      await waitFor(() => expect(mockSave).toHaveBeenCalledTimes(1));
      const registration = mockSave.mock.calls[0][0].registration;
      if (mode === "keep") {
        expect(registration.certificate_thumbprint).toBe(thumbprint);
        expect(registration).not.toHaveProperty("client_secret");
        expect(registration).not.toHaveProperty("private_key");
      } else {
        expect(registration).toMatchObject({
          client_type: mode === "public" ? "public" : "confidential",
          client_secret: mode === "public" ? null : "new-secret",
          private_key: null,
          certificate_thumbprint: null,
        });
      }
    },
  );

  it.each(["saved", "active"])(
    "disables adding while the %s registration list loads",
    (source) => {
      if (source === "saved") mockSavedState = { isLoading: true };
      else mockActiveState = { isLoading: true };
      renderPanel([google]);

      expect(screen.getByTestId("manage-providers-add")).toBeDisabled();
      expect(screen.getByRole("status")).toHaveTextContent("Loading...");
      expect(
        screen.queryByText("No providers configured yet."),
      ).not.toBeInTheDocument();
    },
  );

  it.each(["saved", "active"])(
    "disables adding when the %s registration list fails",
    (source) => {
      if (source === "saved") mockSavedState = { isError: true };
      else mockActiveState = { isError: true };
      renderPanel([google]);

      expect(screen.getByTestId("manage-providers-add")).toBeDisabled();
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Could not load provider registrations.",
      );
      expect(
        screen.queryByText("No providers configured yet."),
      ).not.toBeInTheDocument();
    },
  );
});
