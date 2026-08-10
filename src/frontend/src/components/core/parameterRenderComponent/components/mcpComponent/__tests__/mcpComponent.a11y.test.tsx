import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useGetMCPServers } from "@/controllers/API/queries/mcp/use-get-mcp-servers";
import { axe } from "@/utils/a11y-test";
import {
  mockGenericIconComponent,
  mockZustandStore,
} from "../../__tests__/a11y-mock-helpers";
import McpComponent from "../index";

jest.mock("@/controllers/API/queries/mcp/use-get-mcp-servers", () => ({
  useGetMCPServers: jest.fn(() => ({
    data: [{ name: "server-a", mode: "sse", toolsCount: 2, error: null }],
    refetch: jest.fn(),
    isFetching: false,
  })),
}));

jest.mock("@/controllers/API/queries/mcp/use-add-mcp-server", () => ({
  useAddMCPServer: jest.fn(() => ({ mutate: jest.fn() })),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: jest.fn(() => ({ mutateAsync: jest.fn() })),
}));

jest.mock("@/stores/alertStore", () =>
  mockZustandStore({ setErrorData: jest.fn() }),
);

jest.mock("@/stores/flowStore", () =>
  mockZustandStore({ updateBuildStatus: jest.fn() }),
);

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

jest.mock("@/modals/addMcpServerModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock(
  "@/CustomNodes/GenericNode/components/ListSelectionComponent",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

const baseProps = {
  value: { name: "", config: {} },
  id: "mcp-field",
  editNode: false,
  disabled: false,
  nodeId: "node-1",
  handleOnNewValue: jest.fn(),
};

describe("McpComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">MCP server</span>
        <McpComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: label only, not composed with the selected server
  // name. Note this trigger is a plain button with aria-haspopup="dialog"
  // (it opens ListSelectionComponent's dialog), not role="combobox" like
  // connectionComponent/dropdownComponent — querying by the wrong role
  // silently passed before because RTL's error surfaced the real name.
  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">MCP server</span>
        <McpComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "MCP server" }),
    ).toBeInTheDocument();
  });

  it("does not set aria-labelledby on the trigger when absent", () => {
    render(<McpComponent {...baseProps} />);

    expect(screen.getByTestId("mcp-server-dropdown")).not.toHaveAttribute(
      "aria-labelledby",
    );
  });

  it("keeps the destructive clear-server label instead of the field label", () => {
    render(
      <>
        <span id="field-label">MCP server</span>
        <McpComponent
          {...baseProps}
          value={{ name: "not-in-list", config: { some: "config" } }}
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Clear selected server" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "MCP server" }),
    ).not.toBeInTheDocument();
  });


  it("keeps the add-server button's own name instead of the field label", () => {
    jest.mocked(useGetMCPServers).mockReturnValue({
      data: [],
      refetch: jest.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useGetMCPServers>);

    render(
      <>
        <span id="field-label">MCP server</span>
        <McpComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Add MCP Server" }),
    ).toBeInTheDocument();
  });
});
