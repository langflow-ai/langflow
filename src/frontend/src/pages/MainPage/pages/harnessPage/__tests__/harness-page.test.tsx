import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import type { HookBinding, ProjectTypeType } from "@/pages/MainPage/entities";
import type { FlowType } from "@/types/flow";
import { editorDraft } from "../editor-draft";
import HarnessPage from "../harness-page";

const mockPatch = jest.fn();
// The report workbench has its own API/reader integration suite.
jest.mock("../components/harness-reports", () => ({
  HarnessReports: () => null,
}));
const mockSuccess = jest.fn();
const mockError = jest.fn();
let projectTypes: ProjectTypeType[] | undefined;
let isLoading = false;
let projectFlows: FlowType[] | undefined;
let isLoadingFlows = false;
let isFlowsError = false;
const mockRefetchFlows = jest.fn();
let mockPending = false;
let mockRealNumericControls = false;
const instructionsBinding = {
  flow_id: "source",
  node_id: "terminal",
  output_name: "instructions",
  revision: "reviewed",
};
const contextBinding = {
  ...instructionsBinding,
  flow_id: "context-source",
  output_name: "context",
  timeout_seconds: 5,
};
const compactionBinding = {
  ...instructionsBinding,
  flow_id: "compaction-source",
  output_name: "result",
  timeout_seconds: 2.5,
  trigger_tokens: 2400,
};
const permissionBinding = {
  ...instructionsBinding,
  flow_id: "permission-source",
  output_name: "permission",
  timeout_seconds: 2.5,
};
const hookBinding: HookBinding = {
  flow_id: "hook-source",
  node_id: "hook",
  output_name: "decision",
  revision: "reviewed",
  on_event: "before_tool_call",
};
jest.mock("../components/hook-flow-picker", () => ({
  HookFlowPicker: ({
    value,
    onChange,
    onOpen,
  }: {
    value: HookBinding[];
    onChange: (next: HookBinding[]) => void;
    onOpen: () => void;
  }) => (
    <>
      <button
        data-testid="bind-hook"
        onClick={() => onChange([...value, hookBinding])}
      >
        Add hook
      </button>
      <button data-testid="remove-hooks" onClick={() => onChange([])}>
        Remove hooks
      </button>
      <button data-testid="open-hook" onClick={onOpen}>
        Open hook
      </button>
      <button
        data-testid="invalidate-hook"
        onClick={() => onChange([{ ...hookBinding, timeout_seconds: NaN }])}
      >
        Invalid timeout
      </button>
    </>
  ),
}));

jest.mock("../components/instructions-flow-picker", () => ({
  HarnessFlowPicker: ({
    value,
    onChange,
    fieldName,
    onOpen,
    initialConfig,
  }: {
    value?: unknown;
    onChange: (value: unknown) => void;
    fieldName: string;
    onOpen?: () => void;
    initialConfig?: unknown;
  }) => (
    <>
      <button
        type="button"
        data-testid={
          fieldName === "context_strategy"
            ? "bind-context"
            : fieldName === "compaction"
              ? "bind-compaction"
              : fieldName === "tool_policy"
                ? "bind-permission"
                : "bind-instructions"
        }
        data-initial-config={JSON.stringify(initialConfig)}
        onClick={() =>
          onChange(
            value
              ? undefined
              : fieldName === "context_strategy"
                ? contextBinding
                : fieldName === "compaction"
                  ? compactionBinding
                  : fieldName === "tool_policy"
                    ? permissionBinding
                    : instructionsBinding,
          )
        }
      >
        {value ? "Unbind" : "Bind"}
      </button>
      {fieldName === "tool_policy" && (
        <>
          <button data-testid="open-permission" onClick={onOpen}>
            Open permission
          </button>
          <button
            data-testid="invalidate-permission"
            onClick={() =>
              onChange({ ...permissionBinding, timeout_seconds: NaN })
            }
          >
            Invalid permission timeout
          </button>
        </>
      )}
      {fieldName === "context_strategy" && (
        <>
          <button data-testid="open-context" onClick={onOpen}>
            Open context
          </button>
          <button
            data-testid="invalidate-context"
            onClick={() =>
              onChange({ ...contextBinding, timeout_seconds: NaN })
            }
          >
            Invalid context timeout
          </button>
        </>
      )}
      {fieldName === "compaction" && (
        <>
          <button data-testid="open-compaction" onClick={onOpen}>
            Open compaction
          </button>
          <button
            data-testid="invalidate-compaction-threshold"
            onClick={() =>
              onChange({ ...compactionBinding, trigger_tokens: 1.5 })
            }
          >
            Invalid threshold
          </button>
          <button
            data-testid="invalidate-compaction-timeout"
            onClick={() =>
              onChange({ ...compactionBinding, timeout_seconds: NaN })
            }
          >
            Invalid timeout
          </button>
        </>
      )}
    </>
  ),
}));

