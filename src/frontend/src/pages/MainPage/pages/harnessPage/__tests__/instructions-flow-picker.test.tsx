import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { FlowBinding, FlowOutputChoice } from "@/pages/MainPage/entities";
import { InstructionsFlowPicker } from "../components/instructions-flow-picker";

let choices: FlowOutputChoice[];
let isError = false;
let isLoading = false;
const refetch = jest.fn();
const createFlow = jest.fn();
jest.mock(
  "@/controllers/API/queries/folders/use-create-instructions-flow",
  () => ({ useCreateInstructionsFlow: () => createFlow }),
);
jest.mock(
  "@/controllers/API/queries/folders/use-get-project-flow-outputs",
  () => ({
    useGetProjectFlowOutputsQuery: () => ({
      data: choices,
      isError,
      isLoading,
      refetch,
    }),
  }),
);
jest.mock("react-router-dom", () => ({
  Link: ({
    to,
    children,
    onClick,
  }: {
    to: string;
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <a href={to} onClick={onClick}>
      {children}
    </a>
  ),
}));
// Exercise selection semantics with a native control. The real Radix picker is checked in-browser.
jest.mock("@/components/ui/select", () => ({
  Select: ({
    value,
    disabled,
    onValueChange,
    children,
  }: {
    value: string;
    disabled: boolean;
    onValueChange: (value: string) => void;
    children: React.ReactNode;
  }) => (
    <select
      aria-label="Instructions output"
      value={value}
      disabled={disabled}
      onChange={(event) => onValueChange(event.target.value)}
    >
      <option value="">Choose</option>
      {children}
    </select>
  ),
  SelectTrigger: () => null,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  SelectItem: ({
    value,
    disabled,
    children,
  }: {
    value: string;
    disabled?: boolean;
    children: React.ReactNode;
  }) => (
    <option value={value} disabled={disabled}>
      {children}
    </option>
  ),
}));

const binding: FlowBinding = {
  flow_id: "source",
  node_id: "output",
  output_name: "instructions",
  revision: "reviewed",
  version_id: "snapshot",
};
const key = (value: FlowBinding) =>
  JSON.stringify([value.flow_id, value.node_id, value.output_name]);
const setup = (
  props: Partial<React.ComponentProps<typeof InstructionsFlowPicker>> = {},
) => {
  const onChange = jest.fn();
  render(
    <InstructionsFlowPicker
      projectId="project"
      fieldName="system_prompt"
      agentId="agent"
      disabled={false}
      onChange={onChange}
      {...props}
    />,
  );
  return onChange;
};

beforeEach(() => {
  choices = [
    {
      ...binding,
      flow_name: "Research instructions",
      display_name: "Builder · Instructions",
    },
  ];
  isError = false;
  isLoading = false;
  jest.clearAllMocks();
});

it("requires selecting an explicit output and strips presentation metadata", () => {
  choices.push({
    ...choices[0],
    node_id: "second",
    display_name: "Another output",
  });
  const onChange = setup();
  fireEvent.click(screen.getByRole("button", { name: /Use a flow instead/i }));
  expect(onChange).not.toHaveBeenCalled();
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: key(choices[1]) },
  });
  expect(onChange).toHaveBeenCalledWith({
    flow_id: "source",
    node_id: "second",
    output_name: "instructions",
    revision: "reviewed",
  });
});

it("requires an agent and respects pending saves", () => {
  setup({ agentId: undefined });
  expect(
    screen.getByRole("button", { name: /Use a flow instead/i }),
  ).toBeDisabled();
});

it("opens the selected source and allows returning to the form", () => {
  const onChange = setup({ value: binding });
  expect(screen.getByRole("link")).toHaveAttribute(
    "href",
    "/flow/source?harnessField=system_prompt",
  );
  fireEvent.click(screen.getByRole("button", { name: /Use the form value/i }));
  expect(onChange).toHaveBeenCalledWith(undefined);
});

it("makes a changed definition an explicit update", () => {
  choices[0].revision = "changed";
  const onChange = setup({ value: binding });
  expect(onChange).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /Update binding/i }));
  expect(onChange).toHaveBeenCalledWith({
    flow_id: "source",
    node_id: "output",
    output_name: "instructions",
    revision: "changed",
  });
});

