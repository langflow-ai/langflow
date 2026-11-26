import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { useState } from "react";
import type { FlowOutputChoice, HookBinding } from "@/pages/MainPage/entities";
import { HookFlowPicker } from "../components/hook-flow-picker";
import { outputKey } from "../flow-binding";

let choices: FlowOutputChoice[];
let isError = false;
let isLoading = false;
const refetch = jest.fn();
const createFlow = jest.fn();
jest.mock(
  "@/controllers/API/queries/folders/use-create-instructions-flow",
  () => ({ useCreateProjectFlow: () => createFlow }),
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
// Native selection isolates editor behavior. Radix interactions are verified in the browser.
jest.mock("../components/project-choice-field", () => ({
  ProjectChoiceField: ({
    label,
    options,
    value,
    disabled,
    onChange,
  }: {
    label: string;
    options: Record<string, string>;
    value: string;
    disabled: boolean;
    onChange: (value: string) => void;
  }) => (
    <select
      aria-label={label}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
    >
      <option value="">Choose</option>
      {Object.entries(options).map(([key, text]) => (
        <option key={key} value={key}>
          {text}
        </option>
      ))}
    </select>
  ),
}));

const binding: HookBinding = {
  flow_id: "source",
  node_id: "hook",
  output_name: "decision",
  revision: "reviewed",
  version_id: "snapshot",
  on_event: "before_tool_call",
};
const choose = (label: string, value: string) =>
  fireEvent.change(screen.getByRole("combobox", { name: label }), {
    target: { value },
  });
function setup(
  props: Partial<React.ComponentProps<typeof HookFlowPicker>> = {},
) {
  const onChange = jest.fn();
  function Editor() {
    const [value, setValue] = useState(props.value ?? []);
    return (
      <HookFlowPicker
        projectId="project"
        fieldName="hooks"
        agentId="agent"
        disabled={false}
        onOpen={() => {}}
        {...props}
        value={value}
        onChange={(next) => {
          onChange(next);
          setValue(next);
        }}
      />
    );
  }
  return { ...render(<Editor />), onChange };
}
beforeEach(() => {
  choices = [
    {
      ...binding,
      flow_name: "Check tool arguments",
      display_name: "Hook · Decision",
    },
  ];
  isError = false;
  isLoading = false;
  refetch.mockReset();
  createFlow.mockReset();
});

it("adds an explicit output with safe defaults and excludes the agent", () => {
  choices.push({ ...choices[0], flow_id: "agent", flow_name: "Agent" });
  const { onChange } = setup();
  expect(screen.getByRole("button", { name: /Add hook/i })).toBeDisabled();
  expect(
    screen.queryByRole("option", { name: /^Agent/ }),
  ).not.toBeInTheDocument();
  choose("Choose a Hook flow output", outputKey(binding));
  fireEvent.click(screen.getByRole("button", { name: /Add hook/i }));
  expect(onChange).toHaveBeenLastCalledWith([
    {
      flow_id: "source",
      node_id: "hook",
      output_name: "decision",
      revision: "reviewed",
      on_event: "before_tool_call",
      mode: "observe",
      on_failure: "continue",
      timeout_seconds: 10,
      priority: 1,
    },
  ]);
});

it("requires an agent before adding or creating flows", () => {
  setup({ agentId: undefined });
  expect(screen.getByRole("button", { name: /Add hook/i })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Create Hook Flow" }),
  ).toBeDisabled();
});

it("enforces stop on failure for control and observation after model calls", () => {
  const { onChange } = setup({ value: [binding] });
  choose("Hook 1 behavior", "control");
  expect(
    screen.getByRole("combobox", { name: "Hook 1 failure policy" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("combobox", { name: "Hook 1 failure policy" }),
  ).toHaveValue("stop");
  expect(
    screen.getByText(/Approval uses the resulting arguments/),
  ).toBeVisible();
  choose("Hook 1 event", "after_tool_call");
  expect(screen.getByText(/cannot undo its effects/)).toBeVisible();
  choose("Hook 1 event", "before_llm_call");
  expect(screen.getByText(/narrow available tools/)).toBeVisible();
  choose("Hook 1 event", "after_llm_call");
  expect(
    screen.getByRole("combobox", { name: "Hook 1 behavior" }),
  ).toBeDisabled();
  expect(onChange).toHaveBeenLastCalledWith([
    {
      ...binding,
      mode: "observe",
      on_failure: "stop",
      on_event: "after_llm_call",
    },
  ]);
});

it("shows runtime priority order and saves the moved order, retaining each configuration", () => {
  const second = {
    ...binding,
    flow_id: "second",
    priority: -2,
    timeout_seconds: 3,
  };
  choices.push({ ...choices[0], flow_id: "second", flow_name: "First hook" });
  const { onChange } = setup({ value: [{ ...binding, priority: 8 }, second] });
  expect(
    within(screen.getByTestId("hook-row-0")).getByRole("link"),
  ).toHaveTextContent("First hook");
  fireEvent.click(screen.getByRole("button", { name: "Move hook 1 down" }));
  expect(onChange).toHaveBeenLastCalledWith([
    { ...binding, priority: 0 },
    { ...second, priority: 0 },
  ]);
  fireEvent.click(screen.getByRole("button", { name: "Remove hook 2" }));
  expect(onChange).toHaveBeenLastCalledWith([{ ...binding, priority: 0 }]);
});

it("requires an explicit revision update without losing the hook policy", () => {
  choices[0].revision = "new";
  const original: HookBinding = {
    ...binding,
    mode: "control",
    on_failure: "stop",
    priority: -5,
    timeout_seconds: 4,
  };
  const { onChange } = setup({ value: [original] });
  expect(onChange).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: /Update binding/i }));
  expect(onChange).toHaveBeenLastCalledWith([
    { ...original, revision: "new", version_id: undefined },
  ]);
});