jest.mock("@/controllers/API/queries/folders/use-get-project-types", () => ({
  useGetProjectTypesQuery: () => ({ data: projectTypes, isLoading }),
}));

jest.mock("@/controllers/API/queries/folders/use-get-project-flows", () => ({
  useGetProjectFlowsQuery: () => ({
    data: projectFlows,
    isLoading: isLoadingFlows,
    isError: isFlowsError,
    refetch: mockRefetchFlows,
  }),
}));

jest.mock("@/controllers/API/queries/folders/use-patch-folders", () => ({
  usePatchFolders: () => ({ mutate: mockPatch, isPending: mockPending }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <div data-testid={`icon-${name}`} />,
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setSuccessData: mockSuccess, setErrorData: mockError }),
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
    disabled,
  }: {
    name: string;
    nodeId: string;
    templateValue: unknown;
    handleOnNewValue: (changes: { value: unknown }) => void;
    disabled: boolean;
  }) => {
    if (mockRealNumericControls && name === "context_turns") {
      const IntComponent = jest.requireActual(
        "@/components/core/parameterRenderComponent/components/intComponent",
      ).default;
      return (
        <IntComponent
          name={name}
          nodeId={nodeId}
          id={`input-${name}`}
          value={templateValue}
          rangeSpec={{ min: 1, max: 10000, step: 1 }}
          disabled={disabled}
          handleOnNewValue={handleOnNewValue}
        />
      );
    }
    return (
      <>
        <input
          data-testid={`input-${name}`}
          value={String(templateValue ?? "")}
          onChange={(event) => handleOnNewValue({ value: event.target.value })}
        />
        <span data-testid={`nodeid-${name}`}>{nodeId}</span>
      </>
    );
  },
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

it("keeps unpublished contract controls out of the form and summary", () => {
  projectTypes = [
    {
      ...HARNESS,
      template: {
        ...HARNESS.template,
        hooks: {
          name: "hooks",
          display_name: "Hooks",
          type: "str",
          section: "Runtime",
          show: false,
          value: [],
          renders: "hook_flows",
        },
      },
    },
  ];
  render(<HarnessPage {...defaultProps} />);
  expect(screen.queryByTestId("harness-field-hooks")).not.toBeInTheDocument();
  expect(screen.queryByText("Hooks")).not.toBeInTheDocument();
});

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

const renderPage = (props: Partial<ComponentProps<typeof HarnessPage>> = {}) =>
  render(<HarnessPage {...defaultProps} {...props} />);

