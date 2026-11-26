import { fireEvent, render, screen } from "@testing-library/react";
import type { FlowType } from "@/types/flow";
import { ProjectFlowPicker } from "../components/project-flow-picker";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options ? `${key}:${JSON.stringify(options)}` : key,
  }),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: (string | boolean | undefined)[]) =>
    classes.filter(Boolean).join(" "),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <button type="button" onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/skeleton", () => ({
  Skeleton: (props: Record<string, unknown>) => <div {...props} />,
}));

jest.mock("@/components/ui/switch", () => ({
  Switch: ({
    checked,
    onCheckedChange,
    ...props
  }: {
    checked: boolean;
    onCheckedChange: () => void;
    [key: string]: unknown;
  }) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={() => onCheckedChange()}
      {...props}
    />
  ),
}));

const flow = (id: string, name: string, description = ""): FlowType =>
  ({ id, name, description }) as FlowType;

const FLOWS = [
  flow("f1", "Search docs", "Looks things up"),
  flow("f2", "Send email"),
  flow("f3", "Summarise"),
];

const setup = (
  props: Partial<Parameters<typeof ProjectFlowPicker>[0]> = {},
) => {
  const onChange = jest.fn();
  render(
    <ProjectFlowPicker
      flows={FLOWS}
      isLoading={false}
      value={[]}
      onChange={onChange}
      {...props}
    />,
  );
  return { onChange };
};

describe("ProjectFlowPicker", () => {
  it("lists every flow in the project", () => {
    setup();

    expect(screen.getByTestId("flow-picker-row-f1")).toBeInTheDocument();
    expect(screen.getByTestId("flow-picker-row-f2")).toBeInTheDocument();
    expect(screen.getByTestId("flow-picker-row-f3")).toBeInTheDocument();
  });

  it("shows which flows are already picked", () => {
    setup({ value: ["f2"] });

    expect(screen.getByTestId("flow-picker-switch-f2")).toBeChecked();
    expect(screen.getByTestId("flow-picker-switch-f1")).not.toBeChecked();
  });

  it("picks a flow", () => {
    const { onChange } = setup();

    fireEvent.click(screen.getByTestId("flow-picker-switch-f2"));

    expect(onChange).toHaveBeenCalledWith(["f2"]);
  });

  it("unpicks a flow without disturbing the others", () => {
    const { onChange } = setup({ value: ["f1", "f2"] });

    fireEvent.click(screen.getByTestId("flow-picker-switch-f1"));

    expect(onChange).toHaveBeenCalledWith(["f2"]);
  });

  it("keeps the project's own order rather than the order they were clicked", () => {
    const { onChange } = setup({ value: ["f3"] });

    fireEvent.click(screen.getByTestId("flow-picker-switch-f1"));

    expect(onChange).toHaveBeenCalledWith(["f1", "f3"]);
  });

  it("picks everything at once", () => {
    const { onChange } = setup({ value: ["f2"] });

    fireEvent.click(screen.getByTestId("flow-picker-toggle-all"));

    expect(onChange).toHaveBeenCalledWith(["f1", "f2", "f3"]);
  });

  it("clears everything when all of them are already picked", () => {
    const { onChange } = setup({ value: ["f1", "f2", "f3"] });

    fireEvent.click(screen.getByTestId("flow-picker-toggle-all"));

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("says the project has no flows rather than showing an empty list", () => {
    setup({ flows: [] });

    expect(screen.getByTestId("flow-picker-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("flow-picker")).not.toBeInTheDocument();
  });

  it("does not claim the project is empty while the flows are still loading", () => {
    setup({ flows: [], isLoading: true });

    expect(screen.getByTestId("flow-picker-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("flow-picker-empty")).not.toBeInTheDocument();
  });

  it("falls back to a placeholder for a flow with no description", () => {
    setup();

    // Two of the three fixtures have none.
    expect(screen.getAllByText("harness.toolNoDescription")).toHaveLength(2);
    expect(screen.getByText("Looks things up")).toBeInTheDocument();
  });
});

it("selects filtered results while preserving selections outside the search", () => {
  const { onChange } = setup({
    flows: [
      ...FLOWS,
      flow("f4", "Read logs"),
      flow("f5", "Read tickets"),
      flow("f6", "Read reports"),
    ],
    value: ["f2"],
  });
  fireEvent.change(
    screen.getByRole("textbox", { name: "harness.searchTools" }),
    { target: { value: "Read" } },
  );
  expect(screen.queryByTestId("flow-picker-row-f1")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("flow-picker-toggle-all"));
  expect(onChange).toHaveBeenCalledWith(["f2", "f4", "f5", "f6"]);
});

it("keeps unavailable selections until they are explicitly removed", () => {
  const { onChange } = setup({ value: ["f1", "moved"] });
  fireEvent.click(screen.getByTestId("flow-picker-switch-f2"));
  expect(onChange).toHaveBeenLastCalledWith(["f1", "f2", "moved"]);
  fireEvent.click(
    screen.getByRole("button", { name: "harness.removeUnavailable" }),
  );
  expect(onChange).toHaveBeenLastCalledWith(["f1"]);
});

it("disables changes while a save is pending", () => {
  setup({ disabled: true });
  expect(screen.getByTestId("flow-picker-switch-f1")).toBeDisabled();
  expect(screen.getByTestId("flow-picker-toggle-all")).toBeDisabled();
});
