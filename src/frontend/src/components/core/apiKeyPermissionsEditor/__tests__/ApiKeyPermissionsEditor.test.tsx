import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type {
  ApiKeyPermissionOptions,
  ApiKeyPermissionPolicy,
} from "@/types/api-key-permissions";
import ApiKeyPermissionsEditor, {
  isApiKeyPermissionPolicyValid,
} from "../index";

jest.mock(
  "@/controllers/API/queries/api-keys/use-get-api-key-permission-targets",
  () => ({
    useGetApiKeyPermissionTargets: () => ({
      data: [
        { id: "project-a", name: "Project A" },
        { id: "flow-a", name: "Flow A" },
      ],
      isLoading: false,
      isError: false,
    }),
  }),
);

const options: ApiKeyPermissionOptions = {
  supported: true,
  roles: [
    {
      id: "viewer",
      name: "Viewer",
      permissions: ["flow:read", "flow:execute"],
    },
  ],
  resource_actions: { flow: ["read", "execute", "write"] },
  scope_types: { flow: ["global", "workspace", "project"] },
};

function Editor({
  initial = { roles: [], restrictions: [] },
  metadata = options,
}: {
  initial?: ApiKeyPermissionPolicy | null;
  metadata?: ApiKeyPermissionOptions;
}) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <ApiKeyPermissionsEditor
        value={value}
        onChange={setValue}
        options={metadata}
      />
      <output data-testid="policy">{JSON.stringify(value)}</output>
    </>
  );
}