beforeEach(() => {
  mockPending = false;
  mockRealNumericControls = false;
  jest.clearAllMocks();
  // clearAllMocks keeps implementations, and two tests below give this one; reset so they
  // cannot leak into the tests that only read what it was called with.
  mockPatch.mockReset();
  projectTypes = [FLOWS, HARNESS];
  isLoading = false;
  projectFlows = [
    { id: "f1", name: "Search docs", description: "" } as FlowType,
    { id: "f2", name: "Send email", description: "" } as FlowType,
  ];
  isLoadingFlows = false;
  isFlowsError = false;
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

  it("says how many flows the save reached, not just that it saved", () => {
    mockPatch.mockImplementation((_payload, handlers) =>
      handlers.onSuccess({ flows_updated: 2 }),
    );
    renderPage();

    fireEvent.change(screen.getByTestId("input-system_prompt"), {
      target: { value: "Be terse" },
    });
    fireEvent.click(screen.getByTestId("harness-save-btn"));

    expect(mockSuccess).toHaveBeenCalledWith({
      title: "Saved, and applied to 2 flows",
    });
  });

  it("just says saved when the form reached no flow", () => {
    mockPatch.mockImplementation((_payload, handlers) =>
      handlers.onSuccess({ flows_updated: 0 }),
    );
    renderPage();

    fireEvent.change(screen.getByTestId("input-system_prompt"), {
      target: { value: "Be terse" },
    });
    fireEvent.click(screen.getByTestId("harness-save-btn"));

    expect(mockSuccess).toHaveBeenCalledWith({ title: "Project saved" });
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

const agentFlow = (id: string, role = "workflow") =>
  ({
    id,
    name: `Agent ${id}`,
    flow_type: role,
    data: {
      nodes: [{ id: `Agent-${id}`, data: { type: "Agent" } }],
      edges: [],
    },
  }) as unknown as FlowType;

it("saves the unique agent and excludes it from the tools picker", () => {
  projectFlows = [agentFlow("main"), ...projectFlows!];
  renderPage();
  expect(screen.getByTestId("harness-agent-picker")).toHaveTextContent(
    "Agent main",
  );
  expect(screen.getByTestId("flow-picker")).toHaveAttribute("data-flows", "2");
  fireEvent.change(screen.getByTestId("input-system_prompt"), {
    target: { value: "New instructions" },
  });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.calls[0][0].data.project_config.agent_flow_id).toBe(
    "main",
  );
});

it("requires a choice when multiple agent flows are available", () => {
  projectFlows = [agentFlow("one"), agentFlow("two")];
  renderPage();
  fireEvent.change(screen.getByTestId("input-system_prompt"), {
    target: { value: "New instructions" },
  });
  expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
});

it("uses the A2A marked flow as a default but respects a saved choice", () => {
  projectFlows = [agentFlow("marked", "agent"), agentFlow("chosen")];
  const { unmount } = renderPage();
  expect(screen.getByTestId("harness-agent-picker")).toHaveTextContent(
    "Agent marked",
  );
  unmount();
  renderPage({ projectConfig: { agent_flow_id: "chosen" } });
  expect(screen.getByTestId("harness-agent-picker")).toHaveTextContent(
    "Agent chosen",
  );
});

it("requires replacing a saved agent that is no longer available", () => {
  projectFlows = [agentFlow("available")];
  renderPage({ projectConfig: { agent_flow_id: "moved" } });
  fireEvent.change(screen.getByTestId("input-system_prompt"), {
    target: { value: "New instructions" },
  });
  expect(
    screen.getByText(/selected agent is no longer available/i),
  ).toBeVisible();
  expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
});

it("keeps canvas protection and restore results visible after saving", () => {
  mockPatch.mockImplementation((_payload, handlers) =>
    handlers.onSuccess({
      flows_updated: 1,
      fields_skipped: 2,
      flows_locked: 1,
      restore_version_ids: { main: "version" },
    }),
  );
  renderPage();
  fireEvent.change(screen.getByTestId("input-system_prompt"), {
    target: { value: "New instructions" },
  });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  const result = screen.getByTestId("harness-save-result");
  expect(result).toHaveTextContent(/2.*canvas/i);
  expect(result).toHaveTextContent(/locked/i);
  expect(result).toHaveTextContent(/restore point/i);
});

it("shows the server's actionable validation error", () => {
  mockPatch.mockImplementation((_payload, handlers) =>
    handlers.onError({
      response: {
        data: {
          detail:
            "Flow 'Search' needs an exposed input before it can be used as a tool.",
        },
      },
    }),
  );
  renderPage();
  fireEvent.change(screen.getByTestId("input-system_prompt"), {
    target: { value: "New instructions" },
  });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(JSON.stringify(mockError.mock.calls)).toContain(
    "needs an exposed input",
  );
});

it("offers a retry instead of treating a failed flow query as an empty project", () => {
  projectFlows = undefined;
  isFlowsError = true;
  renderPage();
  expect(screen.getByRole("alert")).toHaveTextContent(/could not load/i);
  expect(screen.queryByTestId("harness-save-btn")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(mockRefetchFlows).toHaveBeenCalledTimes(1);
});

it("saves an Instructions binding separately from the preserved form value", () => {
  projectTypes = [
    {
      ...HARNESS,
      template: {
        ...HARNESS.template,
        system_prompt: {
          ...HARNESS.template.system_prompt,
          supports_flow_binding: true,
          renders: "long_text",
        },
      },
    },
  ];
  projectFlows = [agentFlow("main")];
  renderPage({ projectConfig: { system_prompt: "Saved form instructions" } });
  fireEvent.click(screen.getByTestId("bind-instructions"));
  expect(
    screen.queryByTestId("long-text-system_prompt"),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.calls[0][0].data.project_config).toMatchObject({
    system_prompt: "Saved form instructions",
    flow_bindings: { system_prompt: instructionsBinding },
  });
});

it("removes a saved binding and re-enables its preserved form value", () => {
  projectTypes = [
    {
      ...HARNESS,
      template: {
        ...HARNESS.template,
        system_prompt: {
          ...HARNESS.template.system_prompt,
          supports_flow_binding: true,
          renders: "long_text",
        },
      },
    },
  ];
  projectFlows = [agentFlow("main")];
  renderPage({
    projectConfig: {
      system_prompt: "Saved form instructions",
      flow_bindings: { system_prompt: instructionsBinding },
    },
  });
  fireEvent.click(screen.getByTestId("bind-instructions"));
  expect(screen.getByTestId("long-text-system_prompt")).toBeEnabled();
  expect(screen.getByTestId("long-text-system_prompt")).toHaveValue(
    "Saved form instructions",
  );
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.calls[0][0].data.project_config.flow_bindings).toEqual(
    {},
  );
});

it("restores the explicit editor draft and consumes it once", () => {
  editorDraft.keep("project-1", {
    system_prompt: "Unsaved research instructions",
    n_messages: 25,
    flow_bindings: { system_prompt: instructionsBinding },
  });
  projectFlows = [agentFlow("main")];
  const first = renderPage();
  expect(screen.getByTestId("input-n_messages")).toHaveValue("25");
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.calls[0][0].data.project_config).toMatchObject({
    system_prompt: "Unsaved research instructions",
    n_messages: 25,
    flow_bindings: { system_prompt: instructionsBinding },
  });
  first.unmount();
  renderPage({ projectId: "project-2" });
  expect(screen.getByTestId("input-system_prompt")).not.toHaveValue(
    "Unsaved research instructions",
  );
  expect(editorDraft.get("project-1")).toEqual({});
});

const enableHookFields = () => {
  projectTypes = [
    {
      ...HARNESS,
      template: {
        ...HARNESS.template,
        system_prompt: {
          ...HARNESS.template.system_prompt,
          supports_flow_binding: true,
          renders: "long_text",
        },
        hooks: {
          name: "hooks",
          display_name: "Hooks",
          section: "Hooks",
          renders: "hook_flows",
          value: [],
        },
      },
    },
  ];
  projectFlows = [agentFlow("main")];
};

it("edits Hook and Instructions bindings together and summarizes the hook count", () => {
  enableHookFields();
  renderPage({
    projectConfig: { flow_bindings: { system_prompt: instructionsBinding } },
  });
  fireEvent.click(screen.getByTestId("bind-hook"));
  expect(screen.getByText("1 hook")).toBeVisible();
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config.flow_bindings).toEqual({
    system_prompt: instructionsBinding,
    hooks: [hookBinding],
  });
  fireEvent.click(screen.getByTestId("bind-instructions"));
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config.flow_bindings).toEqual({
    hooks: [hookBinding],
  });
  fireEvent.click(screen.getByTestId("bind-instructions"));
  fireEvent.click(screen.getByTestId("remove-hooks"));
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config.flow_bindings).toEqual({
    system_prompt: instructionsBinding,
    hooks: [],
  });
});

