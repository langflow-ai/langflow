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

it("requires an explicit choice when the created flow has several outputs", async () => {
  createFlow.mockResolvedValue({ id: "created" });
  refetch.mockResolvedValue({
    data: [
      { ...choices[0], flow_id: "created" },
      { ...choices[0], flow_id: "created", node_id: "another" },
    ],
  });
  const onChange = setup({ value: binding });
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  expect(await screen.findByText(/Flow created/i)).toBeVisible();
  expect(onChange).not.toHaveBeenCalled();
});

it("cannot change the draft after leaving a pending creation", async () => {
  let finish: (value: { id: string }) => void;
  createFlow.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  refetch.mockResolvedValue({ data: [{ ...choices[0], flow_id: "created" }] });
  const onChange = jest.fn();
  const { unmount } = render(
    <InstructionsFlowPicker
      projectId="project"
      fieldName="system_prompt"
      agentId="agent"
      disabled={false}
      value={binding}
      onChange={onChange}
    />,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /Create Instructions Flow/i }),
  );
  unmount();
  await act(async () => {
    finish!({ id: "created" });
  });
  expect(onChange).not.toHaveBeenCalled();
  expect(refetch).not.toHaveBeenCalled();
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