it("retains an unavailable binding until the user replaces or removes it", () => {
  choices = [];
  const onChange = setup({ value: binding });
  expect(screen.getByRole("status")).toHaveTextContent(
    /choose another output|form value/i,
  );
  expect(onChange).not.toHaveBeenCalled();
  expect(
    screen.getByRole("button", { name: /Use the form value/i }),
  ).toBeEnabled();
});

it("offers retry for a discovery failure", () => {
  isError = true;
  setup({ value: binding });
  expect(screen.getByRole("alert")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /Retry/i }));
  expect(refetch).toHaveBeenCalledTimes(1);
});

it("disables binding changes while saving", () => {
  choices[0].revision = "changed";
  setup({ value: binding, disabled: true });
  expect(screen.getByRole("combobox")).toBeDisabled();
  expect(
    screen.getByRole("button", { name: /Use the form value/i }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: /Update binding/i }),
  ).toBeDisabled();
});

it("creates from current form text, selects its output, and keeps a path back", async () => {
  createFlow.mockResolvedValue({ id: "created" });
  refetch.mockResolvedValue({ data: [{ ...choices[0], flow_id: "created" }] });
  const onOpen = jest.fn();
  const onChange = setup({
    value: binding,
    initialValue: "Unsaved instructions",
    onOpen,
  });
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  await waitFor(() =>
    expect(onChange).toHaveBeenCalledWith({
      flow_id: "created",
      node_id: "output",
      output_name: "instructions",
      revision: "reviewed",
    }),
  );
  expect(createFlow).toHaveBeenCalledWith(
    "project",
    "system_prompt",
    "Unsaved instructions",
  );
  expect(screen.getByText(/Flow created/i)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("link", { name: "Open the new flow" }));
  expect(onOpen).toHaveBeenCalled();
});

it("keeps the selected binding when creation fails", async () => {
  createFlow.mockRejectedValue(new Error("denied"));
  const onChange = setup({ value: binding });
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /Could not create/,
  );
  expect(onChange).not.toHaveBeenCalled();
});