it("keeps the Hook editor draft while visiting the source canvas", () => {
  enableHookFields();
  const first = renderPage({
    projectConfig: { flow_bindings: { system_prompt: instructionsBinding } },
  });
  fireEvent.click(screen.getByTestId("bind-hook"));
  fireEvent.change(screen.getByTestId("input-n_messages"), {
    target: { value: "27" },
  });
  fireEvent.click(screen.getByTestId("open-hook"));
  first.unmount();
  renderPage();
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    n_messages: "27",
    flow_bindings: { system_prompt: instructionsBinding, hooks: [hookBinding] },
  });
});

it("blocks a save with an invalid Hook timeout and recovers when it is removed", () => {
  enableHookFields();
  renderPage();
  fireEvent.click(screen.getByTestId("invalidate-hook"));
  expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("remove-hooks"));
  expect(screen.getByTestId("harness-save-btn")).toBeEnabled();
});

const enableContextFields = () => {
  enableHookFields();
  const type = projectTypes![0];
  projectTypes = [
    {
      ...type,
      template: {
        ...type.template,
        context_strategy: {
          name: "context_strategy",
          display_name: "Context preparation",
          section: "Runtime",
          value: "recent_turns",
          option_labels: {
            all: "All loaded messages",
            recent_turns: "Recent complete turns",
          },
          supports_flow_binding: true,
        },
        context_turns: {
          name: "context_turns",
          display_name: "Recent turns",
          section: "Runtime",
          value: 3,
          type: "int",
          show_when: { context_strategy: "recent_turns" },
        },
      },
    },
  ];
  projectFlows!.push({
    id: "context-source",
    name: "Evidence context",
    description: "",
  } as FlowType);
};

