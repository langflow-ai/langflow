import { render } from "@testing-library/react";
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

describe("Dropdown value reset bug", () => {
  /**
   * GIVEN: Dropdown with saved value ("new_flow_2") and empty options
   *        (options haven't loaded from backend yet)
   * WHEN:  Component renders (flow reload)
   * THEN:  Value should NOT be reset — empty options means still loading
   */
  it("should_preserve_value_when_options_are_empty_and_loading", () => {
    const mockOnSelect = jest.fn();

    render(
      <Dropdown
        value="new_flow_2"
        options={[]}
        onSelect={mockOnSelect}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
      />,
    );

    expect(mockOnSelect).not.toHaveBeenCalledWith("", undefined, true);
  });

  it("should_reset_value_when_options_are_loaded_and_value_is_not_in_options", () => {
    const mockOnSelect = jest.fn();

    render(
      <Dropdown
        value="deleted_tool"
        options={["tool_a", "tool_b", "tool_c"]}
        onSelect={mockOnSelect}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
      />,
    );

    expect(mockOnSelect).toHaveBeenCalledWith("", undefined, true);
  });

  it("should_preserve_value_when_options_are_loaded_and_value_is_in_options", () => {
    const mockOnSelect = jest.fn();

    render(
      <Dropdown
        value="tool_b"
        options={["tool_a", "tool_b", "tool_c"]}
        onSelect={mockOnSelect}
        name="tool"
        nodeId="test-node"
        nodeClass={mockNodeClass}
        handleNodeClass={jest.fn()}
        id="test-dropdown"
      />,
    );

    expect(mockOnSelect).not.toHaveBeenCalledWith("", undefined, true);
  });
});
