import { fireEvent, render, screen } from "@testing-library/react";
import type { ProjectTypeType } from "@/pages/MainPage/entities";
import type { FlowType } from "@/types/flow";
import HarnessPage from "../harness-page";

const mockPatch = jest.fn();
let projectTypes: ProjectTypeType[] | undefined;
let isLoading = false;
let projectFlows: FlowType[] | undefined;
let isLoadingFlows = false;

jest.mock("@/controllers/API/queries/folders/use-get-project-types", () => ({
  useGetProjectTypesQuery: () => ({ data: projectTypes, isLoading }),
}));

jest.mock("@/controllers/API/queries/folders/use-get-project-flows", () => ({
  useGetProjectFlowsQuery: () => ({
    data: projectFlows,
    isLoading: isLoadingFlows,
  }),
}));

jest.mock("@/controllers/API/queries/folders/use-patch-folders", () => ({
  usePatchFolders: () => ({ mutate: mockPatch, isPending: false }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <div data-testid={`icon-${name}`} />,
}));

jest.mock("@/customization/components/custom-parameter", () => ({
  getCustomParameterTitle: ({ title }: { title: string }) => (
    <span>{title}</span>
  ),
}));

// The field renderer and the flow picker have their own tests. Here they stand in as plain
// controls so what gets checked is this page's own behaviour: what it renders and what it sends.
jest.mock("@/components/core/parameterRenderComponent", () => ({
  ParameterRenderComponent: ({
    name,
    nodeId,
    templateValue,
    handleOnNewValue,
  }: {
    name: string;
    nodeId: string;
    templateValue: unknown;
    handleOnNewValue: (changes: { value: unknown }) => void;
  }) => (
    <>
      <input
        data-testid={`input-${name}`}
        value={String(templateValue ?? "")}
        onChange={(event) => handleOnNewValue({ value: event.target.value })}
      />
      <span data-testid={`nodeid-${name}`}>{nodeId}</span>
    </>
  ),
}));

jest.mock("../components/project-flow-picker", () => ({
  ProjectFlowPicker: ({
    flows,
    value,
    onChange,
  }: {
    flows: { id: string }[];
    value: string[];
    onChange: (picked: string[]) => void;
  }) => (
    <button
      type="button"
      data-testid="flow-picker"
      data-flows={flows.length}
      data-value={value.join(",")}
      onClick={() => onChange([...value, "f2"])}
    />
  ),
}));

const HARNESS: ProjectTypeType = {
  name: "agent-harness",
  display_name: "Agent Harness",
  icon: "Bot",
  description: "An agent built from the flows in this project.",
  template: {
    system_prompt: {
      name: "system_prompt",
      display_name: "Instructions",
      type: "str",
      multiline: true,
      section: "Instructions",
      value: "You are a helpful assistant",
    },
    model: {
      name: "model",
      display_name: "Model",
      type: "model",
      section: "Model",
      value: "",
    },
    tools: {
      name: "tools",
      display_name: "Tools",
      type: "str",
      list: true,
      section: "Tools",
      renders: "project_flows",
      value: [],
    },
    n_messages: {
      name: "n_messages",
      display_name: "Memory",
      type: "int",
      section: "Runtime",
      value: 100,
    },
  },
};

const FLOWS: ProjectTypeType = {
  name: "flows",
  display_name: "Flows",
  icon: "Folders",
  description: "A plain project.",
  template: {},
};

const defaultProps = {
  projectId: "project-1",
  projectType: "agent-harness",
};

const renderPage = (props: Partial<typeof defaultProps> & object = {}) =>
  render(<HarnessPage {...defaultProps} {...props} />);

beforeEach(() => {
  jest.clearAllMocks();
  projectTypes = [FLOWS, HARNESS];
  isLoading = false;
  projectFlows = [
    { id: "f1", name: "Search docs", description: "" } as FlowType,
    { id: "f2", name: "Send email", description: "" } as FlowType,
  ];
  isLoadingFlows = false;
});

describe("HarnessPage", () => {
  it("renders a field for every field the type declares", () => {
    renderPage();

    expect(
      screen.getByTestId("harness-field-system_prompt"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("harness-field-n_messages")).toBeInTheDocument();
  });

  it("groups the fields into the sections the type declares", () => {
    renderPage();

    expect(screen.getByTestId("harness-section-Instructions")).toBeVisible();
    expect(screen.getByTestId("harness-section-Model")).toBeVisible();
    expect(screen.getByTestId("harness-section-Tools")).toBeVisible();
    expect(screen.getByTestId("harness-section-Runtime")).toBeVisible();
  });

  it("puts the two Runtime fields in one section rather than one each", () => {
    projectTypes = [
      {
        ...HARNESS,
        template: {
          ...HARNESS.template,
          compaction: {
            name: "compaction",
            display_name: "Compaction",
            type: "str",
            section: "Runtime",
            value: "off",
          },
        },
      },
    ];

    renderPage();

    const runtime = screen.getByTestId("harness-section-Runtime");
    expect(runtime).toContainElement(screen.getByTestId("input-n_messages"));
    expect(runtime).toContainElement(screen.getByTestId("input-compaction"));
  });

  it("renders the flow picker for the field that asks for it, not the field renderer", () => {
    renderPage();

    expect(screen.getByTestId("flow-picker")).toBeInTheDocument();
    expect(screen.queryByTestId("input-tools")).not.toBeInTheDocument();
  });

  it("hands the project's flows to the picker", () => {
    renderPage();

    expect(screen.getByTestId("flow-picker")).toHaveAttribute(
      "data-flows",
      "2",
    );
  });

  it("starts from the type's defaults when the project has no config", () => {
    renderPage();

    expect(screen.getByTestId("input-system_prompt")).toHaveValue(
      "You are a helpful assistant",
    );
  });

  it("shows the saved config in preference to the defaults", () => {
    renderPage({ projectConfig: { system_prompt: "Be terse" } } as object);

    expect(screen.getByTestId("input-system_prompt")).toHaveValue("Be terse");
  });

  it("still renders a field the saved config has never heard of", () => {
    renderPage({ projectConfig: { system_prompt: "Be terse" } } as object);

    expect(screen.getByTestId("input-n_messages")).toHaveValue("100");
  });

  it("cannot be saved until something changes", () => {
    renderPage();

    expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
  });

  it("says so when there are unsaved changes", () => {
    renderPage();

    expect(screen.queryByTestId("harness-unsaved")).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId("input-system_prompt"), {
      target: { value: "Be terse" },
    });

    expect(screen.getByTestId("harness-unsaved")).toBeInTheDocument();
  });

  it("saves the whole config, not only the edited field", () => {
    renderPage();

    fireEvent.change(screen.getByTestId("input-system_prompt"), {
      target: { value: "Be terse" },
    });
    fireEvent.click(screen.getByTestId("harness-save-btn"));

    expect(mockPatch).toHaveBeenCalledTimes(1);
    const [payload] = mockPatch.mock.calls[0];
    expect(payload.folderId).toBe("project-1");
    expect(payload.data.project_config).toEqual({
      system_prompt: "Be terse",
      model: "",
      tools: [],
      n_messages: 100,
    });
  });

  it("saves the picked flows as the tools field", () => {
    renderPage();

    fireEvent.click(screen.getByTestId("flow-picker"));
    fireEvent.click(screen.getByTestId("harness-save-btn"));

    expect(mockPatch.mock.calls[0][0].data.project_config.tools).toEqual([
      "f2",
    ]);
  });

  it("sends only the config, so saving the form cannot rename the project", () => {
    renderPage();

    fireEvent.change(screen.getByTestId("input-system_prompt"), {
      target: { value: "Be terse" },
    });
    fireEvent.click(screen.getByTestId("harness-save-btn"));

    expect(Object.keys(mockPatch.mock.calls[0][0].data)).toEqual([
      "project_config",
    ]);
  });

  it("gives the widgets no node id, since no canvas node is behind this form", () => {
    renderPage();

    expect(screen.getByTestId("nodeid-system_prompt")).toHaveTextContent("");
  });

  it("summarises the harness alongside the form", () => {
    renderPage({ projectConfig: { tools: ["f1"] } } as object);

    expect(screen.getByTestId("harness-summary")).toBeInTheDocument();
    expect(screen.getByTestId("harness-summary-tool-f1")).toBeInTheDocument();
  });

  it("keeps long free text out of the summary rows", () => {
    renderPage();

    expect(
      screen.queryByTestId("harness-summary-detail-system_prompt"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("harness-summary-detail-n_messages"),
    ).toHaveTextContent("100");
  });

  it("says so when the type has no form rather than showing an empty page", () => {
    renderPage({ projectType: "flows" });

    expect(
      screen.getByText("This project type has nothing to configure."),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("harness-save-btn")).not.toBeInTheDocument();
  });

  it("says so when the server does not know the project's type", () => {
    renderPage({ projectType: "something-else" });

    expect(screen.queryByTestId("harness-save-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("input-system_prompt")).not.toBeInTheDocument();
  });

  it("does not render a stale empty form while the types are loading", () => {
    projectTypes = undefined;
    isLoading = true;

    renderPage();

    expect(screen.getByTestId("harness-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("harness-save-btn")).not.toBeInTheDocument();
  });
});