const enableCompactionFields = () => {
  enableContextFields();
  const type = projectTypes![0];
  projectTypes = [
    {
      ...type,
      template: {
        ...type.template,
        compaction: {
          name: "compaction",
          display_name: "Compaction",
          section: "Runtime",
          value: "summarize",
          option_labels: { off: "Off", summarize: "Summarize older messages" },
          supports_flow_binding: true,
        },
        compaction_trigger_tokens: {
          name: "compaction_trigger_tokens",
          display_name: "Token threshold",
          section: "Runtime",
          value: 2400,
          type: "int",
          show_when: { compaction: "summarize" },
        },
        compaction_keep_messages: {
          name: "compaction_keep_messages",
          display_name: "Keep recent messages",
          section: "Runtime",
          value: 3,
          type: "int",
          show_when: { compaction: "summarize" },
        },
      },
    },
  ];
  projectFlows!.push({
    id: "compaction-source",
    name: "Evidence compaction",
    description: "",
  } as FlowType);
};

const enablePermissionFields = () => {
  enableCompactionFields();
  const type = projectTypes![0];
  projectTypes = [
    {
      ...type,
      template: {
        ...type.template,
        tool_policy: {
          name: "tool_policy",
          display_name: "Permissions",
          section: "Runtime",
          value: "deny",
          option_labels: {
            tool_defaults: "Use tool settings",
            ask: "Ask before each call",
            deny: "Block all tools",
          },
          supports_flow_binding: true,
        },
      },
    },
  ];
  projectFlows!.push({
    id: "permission-source",
    name: "Review research tools",
    description: "",
  } as FlowType);
};

it("creates Permissions from the current policy and restores that policy when unbound", () => {
  enablePermissionFields();
  renderPage();
  expect(screen.getByTestId("bind-permission")).toHaveAttribute(
    "data-initial-config",
    JSON.stringify({ tool_policy: "deny" }),
  );
  fireEvent.click(screen.getByTestId("bind-permission"));
  expect(
    screen.queryByTestId("harness-choice-tool_policy"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByTestId("harness-summary-detail-tool_policy"),
  ).toHaveTextContent("Review research tools · flow");
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    tool_policy: "deny",
    flow_bindings: { tool_policy: permissionBinding },
  });
  fireEvent.click(screen.getByTestId("bind-permission"));
  expect(screen.getByTestId("harness-choice-tool_policy")).toHaveTextContent(
    "Block all tools",
  );
});

it("retains five bindings and form edits across the permission canvas round trip", () => {
  enablePermissionFields();
  const projectConfig = {
    flow_bindings: {
      system_prompt: instructionsBinding,
      context_strategy: contextBinding,
      compaction: compactionBinding,
      hooks: [hookBinding],
    },
  };
  const first = renderPage({ projectConfig });
  fireEvent.click(screen.getByTestId("bind-permission"));
  fireEvent.change(screen.getByTestId("input-n_messages"), {
    target: { value: "27" },
  });
  fireEvent.click(screen.getByTestId("open-permission"));
  first.unmount();
  renderPage({ projectConfig });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    n_messages: "27",
    flow_bindings: {
      ...projectConfig.flow_bindings,
      tool_policy: permissionBinding,
    },
  });
});

it("blocks a save with invalid permission timeout while retaining other bindings", () => {
  enablePermissionFields();
  renderPage({
    projectConfig: {
      flow_bindings: {
        context_strategy: contextBinding,
        compaction: compactionBinding,
        hooks: [hookBinding],
      },
    },
  });
  fireEvent.click(screen.getByTestId("invalidate-permission"));
  fireEvent.change(screen.getByTestId("input-n_messages"), {
    target: { value: "27" },
  });
  expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
  expect(mockPatch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("bind-permission"));
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(
    mockPatch.mock.lastCall[0].data.project_config.flow_bindings,
  ).toMatchObject({
    context_strategy: contextBinding,
    compaction: compactionBinding,
    hooks: [hookBinding],
  });
});

