import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { axe } from "@/utils/a11y-test";
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

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector?: (state: unknown) => unknown) =>
    selector ? selector({ setErrorData: jest.fn() }) : {},
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: (state: unknown) => unknown) =>
    selector ? selector({ updateBuildStatus: jest.fn() }) : {},
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

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
  // name — role="combobox" gets special handling from screen readers, same
  // reasoning as connectionComponent.
  it("uses the field's real label as the combobox trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">MCP server</span>
        <McpComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("combobox", { name: "MCP server" }),
    ).toBeInTheDocument();
  });

  it("does not set aria-labelledby on the combobox trigger when absent", () => {
    render(<McpComponent {...baseProps} />);

    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-labelledby");
  });
});
