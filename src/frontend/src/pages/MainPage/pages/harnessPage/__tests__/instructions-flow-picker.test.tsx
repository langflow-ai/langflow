import { fireEvent, render, screen } from "@testing-library/react";
import type { FlowBinding, FlowOutputChoice } from "@/pages/MainPage/entities";
import { InstructionsFlowPicker } from "../components/instructions-flow-picker";

let choices: FlowOutputChoice[];
let isError = false;
let isLoading = false;
const refetch = jest.fn();
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
  Link: ({ to, children }: { to: string; children: React.ReactNode }) => (
    <a href={to}>{children}</a>
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
  expect(screen.getByRole("link")).toHaveAttribute("href", "/flow/source");
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