it("creates Compaction from current settings and restores scalar controls when unbound", () => {
  enableCompactionFields();
  renderPage();
  expect(screen.getByTestId("bind-compaction")).toHaveAttribute(
    "data-initial-config",
    JSON.stringify({
      compaction_trigger_tokens: 2400,
      compaction_keep_messages: 3,
    }),
  );
  fireEvent.click(screen.getByTestId("bind-compaction"));
  expect(
    screen.queryByTestId("input-compaction_trigger_tokens"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByTestId("input-compaction_keep_messages"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByTestId("harness-summary-detail-compaction"),
  ).toHaveTextContent("Evidence compaction · flow");
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    compaction: "summarize",
    compaction_trigger_tokens: 2400,
    compaction_keep_messages: 3,
    flow_bindings: { compaction: compactionBinding },
  });
  fireEvent.click(screen.getByTestId("bind-compaction"));
  expect(screen.getByTestId("input-compaction_keep_messages")).toHaveValue("3");
});

it("keeps all four bindings and other edits through the Compaction canvas round trip", () => {
  enableCompactionFields();
  const projectConfig = {
    flow_bindings: {
      system_prompt: instructionsBinding,
      context_strategy: contextBinding,
      hooks: [hookBinding],
    },
  };
  const first = renderPage({ projectConfig });
  fireEvent.click(screen.getByTestId("bind-compaction"));
  fireEvent.change(screen.getByTestId("input-n_messages"), {
    target: { value: "27" },
  });
  fireEvent.click(screen.getByTestId("open-compaction"));
  first.unmount();
  renderPage({ projectConfig });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    n_messages: "27",
    flow_bindings: {
      ...projectConfig.flow_bindings,
      compaction: compactionBinding,
    },
  });
});

it.each(["threshold", "timeout"])(
  "blocks an invalid Compaction %s without discarding other bindings",
  (setting) => {
    enableCompactionFields();
    renderPage({ projectConfig: { flow_bindings: { hooks: [hookBinding] } } });
    fireEvent.click(screen.getByTestId(`invalidate-compaction-${setting}`));
    fireEvent.change(screen.getByTestId("input-n_messages"), {
      target: { value: "27" },
    });
    expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
    fireEvent.click(screen.getByTestId("bind-compaction"));
    expect(screen.getByTestId("harness-save-btn")).toBeEnabled();
    fireEvent.click(screen.getByTestId("harness-save-btn"));
    expect(
      mockPatch.mock.lastCall[0].data.project_config.flow_bindings,
    ).toEqual({ hooks: [hookBinding] });
  },
);

it("replaces scalar Context controls, retains their values, and names the flow in the summary", () => {
  enableContextFields();
  renderPage();
  expect(screen.getByTestId("bind-context")).toHaveAttribute(
    "data-initial-config",
    JSON.stringify({ context_strategy: "recent_turns", context_turns: 3 }),
  );
  fireEvent.click(screen.getByTestId("bind-context"));
  expect(screen.queryByTestId("input-context_turns")).not.toBeInTheDocument();
  expect(
    screen.getByTestId("harness-summary-detail-context_strategy"),
  ).toHaveTextContent("Evidence context · flow");
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    context_strategy: "recent_turns",
    context_turns: 3,
    flow_bindings: { context_strategy: contextBinding },
  });
  fireEvent.click(screen.getByTestId("bind-context"));
  expect(screen.getByTestId("input-context_turns")).toHaveValue("3");
});

it("keeps all three binding kinds and other edits through the Context canvas round trip", () => {
  enableContextFields();
  const projectConfig = {
    flow_bindings: { system_prompt: instructionsBinding, hooks: [hookBinding] },
  };
  const first = renderPage({ projectConfig });
  fireEvent.click(screen.getByTestId("bind-context"));
  fireEvent.change(screen.getByTestId("input-n_messages"), {
    target: { value: "27" },
  });
  fireEvent.click(screen.getByTestId("open-context"));
  first.unmount();
  renderPage({ projectConfig });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config).toMatchObject({
    n_messages: "27",
    flow_bindings: {
      system_prompt: instructionsBinding,
      hooks: [hookBinding],
      context_strategy: contextBinding,
    },
  });
});