it("keeps a successful creation accessible when output refresh fails", async () => {
  createFlow.mockResolvedValue({ id: "created" });
  refetch.mockRejectedValue(new Error("offline"));
  const onChange = setup({ value: binding });
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  const link = await screen.findByRole("link", { name: "Open the new flow" });
  expect(link).toHaveAttribute(
    "href",
    "/flow/created?harnessField=system_prompt",
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(onChange).not.toHaveBeenCalled();
});

it("leaves multiple outputs for the user to choose after creation", async () => {
  createFlow.mockResolvedValue({ id: "created" });
  refetch.mockResolvedValue({
    data: [
      { ...choices[0], flow_id: "created" },
      { ...choices[0], flow_id: "created", node_id: "alternative" },
    ],
  });
  const onChange = setup({ value: binding });
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  await screen.findByText(/Flow created/i);
  expect(onChange).not.toHaveBeenCalled();
});

it("ignores a creation that completes after leaving the picker", async () => {
  let complete!: (flow: { id: string }) => void;
  createFlow.mockReturnValue(
    new Promise((resolve) => {
      complete = resolve;
    }),
  );
  const onChange = jest.fn();
  const { unmount } = render(
    <InstructionsFlowPicker
      projectId="project"
      fieldName="system_prompt"
      agentId="agent"
      value={binding}
      disabled={false}
      onChange={onChange}
    />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  unmount();
  await act(async () => {
    complete({ id: "old-request" });
  });
  expect(refetch).not.toHaveBeenCalled();
  expect(onChange).not.toHaveBeenCalled();
});

it("releases creation controls and ignores the old response when the Agent changes", async () => {
  let complete!: (flow: { id: string }) => void;
  createFlow.mockReturnValue(
    new Promise((resolve) => {
      complete = resolve;
    }),
  );
  const onChange = jest.fn();
  const props = {
    projectId: "project",
    fieldName: "system_prompt",
    value: binding,
    disabled: false,
    onChange,
  };
  const { rerender } = render(
    <InstructionsFlowPicker {...props} agentId="agent" />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  rerender(<InstructionsFlowPicker {...props} agentId="different-agent" />);
  expect(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  ).toBeEnabled();
  await act(async () => {
    complete({ id: "old-agent-request" });
  });
  expect(refetch).not.toHaveBeenCalled();
  expect(onChange).not.toHaveBeenCalled();
  expect(screen.queryByText(/Flow created/i)).not.toBeInTheDocument();
});

describe("Context flow selection", () => {
  const context = { ...binding, output_name: "context", timeout_seconds: 5 };
  beforeEach(() => {
    choices = [
      {
        ...context,
        flow_name: "Evidence context",
        display_name: "Prepare Context · Messages",
      },
    ];
  });

  it("uses the context route, keeps timeout on revision updates, and drops the old snapshot", () => {
    choices[0].revision = "changed";
    const onChange = setup({ fieldName: "context_strategy", value: context });
    expect(screen.getByText("Context from a flow")).toBeVisible();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/flow/source?harnessField=context_strategy",
    );
    fireEvent.click(screen.getByRole("button", { name: /Update binding/i }));
    expect(onChange).toHaveBeenCalledWith({
      ...context,
      revision: "changed",
      version_id: undefined,
    });
    expect(onChange.mock.calls[0][0]).not.toHaveProperty("version_id");
  });

  it("creates from the current scalar settings and selects the unambiguous output", async () => {
    createFlow.mockResolvedValue({ id: "created" });
    refetch.mockResolvedValue({
      data: [{ ...choices[0], flow_id: "created" }],
    });
    const initialConfig = {
      context_strategy: "recent_turns",
      context_turns: 3,
    };
    const onChange = setup({ fieldName: "context_strategy", initialConfig });
    fireEvent.click(
      screen.getByRole("button", { name: /Use a flow instead/i }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Create Context Flow/i }),
    );
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(createFlow).toHaveBeenCalledWith(
      "project",
      "context_strategy",
      "",
      initialConfig,
    );
    expect(onChange.mock.calls[0][0]).toMatchObject({
      flow_id: "created",
      timeout_seconds: 30,
    });
  });

  it("keeps an invalid timeout visible until it is corrected", () => {
    const onChange = setup({
      fieldName: "context_strategy",
      value: { ...context, timeout_seconds: NaN },
    });
    const input = screen.getByRole("spinbutton", { name: "Timeout (seconds)" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("greater than 0");
    fireEvent.change(input, { target: { value: "2.5" } });
    expect(onChange).toHaveBeenCalledWith({ ...context, timeout_seconds: 2.5 });
  });

  it("preserves a removed output and explains how to replace it", () => {
    choices = [];
    const onChange = setup({ fieldName: "context_strategy", value: context });
    expect(screen.getByRole("status")).toHaveTextContent(
      /no longer compatible/,
    );
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("button", { name: /Use the form value/i }),
    );
    expect(onChange).toHaveBeenCalledWith(undefined);
  });

  it("disables context changes during a save", () => {
    setup({ fieldName: "context_strategy", value: context, disabled: true });
    expect(screen.getByRole("spinbutton")).toBeDisabled();
    expect(screen.getByRole("combobox")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Use the form value/i }),
    ).toBeDisabled();
  });
});

describe("Permission flow selection", () => {
  const permission = {
    ...binding,
    output_name: "permission",
    timeout_seconds: 2.5,
  };
  beforeEach(() => {
    choices = [
      {
        ...permission,
        flow_name: "Review research tools",
        display_name: "Permission Gate · Permission",
      },
    ];
  });

  it("reviews a new revision while preserving timeout and dropping the old snapshot", () => {
    choices[0].revision = "changed";
    const onChange = setup({ fieldName: "tool_policy", value: permission });
    expect(screen.getByText("Permissions from a flow")).toBeVisible();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/flow/source?harnessField=tool_policy",
    );
    fireEvent.click(screen.getByRole("button", { name: /Update binding/i }));
    expect(onChange.mock.calls[0][0]).toEqual({
      flow_id: "source",
      node_id: "output",
      output_name: "permission",
      revision: "changed",
      timeout_seconds: 2.5,
    });
  });

  it("creates from the current tool policy with the runtime timeout default", async () => {
    createFlow.mockResolvedValue({ id: "created" });
    refetch.mockResolvedValue({
      data: [{ ...choices[0], flow_id: "created" }],
    });
    const initialConfig = { tool_policy: "deny" };
    const onChange = setup({ fieldName: "tool_policy", initialConfig });
    fireEvent.click(
      screen.getByRole("button", { name: /Use a flow instead/i }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Create Permission Flow/i }),
    );
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(createFlow).toHaveBeenCalledWith(
      "project",
      "tool_policy",
      "",
      initialConfig,
    );
    expect(onChange.mock.calls[0][0]).toMatchObject({
      flow_id: "created",
      timeout_seconds: 10,
    });
  });

  it.each([0, -1, 301, NaN, Infinity])(
    "keeps invalid timeout %s visible until corrected",
    (timeout) => {
      const onChange = setup({
        fieldName: "tool_policy",
        value: { ...permission, timeout_seconds: timeout },
      });
      const input = screen.getByRole("spinbutton");
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByRole("alert")).toBeVisible();
      fireEvent.change(input, { target: { value: "1.5" } });
      expect(onChange).toHaveBeenLastCalledWith({
        ...permission,
        timeout_seconds: 1.5,
      });
    },
  );
});

