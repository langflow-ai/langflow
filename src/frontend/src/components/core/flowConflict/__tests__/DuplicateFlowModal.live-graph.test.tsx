import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowConflict } from "@/stores/flowConflictStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { AllNodeType } from "@/types/flow";
import { clearLoadRefreshes, recordLoadRefresh } from "@/utils/load-refreshes";
import DuplicateFlowModal from "../DuplicateFlowModal";

const mockForkFlow = jest.fn();
const mockOverwriteFlow = jest.fn();

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => jest.fn(),
}));

jest.mock(
  "@/controllers/API/queries/flow-version/use-post-create-snapshot",
  () => ({
    usePostCreateSnapshot: () => ({
      mutateAsync: jest.fn().mockResolvedValue({}),
      isPending: false,
    }),
  }),
);

jest.mock("@/controllers/API/queries/flows/use-post-fork-flow", () => ({
  usePostForkFlow: () => ({ mutate: mockForkFlow, isPending: false }),
}));

jest.mock("@/controllers/API/queries/flows/use-post-overwrite-flow", () => ({
  usePostOverwriteFlow: () => ({ mutate: mockOverwriteFlow, isPending: false }),
}));

const node = (id: string, displayName: string, value: string): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "Component",
      node: {
        display_name: displayName,
        description: "",
        documentation: "",
        template: {
          text: {
            type: "str",
            required: false,
            list: false,
            show: true,
            readonly: false,
            display_name: "Text",
            value,
          },
        },
      },
    },
  }) as unknown as AllNodeType;

const conflict = (): FlowConflict => ({
  flowId: "flow-1",
  author: { id: "user-2", username: "carlos" },
  isSelf: false,
  modifiedAt: "2026-09-02T10:00:00Z",
  expectedToken: "token-a",
  currentToken: "token-b",
  theirFlow: {
    id: "flow-1",
    name: "probe",
    description: "",
    data: {
      nodes: [
        node("prompt-1", "Prompt Template", "base"),
        node("chat-1", "Chat Input", "theirs"),
      ],
      edges: [],
      viewport: { x: 0, y: 0, zoom: 1 },
    },
  },
});

/** A conflict registered while the dialog is still closed, as a refused save leaves it. */
const seedRefusedSave = () => {
  useFlowsManagerStore.setState({
    currentFlow: {
      id: "flow-1",
      name: "probe",
      description: "",
      data: {
        nodes: [
          node("prompt-1", "Prompt Template", "base"),
          node("chat-1", "Chat Input", "base"),
        ],
        edges: [],
        viewport: { x: 0, y: 0, zoom: 1 },
      },
    },
  });
  useFlowStore.setState({
    nodes: [
      node("prompt-1", "Prompt Template", "base"),
      node("chat-1", "Chat Input", "base"),
    ],
    edges: [],
  });
  useFlowConflictStore.setState({
    conflict: conflict(),
    dialogOpen: false,
    abandonedFlowIds: new Set<string>(),
  });
};

/** What the person types after the refusal, while the banner stands. */
const editAfterRefusal = () =>
  act(() => {
    useFlowStore.setState({
      nodes: [
        node("prompt-1", "Prompt Template", "typed after the refusal"),
        node("chat-1", "Chat Input", "base"),
      ],
    });
  });

const textOf = (data: { nodes: AllNodeType[] }, id: string) =>
  (
    data.nodes.find((candidate) => candidate.id === id)?.data
      .node as unknown as {
      template: { text: { value: string } };
    }
  ).template.text.value;

describe("DuplicateFlowModal after a refused save", () => {
  beforeEach(() => {
    mockForkFlow.mockReset();
    mockOverwriteFlow.mockReset();
    seedRefusedSave();
  });

  it("should_list_an_edit_made_after_the_refusal_when_the_dialog_opens", async () => {
    render(<DuplicateFlowModal />);
    editAfterRefusal();

    act(() => useFlowConflictStore.getState().openDialog());

    expect(
      await screen.findByTestId("conflict-change-mine-node:prompt-1"),
    ).toBeInTheDocument();
  });

  it("should_carry_an_edit_made_after_the_refusal_into_the_duplicate", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    editAfterRefusal();

    act(() => useFlowConflictStore.getState().openDialog());
    await user.click(await screen.findByTestId("confirm-duplicate-flow"));

    expect(mockForkFlow).toHaveBeenCalledTimes(1);
    const [{ data }] = mockForkFlow.mock.calls[0];
    expect(textOf(data, "prompt-1")).toBe("typed after the refusal");
  });

  it("should_not_list_a_load_time_refresh_as_my_change", async () => {
    recordLoadRefresh(
      "flow-1",
      "prompt-1",
      { text: { value: "base" } } as never,
      { text: { value: "refreshed on open" } } as never,
    );
    act(() => {
      useFlowStore.setState({
        nodes: [
          node("prompt-1", "Prompt Template", "refreshed on open"),
          node("chat-1", "Chat Input", "base"),
        ],
      });
    });

    render(<DuplicateFlowModal />);
    act(() => useFlowConflictStore.getState().openDialog());

    expect(await screen.findByTestId("duplicate-flow-modal")).toBeVisible();
    expect(
      screen.queryByTestId("conflict-change-mine-node:prompt-1"),
    ).not.toBeInTheDocument();
    clearLoadRefreshes();
  });

  it("should_carry_an_edit_made_after_the_refusal_into_the_update", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    editAfterRefusal();

    act(() => useFlowConflictStore.getState().openDialog());
    await user.click(await screen.findByTestId("confirm-overwrite-flow"));

    expect(mockOverwriteFlow).toHaveBeenCalledTimes(1);
    const [{ data }] = mockOverwriteFlow.mock.calls[0];
    expect(textOf(data, "prompt-1")).toBe("typed after the refusal");
    expect(textOf(data, "chat-1")).toBe("base");
  });
});
