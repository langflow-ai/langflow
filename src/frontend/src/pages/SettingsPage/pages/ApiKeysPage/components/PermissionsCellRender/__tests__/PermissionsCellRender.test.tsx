import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FormEventHandler, ReactNode } from "react";
import type { IApiKeysDataArray } from "@/controllers/API/queries/api-keys";
import PermissionsCellRender from "../index";

jest.mock("@radix-ui/react-form", () => ({
  Root: ({
    children,
    onSubmit,
  }: {
    children: ReactNode;
    onSubmit?: FormEventHandler<HTMLFormElement>;
  }) => <form onSubmit={onSubmit}>{children}</form>,
  Field: ({ children }: { children: ReactNode }) => <>{children}</>,
  Label: ({ children }: { children: ReactNode }) => <>{children}</>,
  Control: ({ children }: { children: ReactNode }) => <>{children}</>,
  Submit: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const options = {
  supported: true,
  roles: [{ id: "viewer", name: "Viewer", permissions: ["flow:read"] }],
  resource_actions: { flow: ["read"] },
  scope_types: { flow: ["global"] },
};
let mockOptionsQuery = { data: options, isError: false, isFetching: false };
const mockMutate = jest.fn();

jest.mock("@/controllers/API/queries/api-keys", () => ({
  useGetApiKeyPermissionOptions: () => mockOptionsQuery,
  usePatchApiKeyPermissions: () => ({ mutate: mockMutate, isPending: false }),
}));
jest.mock(
  "@/controllers/API/queries/api-keys/use-get-api-key-permission-targets",
  () => ({
    useGetApiKeyPermissionTargets: () => ({
      data: [],
      isLoading: false,
      isError: false,
    }),
  }),
);

const key: IApiKeysDataArray = {
  id: "key-a",
  name: "Runner",
  api_key: "masked", // pragma: allowlist secret
  user_id: "user-a",
  created_at: "2026-10-26T00:00:00Z",
  expires_at: null,
  last_used_at: null,
  total_uses: 0,
  is_active: true,
  permissions: {
    roles: [{ role_id: "viewer", domain_type: "global", domain_id: null }],
    restrictions: [],
  },
};

describe("API key permission editing", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOptionsQuery = { data: options, isError: false, isFetching: false };
  });

  it("shows the stored restriction summary before loading options", () => {
    render(<PermissionsCellRender data={key} />);
    expect(
      screen.getByRole("button", { name: "Edit permissions for Runner" }),
    ).toHaveTextContent(/Restricted access \(1 rule\)/i);
  });

  it("names the allowed resource and actions for a simple restriction", () => {
    render(
      <PermissionsCellRender
        data={{
          ...key,
          permissions: {
            roles: [],
            restrictions: [
              {
                resource_type: "flow",
                actions: ["read", "execute"],
                domain_type: "project",
                domain_id: "project-a",
                resource_ids: null,
              },
            ],
          },
        }}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Edit permissions for Runner" }),
    ).toHaveTextContent(/Flows.*Read.*Run.*Project/i);
  });

  it("changes permissions through PATCH without generating a new key", async () => {
    const user = userEvent.setup();
    render(<PermissionsCellRender data={key} />);
    await user.click(
      screen.getByRole("button", { name: "Edit permissions for Runner" }),
    );
    expect(screen.getByLabelText("Role 1")).toHaveValue("viewer");
    await user.click(screen.getByRole("radio", { name: "Full owner access" }));
    await user.click(
      screen.getByRole("button", { name: /^Save permissions$/i }),
    );
    expect(mockMutate).toHaveBeenCalledWith(
      { id: "key-a", permissions: null },
      expect.any(Object),
    );
  });

  it("preserves policy and blocks saving when metadata refresh fails", async () => {
    const user = userEvent.setup();
    mockOptionsQuery = { data: options, isError: true, isFetching: false };
    render(<PermissionsCellRender data={key} />);
    await user.click(
      screen.getByRole("button", { name: "Edit permissions for Runner" }),
    );
    expect(screen.getByLabelText("Role 1")).toHaveValue("viewer");
    expect(
      screen.getByRole("button", { name: /^Save permissions$/i }),
    ).toBeDisabled();
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("keeps the current selection visible after a server denial", async () => {
    const user = userEvent.setup();
    mockMutate.mockImplementation((_payload, callbacks) =>
      callbacks.onError({
        response: { data: { detail: "Role no longer available" } },
      }),
    );
    render(<PermissionsCellRender data={key} />);
    await user.click(
      screen.getByRole("button", { name: "Edit permissions for Runner" }),
    );
    fireEvent.submit(
      screen
        .getByRole("button", { name: /^Save permissions$/i })
        .closest("form")!,
    );
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Role no longer available",
      ),
    );
    expect(screen.getByLabelText("Role 1")).toHaveValue("viewer");
  });
});
