import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import type { APIClassType } from "@/types/api";
import Dropdown from "../index";

interface MockChildrenProps {
  children: ReactNode;
}

interface MockCommandItemProps {
  children: ReactNode;
  onSelect?: () => void;
}

interface MockButtonProps extends Record<string, unknown> {
  children: ReactNode;
}

interface MockStoreSelectorFn<T> {
  (state: T): unknown;
}

jest.mock("@radix-ui/react-popover", () => ({
  PopoverAnchor: ({ children }: MockChildrenProps) => <div>{children}</div>,
}));

jest.mock("fuse.js", () => {
  return jest.fn().mockImplementation(() => ({
    search: jest.fn(() => []),
  }));
});

jest.mock("@/CustomNodes/GenericNode/components/NodeDialogComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: jest.fn(),
}));

jest.mock("@/components/common/loadingTextComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/constants/constants", () => ({
  RECEIVING_INPUT_VALUE: "Receiving input",
  SELECT_AN_OPTION: "Select an option",
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: () => ({ mutateAsync: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({
    data: undefined,
    isLoading: false,
    isFetching: false,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector?: MockStoreSelectorFn<{ setErrorData: jest.Mock }>) =>
    selector ? selector({ setErrorData: jest.fn() }) : {},
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: MockStoreSelectorFn<{ nodes: unknown[] }>) =>
    selector ? selector({ nodes: [] }) : {},
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (
    selector?: MockStoreSelectorFn<{
      currentFlowId: string;
    }>,
  ) => (selector ? selector({ currentFlowId: "flow-one" }) : {}),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (
    selector?: MockStoreSelectorFn<{ types: Record<string, unknown> }>,
  ) => (selector ? selector({ types: {} }) : {}),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapedJSONStringfy: jest.fn((v: unknown) => JSON.stringify(v)),
}));

jest.mock("@/utils/stringManipulation", () => ({
  convertStringToHTML: jest.fn((v: string) => v),
  getStatusColor: jest.fn(() => ""),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
  filterNullOptions: (opts: (string | null)[]) =>
    opts?.filter((o): o is string => o != null) ?? [],
  formatName: (name: string) => ({ firstWord: name }),
  groupByFamily: jest.fn(() => ({})),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: MockChildrenProps) => <div>{children}</div>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: MockButtonProps) => (
    <button {...props}>{children}</button>
  ),
}));

jest.mock("@/components/ui/command", () => ({
  Command: ({ children }: MockChildrenProps) => <div>{children}</div>,
  CommandGroup: ({ children }: MockChildrenProps) => <div>{children}</div>,
  CommandItem: ({ children, onSelect }: MockCommandItemProps) => (
    <div onClick={onSelect}>{children}</div>
  ),
  CommandList: ({ children }: MockChildrenProps) => <div>{children}</div>,
  CommandSeparator: () => <hr />,
}));

jest.mock("@/components/ui/popover", () => ({
  Popover: ({ children }: MockChildrenProps) => <div>{children}</div>,
  PopoverContent: ({ children }: MockChildrenProps) => <div>{children}</div>,
  PopoverContentWithoutPortal: ({ children }: MockChildrenProps) => (
    <div>{children}</div>
  ),
  PopoverTrigger: ({ children }: MockChildrenProps) => <div>{children}</div>,
}));

const mockNodeClass: APIClassType = {
  template: {},
  display_name: "Test",
  documentation: "",
  description: "",
};

const baseProps = {
  onSelect: jest.fn(),
  name: "model",
  nodeId: "test-node",
  nodeClass: mockNodeClass,
  handleNodeClass: jest.fn(),
  id: "model-dropdown",
  editNode: false,
  handleOnNewValue: jest.fn(),
  disabled: false,
};

describe("Dropdown accessible name", () => {
  // The name is deliberately label-only, not composed with the selected
  // value: role="combobox" gets special handling from screen readers —
  // VoiceOver reads the computed name, then separately re-announces the
  // trigger's own visible text as the combobox's current value (same as
  // native <select> — label, then selected option, as distinct parts). An
  // earlier version of this fix composed the value into aria-labelledby
  // too, which caused it to be announced twice.
  it("should_use_the_forwarded_field_label_as_the_accessible_name_independent_of_the_selected_value", () => {
    render(
      <>
        <span id="model-label">Model</span>
        <Dropdown
          {...baseProps}
          value="gpt-4"
          options={["gpt-4", "gpt-3.5"]}
          ariaLabelledBy="model-label"
        />
      </>,
    );

    const trigger = screen.getByRole("combobox", { name: "Model" });
    // The selected value is still visible content on the trigger — just
    // not folded into the accessible name.
    expect(trigger).toHaveTextContent("gpt-4");
  });

  it("should_use_the_forwarded_field_label_as_the_accessible_name_when_nothing_is_selected", () => {
    render(
      <>
        <span id="model-label">Model</span>
        <Dropdown
          {...baseProps}
          value=""
          options={["gpt-4", "gpt-3.5"]}
          ariaLabelledBy="model-label"
        />
      </>,
    );

    expect(screen.getByRole("combobox", { name: "Model" })).toBeInTheDocument();
  });

  it("should_render_with_no_aria_labelledby_when_no_field_label_is_forwarded", () => {
    render(
      <Dropdown {...baseProps} value="gpt-4" options={["gpt-4", "gpt-3.5"]} />,
    );

    // With no field label, the button falls back to the browser's own
    // name-from-content computation over its visible children — we don't
    // assert the exact resulting string here, just that we didn't force an
    // aria-labelledby that would override it.
    expect(screen.getByTestId("model-dropdown")).not.toHaveAttribute(
      "aria-labelledby",
    );
  });
});
