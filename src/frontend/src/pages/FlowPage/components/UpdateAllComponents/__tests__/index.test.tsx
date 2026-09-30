import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import UpdateAllComponents from "../index";

const mockAddDismissedNodes = jest.fn();
const mockRemoveDismissedNodes = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetNoticeData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockTakeSnapshot = jest.fn();
const mockUpdateAllNodes = jest.fn();
const mockValidateComponentCode = jest.fn();
const mockProcessNodeAdvancedFields = jest.fn();

let flowStoreState: Record<string, unknown>;
let mockTemplates: Record<
  string,
  { template: { code?: { value: string } }; outputs?: unknown[] }
>;

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  motion: {
    div: ({
      children,
      variants: _variants,
      initial: _initial,
      animate: _animate,
      exit: _exit,
      transition: _transition,
      ...props
    }: HTMLAttributes<HTMLDivElement> & {
      variants?: unknown;
      initial?: unknown;
      animate?: unknown;
      exit?: unknown;
      transition?: unknown;
    }) => <div {...props}>{children}</div>,
  },
}));

jest.mock("@/CustomNodes/helpers/process-node-advanced-fields", () => ({
  processNodeAdvancedFields: (...args: unknown[]) =>
    mockProcessNodeAdvancedFields(...args),
}));

jest.mock("@/CustomNodes/hooks/use-update-all-nodes", () => ({
  __esModule: true,
  default: () => mockUpdateAllNodes,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    loading,
    ...props
  }: ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean }) => (
    <button onClick={onClick} data-loading={loading} {...props}>
      {children}
    </button>
  ),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({
      mutateAsync: mockValidateComponentCode,
    }),
  }),
);

jest.mock("@/modals/updateComponentModal", () => () => null);

jest.mock("@/stores/alertStore", () => {
  type AlertState = {
    setErrorData: typeof mockSetErrorData;
    setNoticeData: jest.Mock;
    setSuccessData: typeof mockSetSuccessData;
  };
  const useAlertStore = <T,>(selector: (state: AlertState) => T): T =>
    selector({
      setErrorData: mockSetErrorData,
      setNoticeData: mockSetNoticeData,
      setSuccessData: mockSetSuccessData,
    });
  useAlertStore.getState = () => ({
    setErrorData: mockSetErrorData,
    setNoticeData: mockSetNoticeData,
    setSuccessData: mockSetSuccessData,
  });

  return {
    __esModule: true,
    default: useAlertStore,
  };
});

jest.mock("@/stores/flowStore", () => {
  const useFlowStore = <T,>(
    selector?: (state: Record<string, unknown>) => T,
  ) => (selector ? selector(flowStoreState) : flowStoreState);
  useFlowStore.getState = () => flowStoreState;

  return {
    __esModule: true,
    default: useFlowStore,
    registerNodeUpdate: jest.fn(),
    completeNodeUpdate: jest.fn(),
  };
});

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: <T,>(
    selector: (state: { takeSnapshot: typeof mockTakeSnapshot }) => T,
  ): T =>
    selector({
      takeSnapshot: mockTakeSnapshot,
    }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: <T,>(
    selector: (state: { templates: typeof mockTemplates }) => T,
  ): T =>
    selector({
      templates: mockTemplates,
    }),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: <T,>(
    selector: (state: { allowCustomComponents: boolean }) => T,
  ): T =>
    selector({
      allowCustomComponents: false,
    }),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: unknown[]) => classes.filter(Boolean).join(" "),
}));

const mockSetNodes = jest.fn();

function configureUpdatableNodes(ids: string[]) {
  mockTemplates = {
    Prompt: {
      template: {
        code: { value: "server_code" },
      },
      outputs: [],
    },
  };
  mockProcessNodeAdvancedFields.mockImplementation((_data, _edges, nodeId) => ({
    nodeId,
  }));
  flowStoreState = {
    ...flowStoreState,
    componentsToUpdate: ids.map((id) => ({
      id,
      display_name: "Prompt",
      icon: "FileText",
      outdated: true,
      blocked: false,
      breakingChange: false,
      userEdited: false,
    })),
    nodes: ids.map((id) => ({
      id,
      type: "genericNode",
      data: {
        id,
        type: "Prompt",
        node: {
          edited: false,
          display_name: "Prompt",
          template: { code: { value: "old_code" } },
          outputs: [],
        },
      },
    })),
    dismissedNodes: [...ids],
  };
}