describe("API key permissions editor", () => {
  it("requires an explicit permission selection for restricted access", () => {
    render(<Editor />);
    expect(
      screen.getByRole("radio", { name: "Restricted access" }),
    ).toBeChecked();
    expect(
      isApiKeyPermissionPolicyValid({ roles: [], restrictions: [] }, options),
    ).toBe(false);
  });

  it("starts with two simple permission choices", () => {
    render(<Editor />);

    expect(screen.getByRole("button", { name: /^Use a role$/i })).toBeVisible();
    expect(
      screen.getByRole("button", { name: /^Choose specific access$/i }),
    ).toBeVisible();
    expect(
      screen.queryByText(/Selected roles combine/),
    ).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Role 1")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Resource type for restriction 1"),
    ).not.toBeInTheDocument();
  });

  it("keeps keyboard focus when choosing a role", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(screen.getByRole("button", { name: /^Use a role$/i }));
    const role = screen.getByLabelText("Role 1");
    role.focus();
    await user.selectOptions(role, "viewer");
    expect(screen.getByLabelText("Role 1")).toHaveFocus();
  });

  it("reveals optional limits without changing the selected role", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(screen.getByRole("button", { name: /^Use a role$/i }));
    await user.selectOptions(screen.getByLabelText("Role 1"), "viewer");
    const selected = screen.getByTestId("policy").textContent;

    expect(
      screen.queryByRole("button", { name: /^Choose specific access$/i }),
    ).not.toBeInTheDocument();
    const advanced = screen.getByRole("button", {
      name: /^Further limit access$/i,
    });
    expect(advanced).toHaveAttribute("aria-expanded", "false");
    await user.click(advanced);
    expect(screen.getByText(/Selected roles combine/)).toBeVisible();
    await user.click(advanced);

    expect(screen.getByTestId("policy").textContent).toBe(selected);
    expect(screen.getByLabelText("Role 1")).toHaveValue("viewer");
  });

  it("keeps role combination optional when choosing specific access", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(
      screen.getByRole("button", { name: /^Choose specific access$/i }),
    );

    expect(
      screen.getByLabelText("Resource type for restriction 1"),
    ).toHaveValue("flow");
    expect(screen.queryByLabelText("Role 1")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: /^Combine with a role$/i }),
    );
    await user.click(screen.getByRole("button", { name: /^Use a role$/i }));

    expect(screen.getByLabelText("Role 1")).toBeVisible();
    expect(
      screen.getByLabelText("Resource type for restriction 1"),
    ).toBeVisible();
  });

  it("starts specific access with flows when other resources are listed first", async () => {
    const user = userEvent.setup();
    render(
      <Editor
        metadata={{
          ...options,
          resource_actions: { file: ["read"], ...options.resource_actions },
        }}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /^Choose specific access$/i }),
    );

    expect(
      screen.getByLabelText("Resource type for restriction 1"),
    ).toHaveValue("flow");
  });

  it("shows both parts of an existing combined policy immediately", () => {
    const initial: ApiKeyPermissionPolicy = {
      roles: [
        { role_id: "removed-role", domain_type: "global", domain_id: null },
      ],
      restrictions: [
        {
          resource_type: "flow",
          actions: ["read"],
          domain_type: "global",
          domain_id: null,
          resource_ids: ["removed-flow"],
        },
      ],
    };
    render(<Editor initial={initial} />);

    expect(screen.getByLabelText("Role 1")).toBeVisible();
    expect(screen.getByLabelText("Resources for restriction 1")).toBeVisible();
    expect(screen.getByText(/Unavailable role/)).toBeInTheDocument();
    expect(
      screen.getByText(/Unavailable resource \(removed-flow\)/),
    ).toBeInTheDocument();
    expect(JSON.parse(screen.getByTestId("policy").textContent!)).toEqual(
      initial,
    );
  });

  it("switches a restricted policy to full owner access", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(screen.getByRole("radio", { name: "Full owner access" }));
    expect(screen.getByTestId("policy")).toHaveTextContent("null");
  });

  it("supports changing access mode with the keyboard", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.tab();
    expect(
      screen.getByRole("radio", { name: "Restricted access" }),
    ).toHaveFocus();
    await user.keyboard("{ArrowRight}");
    expect(
      screen.getByRole("radio", { name: "Full owner access" }),
    ).toBeChecked();
  });

  it("adds a role and a resource restriction without replacing either", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(screen.getByRole("button", { name: /^Use a role$/i }));
    await user.selectOptions(screen.getByLabelText("Role 1"), "viewer");
    await user.click(
      screen.getByRole("button", { name: /^Further limit access$/i }),
    );
    await user.click(
      screen.getByRole("button", { name: /^Choose specific access$/i }),
    );
    await user.click(screen.getByRole("checkbox", { name: "Read" }));
    const policy = JSON.parse(screen.getByTestId("policy").textContent!);
    expect(policy.roles).toEqual([
      { role_id: "viewer", domain_type: "global", domain_id: null },
    ]);
    expect(policy.restrictions[0].actions).toEqual(["read"]);
    expect(isApiKeyPermissionPolicyValid(policy, options)).toBe(true);
  });

  it("selects a project by name and requires its scope target", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(
      screen.getByRole("button", { name: /^Choose specific access$/i }),
    );
    await user.selectOptions(
      screen.getByLabelText("Scope for restriction 1"),
      "project",
    );
    await user.selectOptions(
      screen.getByLabelText("Project for restriction 1"),
      "project-a",
    );
    expect(
      JSON.parse(screen.getByTestId("policy").textContent!).restrictions[0],
    ).toMatchObject({ domain_type: "project", domain_id: "project-a" });
  });

  it("preserves an unavailable role until the user explicitly removes it", async () => {
    const user = userEvent.setup();
    render(
      <Editor
        initial={{
          roles: [
            { role_id: "removed-role", domain_type: "global", domain_id: null },
          ],
          restrictions: [],
        }}
      />,
    );
    expect(screen.getByText(/Unavailable role/)).toBeInTheDocument();
    expect(screen.getByTestId("policy")).toHaveTextContent("removed-role");
    await user.click(screen.getByRole("button", { name: /^Remove role 1$/i }));
    expect(JSON.parse(screen.getByTestId("policy").textContent!).roles).toEqual(
      [],
    );
  });

  it("does not treat an empty exact-resource selection as all resources", () => {
    const policy: ApiKeyPermissionPolicy = {
      roles: [],
      restrictions: [
        {
          resource_type: "flow",
          actions: ["read"],
          domain_type: "global",
          domain_id: null,
          resource_ids: [],
        },
      ],
    };
    expect(isApiKeyPermissionPolicyValid(policy, options)).toBe(false);
  });

  it("keeps an explicit resource limit when selecting resources", async () => {
    const user = userEvent.setup();
    render(<Editor />);
    await user.click(
      screen.getByRole("button", { name: /^Choose specific access$/i }),
    );
    await user.click(screen.getByRole("checkbox", { name: "Read" }));
    await user.click(
      screen.getByRole("checkbox", {
        name: /Limit restriction 1 to specific resources/,
      }),
    );
    expect(
      JSON.parse(screen.getByTestId("policy").textContent!).restrictions[0]
        .resource_ids,
    ).toEqual([]);
    await user.selectOptions(
      screen.getByLabelText("Resources for restriction 1"),
      "flow-a",
    );
    expect(
      JSON.parse(screen.getByTestId("policy").textContent!).restrictions[0]
        .resource_ids,
    ).toEqual(["flow-a"]);
  });

  it("preserves unavailable selected resources visibly", () => {
    render(
      <Editor
        initial={{
          roles: [],
          restrictions: [
            {
              resource_type: "flow",
              actions: ["read"],
              domain_type: "global",
              domain_id: null,
              resource_ids: ["removed-flow"],
            },
          ],
        }}
      />,
    );
    expect(
      screen.getByRole("option", {
        name: /Unavailable resource \(removed-flow\)/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Resources for restriction 1")).toHaveValue([
      "removed-flow",
    ]);
  });

  it("preserves and edits a workspace identifier", async () => {
    const user = userEvent.setup();
    render(
      <Editor
        initial={{
          roles: [
            {
              role_id: "viewer",
              domain_type: "workspace",
              domain_id: "workspace-a",
            },
          ],
          restrictions: [],
        }}
      />,
    );
    const workspace = screen.getByLabelText("Workspace ID for role 1");
    expect(workspace).toHaveValue("workspace-a");
    await user.clear(workspace);
    await user.type(workspace, "workspace-b");
    expect(
      JSON.parse(screen.getByTestId("policy").textContent!).roles[0].domain_id,
    ).toBe("workspace-b");
  });
});