it("blocks an invalid Context timeout without discarding other bindings", () => {
  enableContextFields();
  renderPage({ projectConfig: { flow_bindings: { hooks: [hookBinding] } } });
  fireEvent.click(screen.getByTestId("invalidate-context"));
  fireEvent.change(screen.getByTestId("input-n_messages"), {
    target: { value: "27" },
  });
  expect(screen.getByTestId("harness-save-btn")).toBeDisabled();
  fireEvent.click(screen.getByTestId("bind-context"));
  expect(screen.getByTestId("harness-save-btn")).toBeEnabled();
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.lastCall[0].data.project_config.flow_bindings).toEqual({
    hooks: [hookBinding],
  });
});

it("reveals mode settings and preserves them when a mode is turned off", () => {
  projectTypes = [
    {
      ...HARNESS,
      template: {
        ...HARNESS.template,
        compaction: { name: "compaction", value: "off", section: "Runtime" },
        compaction_trigger_tokens: {
          name: "compaction_trigger_tokens",
          display_name: "Summarize at estimated tokens",
          value: 8000,
          section: "Runtime",
          show_when: { compaction: "summarize" },
        },
      },
    },
  ];
  renderPage();
  expect(
    screen.queryByTestId("input-compaction_trigger_tokens"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("Summarize at estimated tokens"),
  ).not.toBeInTheDocument();
  fireEvent.change(screen.getByTestId("input-compaction"), {
    target: { value: "summarize" },
  });
  fireEvent.change(screen.getByTestId("input-compaction_trigger_tokens"), {
    target: { value: "6000" },
  });
  fireEvent.change(screen.getByTestId("input-compaction"), {
    target: { value: "off" },
  });
  expect(
    screen.queryByTestId("input-compaction_trigger_tokens"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("Summarize at estimated tokens"),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  expect(mockPatch.mock.calls[0][0].data.project_config).toMatchObject({
    compaction: "off",
    compaction_trigger_tokens: "6000",
  });
  fireEvent.change(screen.getByTestId("input-compaction"), {
    target: { value: "summarize" },
  });
  expect(screen.getByTestId("input-compaction_trigger_tokens")).toHaveValue(
    "6000",
  );
});

it.each([
  [
    "context_strategy",
    "Context preparation",
    "recent_turns",
    "Recent complete turns",
  ],
  ["tool_policy", "Tool permissions", "ask", "Ask before each call"],
  ["tool_policy", "Tool permissions", "deny", "Block all tools"],
])(
  "saves %s as %s with readable choice labels",
  (field, label, value, choice) => {
    projectTypes = [
      {
        ...HARNESS,
        template: {
          ...HARNESS.template,
          [field]: {
            name: field,
            display_name: label,
            section: "Runtime",
            value,
            option_labels: {
              [value]: choice,
            },
          },
        },
      },
    ];
    renderPage();
    expect(screen.getByRole("combobox", { name: label })).toHaveTextContent(
      choice,
    );
    expect(screen.queryByText(value)).not.toBeInTheDocument();
    fireEvent.change(screen.getByTestId("input-system_prompt"), {
      target: { value: "Changed instructions" },
    });
    fireEvent.click(screen.getByTestId("harness-save-btn"));
    expect(mockPatch.mock.calls[0][0].data.project_config[field]).toBe(value);
  },
);

it("keeps positive numeric settings intact throughout a pending save", () => {
  mockRealNumericControls = true;
  projectTypes = [
    {
      ...HARNESS,
      template: {
        ...HARNESS.template,
        context_turns: {
          name: "context_turns",
          display_name: "Recent turns",
          type: "int",
          section: "Runtime",
          value: 6,
        },
      },
    },
  ];
  const view = renderPage();
  fireEvent.change(screen.getByTestId("input-system_prompt"), {
    target: { value: "Changed instructions" },
  });
  fireEvent.click(screen.getByTestId("harness-save-btn"));
  mockPending = true;
  view.rerender(<HarnessPage {...defaultProps} />);
  expect(screen.getByTestId("input-context_turns")).toHaveValue("6");
  expect(screen.getByTestId("input-context_turns")).toBeDisabled();
  mockPending = false;
  view.rerender(<HarnessPage {...defaultProps} />);
  expect(screen.getByTestId("input-context_turns")).toHaveValue("6");
  expect(screen.getByTestId("input-context_turns")).toBeEnabled();
});