describe("UpdateAllComponents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockTemplates = {};

    flowStoreState = {
      componentsToUpdate: [
        {
          id: "node-1",
          display_name: "Unknown Custom",
          icon: "box",
          outdated: false,
          blocked: true,
          breakingChange: false,
          userEdited: false,
        },
      ],
      nodes: [
        {
          id: "node-1",
          data: {
            type: "UnknownCustom",
            node: {
              edited: false,
              display_name: "Unknown Custom",
              template: { code: { value: "custom_code" } },
            },
          },
        },
      ],
      edges: [],
      setNodes: mockSetNodes,
      dismissedNodes: [],
      addDismissedNodes: mockAddDismissedNodes,
      removeDismissedNodes: mockRemoveDismissedNodes,
      isBuilding: false,
      buildInfo: null,
    };
  });

  it("dismiss marks nodes as edited via setNodes", async () => {
    const user = userEvent.setup();

    render(<UpdateAllComponents />);

    await user.click(screen.getByRole("button", { name: /dismiss/i }));

    expect(mockAddDismissedNodes).toHaveBeenCalledWith(["node-1"]);
    expect(mockSetNodes).toHaveBeenCalled();
  });

  it("clears dismissed nodes after a successful bulk update", async () => {
    const user = userEvent.setup();

    mockTemplates = {
      Prompt: {
        template: {
          code: { value: "server_code" },
        },
        outputs: [],
      },
    };

    mockValidateComponentCode.mockResolvedValue({
      data: {
        display_name: "Prompt",
        description: "Prompt component",
        template: {
          code: { value: "server_code" },
        },
        outputs: [],
      },
      type: "Prompt",
    });

    mockProcessNodeAdvancedFields.mockReturnValue({
      display_name: "Prompt",
      description: "Prompt component",
      template: {
        code: { value: "server_code" },
      },
      outputs: [],
    });

    flowStoreState = {
      componentsToUpdate: [
        {
          id: "node-1",
          display_name: "Prompt",
          icon: "FileText",
          outdated: true,
          blocked: false,
          breakingChange: false,
          userEdited: true,
        },
      ],
      nodes: [
        {
          id: "node-1",
          type: "genericNode",
          data: {
            id: "node-1",
            type: "Prompt",
            node: {
              edited: true,
              display_name: "Prompt",
              template: { code: { value: "old_code" } },
              outputs: [],
            },
          },
        },
      ],
      edges: [],
      setNodes: mockSetNodes,
      dismissedNodes: ["node-1"],
      addDismissedNodes: mockAddDismissedNodes,
      removeDismissedNodes: mockRemoveDismissedNodes,
      isBuilding: false,
      buildInfo: null,
    };

    render(<UpdateAllComponents />);

    await user.click(screen.getByTestId("update-all-button"));

    await waitFor(() => {
      expect(mockUpdateAllNodes).toHaveBeenCalledTimes(1);
      expect(mockRemoveDismissedNodes).toHaveBeenCalledWith(["node-1"]);
    });
  });

  it("keeps the update button loading until every validation settles", async () => {
    const user = userEvent.setup();
    configureUpdatableNodes(["node-1"]);

    let resolveValidation!: (value: {
      data: Record<string, unknown>;
      type: string;
    }) => void;
    mockValidateComponentCode.mockReturnValue(
      new Promise((resolve) => {
        resolveValidation = resolve;
      }),
    );

    render(<UpdateAllComponents />);

    await user.click(screen.getByTestId("update-all-button"));
    expect(screen.getByTestId("update-all-button")).toHaveAttribute(
      "data-loading",
      "true",
    );

    resolveValidation({ data: { display_name: "Prompt" }, type: "Prompt" });

    await waitFor(() =>
      expect(screen.getByTestId("update-all-button")).toHaveAttribute(
        "data-loading",
        "false",
      ),
    );
    expect(mockUpdateAllNodes).toHaveBeenCalledTimes(1);
  });

  it("applies successful updates but keeps failed nodes eligible", async () => {
    const user = userEvent.setup();
    configureUpdatableNodes(["node-1", "node-2"]);
    flowStoreState.edges = [{ id: "edge-1" }];
    mockValidateComponentCode
      .mockResolvedValueOnce({
        data: { display_name: "Prompt" },
        type: "Prompt",
      })
      .mockRejectedValueOnce(new Error("validation failed"));

    const { rerender } = render(<UpdateAllComponents />);

    await user.click(screen.getByTestId("update-all-button"));

    await waitFor(() => expect(mockSetErrorData).toHaveBeenCalledTimes(1));
    expect(mockUpdateAllNodes).toHaveBeenCalledWith([
      expect.objectContaining({ nodeId: "node-1" }),
    ]);
    expect(mockRemoveDismissedNodes).toHaveBeenCalledWith(["node-1"]);
    expect(mockRemoveDismissedNodes).not.toHaveBeenCalledWith(
      expect.arrayContaining(["node-2"]),
    );
    expect(mockSetSuccessData).not.toHaveBeenCalled();
    expect(screen.getByTestId("update-all-button")).toHaveAttribute(
      "data-loading",
      "false",
    );

    flowStoreState.edges = [{ id: "edge-1" }, { id: "unrelated-edge" }];
    rerender(<UpdateAllComponents />);
    expect(mockSetNoticeData).not.toHaveBeenCalled();
  });

  it("reports an error when applying validated updates fails", async () => {
    const user = userEvent.setup();
    configureUpdatableNodes(["node-1"]);
    mockValidateComponentCode.mockResolvedValue({
      data: { display_name: "Prompt" },
      type: "Prompt",
    });
    mockUpdateAllNodes.mockImplementationOnce(() => {
      throw new Error("apply failed");
    });

    render(<UpdateAllComponents />);

    await user.click(screen.getByTestId("update-all-button"));

    await waitFor(() => expect(mockSetErrorData).toHaveBeenCalledTimes(1));
    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Error updating components",
      list: [
        "There was an error updating the components.",
        "If the error persists, please report it on our Discord or GitHub.",
      ],
    });
    expect(screen.getByTestId("update-all-button")).toHaveAttribute(
      "data-loading",
      "false",
    );
  });
});