it("retains missing outputs and opens the source with its return context", () => {
  choices = [];
  const onOpen = jest.fn();
  const { onChange } = setup({ value: [binding], onOpen });
  expect(screen.getByRole("status")).toHaveTextContent(
    "This output is unavailable",
  );
  const link = screen.getByRole("link");
  expect(link).toHaveAttribute("href", "/flow/source?harnessField=hooks");
  fireEvent.click(link);
  expect(onOpen).toHaveBeenCalledTimes(1);
  expect(onChange).not.toHaveBeenCalled();
});

it("reports blank and out-of-range timeouts without silently substituting defaults", () => {
  const { onChange } = setup({ value: [binding] });
  const input = screen.getByRole("spinbutton", { name: "Hook 1 timeout" });
  for (const value of ["", "0", "301"]) {
    fireEvent.change(input, { target: { value } });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("greater than 0");
  }
  fireEvent.change(input, { target: { value: "0.01" } });
  expect(input).toHaveAttribute("aria-invalid", "false");
  expect(onChange).toHaveBeenLastCalledWith([
    { ...binding, timeout_seconds: 0.01 },
  ]);
});

it("shows discovery loading and offers retry after failure", () => {
  isLoading = true;
  const { rerender } = setup();
  expect(screen.getByRole("status")).toHaveTextContent(/Loading/);
  isLoading = false;
  isError = true;
  rerender(
    <HookFlowPicker
      projectId="project"
      fieldName="hooks"
      value={[]}
      disabled={false}
      onChange={() => {}}
      onOpen={() => {}}
    />,
  );
  expect(screen.getByRole("alert")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /Retry/ }));
  expect(refetch).toHaveBeenCalledTimes(1);
});

it("freezes all editing during a save", () => {
  choices[0].revision = "new";
  setup({ value: [binding, binding], disabled: true });
  for (const control of [
    ...screen.getAllByRole("button"),
    ...screen.getAllByRole("combobox"),
    ...screen.getAllByRole("spinbutton"),
  ])
    expect(control).toBeDisabled();
});

it("creates the baseline, appends its unambiguous output and offers the canvas", async () => {
  createFlow.mockResolvedValue({ id: "created" });
  refetch.mockResolvedValue({ data: [{ ...choices[0], flow_id: "created" }] });
  const { onChange } = setup({ value: [binding] });
  fireEvent.click(screen.getByRole("button", { name: "Create Hook Flow" }));
  await waitFor(() => expect(onChange).toHaveBeenCalled());
  expect(createFlow).toHaveBeenCalledWith("project", "hooks");
  expect(onChange.mock.lastCall[0][0]).toEqual(binding);
  expect(onChange.mock.lastCall[0][1]).toMatchObject({
    flow_id: "created",
    on_event: "before_tool_call",
  });
  expect(screen.getByRole("link", { name: "Open Hook flow" })).toHaveAttribute(
    "href",
    "/flow/created?harnessField=hooks",
  );
});

it.each(["refresh failure", "ambiguous outputs"])(
  "keeps successful creation visible after %s",
  async (scenario) => {
    createFlow.mockResolvedValue({ id: "created" });
    if (scenario === "refresh failure")
      refetch.mockRejectedValue(new Error("offline"));
    else
      refetch.mockResolvedValue({
        data: [1, 2].map((id) => ({
          ...choices[0],
          flow_id: "created",
          node_id: String(id),
        })),
      });
    const { onChange } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Create Hook Flow" }));
    await screen.findByRole("link", { name: "Open Hook flow" });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  },
);

it("retains bindings when creation fails and allows retry", async () => {
  createFlow.mockRejectedValue(new Error("offline"));
  const { onChange } = setup({ value: [binding] });
  fireEvent.click(screen.getByRole("button", { name: "Create Hook Flow" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not create",
  );
  expect(
    screen.getByRole("button", { name: "Create Hook Flow" }),
  ).toBeEnabled();
  expect(onChange).not.toHaveBeenCalled();
});

it("does not apply a pending creation after leaving the editor", async () => {
  let resolveCreate: (value: unknown) => void;
  createFlow.mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveCreate = resolve;
      }),
  );
  const { unmount, onChange } = setup();
  fireEvent.click(screen.getByRole("button", { name: "Create Hook Flow" }));
  expect(
    screen.getByRole("button", { name: /Creating Hook Flow/ }),
  ).toHaveAttribute("aria-disabled", "true");
  unmount();
  await act(async () => {
    resolveCreate!({ id: "created" });
  });
  expect(refetch).not.toHaveBeenCalled();
  expect(onChange).not.toHaveBeenCalled();
});