describe("Compaction flow selection", () => {
  const compaction = {
    ...binding,
    output_name: "result",
    timeout_seconds: 2.5,
    trigger_tokens: 1600,
  };
  beforeEach(() => {
    choices = [
      {
        ...compaction,
        flow_name: "Evidence compaction",
        display_name: "Compact Conversation · Compaction",
      },
    ];
  });

  it("keeps threshold and timeout when reviewing a new revision, and drops the previous snapshot", () => {
    choices[0].revision = "changed";
    const onChange = setup({ fieldName: "compaction", value: compaction });
    expect(screen.getByText("Compaction from a flow")).toBeVisible();
    expect(screen.getByRole("link")).toHaveAttribute(
      "href",
      "/flow/source?harnessField=compaction",
    );
    fireEvent.click(screen.getByRole("button", { name: /Update binding/i }));
    expect(onChange.mock.calls[0][0]).toEqual({
      flow_id: "source",
      node_id: "output",
      output_name: "result",
      revision: "changed",
      trigger_tokens: 1600,
      timeout_seconds: 2.5,
    });
  });

  it("creates from the retained-message setting and binds the current threshold", async () => {
    createFlow.mockResolvedValue({ id: "created" });
    refetch.mockResolvedValue({
      data: [{ ...choices[0], flow_id: "created" }],
    });
    const initialConfig = {
      compaction_keep_messages: 3,
      compaction_trigger_tokens: 2400,
    };
    const onChange = setup({ fieldName: "compaction", initialConfig });
    fireEvent.click(
      screen.getByRole("button", { name: /Use a flow instead/i }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /Create Compaction Flow/i }),
    );
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(createFlow).toHaveBeenCalledWith(
      "project",
      "compaction",
      "",
      initialConfig,
    );
    expect(onChange.mock.calls[0][0]).toMatchObject({
      flow_id: "created",
      timeout_seconds: 60,
      trigger_tokens: 2400,
    });
  });

  it.each([0, 1.5, 10_000_001, NaN, Infinity])(
    "keeps invalid threshold %s visible until correction",
    (threshold) => {
      const onChange = setup({
        fieldName: "compaction",
        value: { ...compaction, trigger_tokens: threshold },
      });
      const input = screen.getByRole("spinbutton", {
        name: "Trigger at estimated tokens",
      });
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByRole("alert")).toHaveTextContent(
        "whole-number threshold",
      );
      fireEvent.change(input, { target: { value: "8000" } });
      expect(onChange).toHaveBeenCalledWith({
        ...compaction,
        trigger_tokens: 8000,
      });
    },
  );

  it("uses runtime defaults for an existing binding instead of unrelated scalar settings", () => {
    setup({
      fieldName: "compaction",
      value: binding,
      initialConfig: { compaction_trigger_tokens: 1234 },
    });
    expect(
      screen.getByRole("spinbutton", { name: "Trigger at estimated tokens" }),
    ).toHaveValue(8000);
    expect(
      screen.getByRole("spinbutton", { name: "Timeout (seconds)" }),
    ).toHaveValue(60);
  });

  it("preserves the threshold when fixing a timeout and disables both during saves", () => {
    const onChange = setup({
      fieldName: "compaction",
      value: { ...compaction, timeout_seconds: 0 },
    });
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Timeout (seconds)" }),
      { target: { value: "1.5" } },
    );
    expect(onChange).toHaveBeenCalledWith({
      ...compaction,
      timeout_seconds: 1.5,
    });
  });

  it("disables Compaction changes during a save", () => {
    setup({ fieldName: "compaction", value: compaction, disabled: true });
    screen
      .getAllByRole("spinbutton")
      .forEach((input) => expect(input).toBeDisabled());
    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
