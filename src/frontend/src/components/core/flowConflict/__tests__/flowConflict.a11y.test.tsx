import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowConflict } from "@/stores/flowConflictStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { AllNodeType } from "@/types/flow";
import { axe } from "@/utils/a11y-test";
import { ConflictBanner, ConflictCanvasFrame } from "../ConflictBanner";
import DuplicateFlowModal from "../DuplicateFlowModal";

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
  usePostForkFlow: () => ({ mutate: jest.fn(), isPending: false }),
}));

jest.mock("@/controllers/API/queries/flows/use-post-overwrite-flow", () => ({
  usePostOverwriteFlow: () => ({ mutate: jest.fn(), isPending: false }),
}));

const node = (
  id: string,
  displayName: string,
  fields: Record<string, { value: unknown; password?: boolean }> = {},
  position = { x: 0, y: 0 },
): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position,
    data: {
      id,
      type: "Component",
      node: {
        display_name: displayName,
        description: "",
        documentation: "",
        template: Object.fromEntries(
          Object.entries(fields).map(([name, spec]) => [
            name,
            {
              type: "str",
              required: false,
              list: false,
              show: true,
              readonly: false,
              display_name: name,
              ...spec,
            },
          ]),
        ),
      },
    },
  }) as unknown as AllNodeType;

const conflict = (overrides: Partial<FlowConflict> = {}): FlowConflict => ({
  flowId: "flow-1",
  author: { id: "user-2", username: "carlos" },
  isSelf: false,
  modifiedAt: "2026-09-02T10:00:00Z",
  expectedToken: "token-a",
  currentToken: "token-b",
  theirFlow: null,
  ...overrides,
});

/** Base graph, my canvas, and their version — enough for every dialog state. */
const seedStores = () => {
  const base = {
    nodes: [
      node("prompt-1", "Prompt Template", { template: { value: "base" } }),
      node("model-1", "OpenAI Model", { temperature: { value: "0.7" } }),
      node("secret-1", "OpenAI", {
        api_key: { value: "sk-base", password: true },
      }),
    ],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  };
  const mine = [
    node("prompt-1", "Prompt Template", { template: { value: "mine" } }),
    node("model-1", "OpenAI Model", { temperature: { value: "0.7" } }),
    node("secret-1", "OpenAI", {
      api_key: { value: "sk-base", password: true },
    }),
  ];
  const theirs = {
    nodes: [
      node("prompt-1", "Prompt Template", { template: { value: "theirs" } }),
      node("model-1", "OpenAI Model", { temperature: { value: "0.3" } }),
      node("secret-1", "OpenAI", {
        api_key: { value: "sk-rotated", password: true },
      }),
      node("kb-1", "Knowledge Base Search", {
        long: { value: "a very long retrieval instruction ".repeat(8) },
      }),
    ],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  };

  useFlowsManagerStore.setState({
    currentFlow: { id: "flow-1", name: "probe", description: "", data: base },
  });
  useFlowStore.setState({ nodes: mine, edges: [] });
  useFlowConflictStore.setState({
    conflict: conflict({
      theirFlow: { id: "flow-1", name: "probe", description: "", data: theirs },
    }),
    dialogOpen: true,
    abandonedFlowIds: new Set<string>(),
  });
};

describe("conflict banner accessibility", () => {
  beforeEach(() => {
    useFlowConflictStore.setState({
      conflict: conflict(),
      dialogOpen: false,
      abandonedFlowIds: new Set<string>(),
    });
  });

  it("should_have_no_violations_when_another_person_edited", async () => {
    render(<ConflictBanner flowId="flow-1" />);

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_have_no_violations_when_the_other_writer_is_me", async () => {
    useFlowConflictStore.setState({ conflict: conflict({ isSelf: true }) });

    render(<ConflictBanner flowId="flow-1" />);

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_announce_itself_without_stealing_focus", () => {
    render(<ConflictBanner flowId="flow-1" />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(document.body).toHaveFocus();
  });

  it("should_expose_the_review_action_as_a_named_button", () => {
    render(<ConflictBanner flowId="flow-1" />);

    expect(
      screen.getByTestId("flow-conflict-review-button"),
    ).toHaveAccessibleName(/review/i);
  });

  it("should_render_nothing_for_a_different_flow", () => {
    render(<ConflictBanner flowId="another-flow" />);

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

describe("duplicate dialog accessibility", () => {
  beforeEach(seedStores);

  it("should_have_no_violations_in_its_default_state", async () => {
    render(<DuplicateFlowModal />);

    expect(await screen.findByTestId("duplicate-flow-modal")).toBeVisible();
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_have_no_violations_with_a_change_selected", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    const selectable = screen
      .getAllByRole("checkbox")
      .filter((box) => !box.hasAttribute("disabled"));
    await user.click(selectable[0]);

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_have_no_violations_with_the_raw_diff_expanded", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    await user.click(
      screen.getAllByRole("button", { name: /show changes/i })[0],
    );

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_give_every_change_checkbox_an_accessible_name", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    for (const box of screen.getAllByRole("checkbox")) {
      expect(box).toHaveAccessibleName();
    }
  });

  it("should_tie_the_trade_off_note_to_its_checkbox_for_screen_readers", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    const described = screen
      .getAllByRole("checkbox")
      .filter((box) => box.getAttribute("aria-describedby"));

    expect(described.length).toBeGreaterThan(0);
  });

  it("should_let_me_take_their_version_of_a_component_we_both_changed", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // Both sides edited prompt-1, so their row must be a choice, not a refusal.
    const contested = screen.getByTestId(
      "conflict-change-theirs-node:prompt-1",
    );
    const theirs = contested.querySelector('button[role="checkbox"]');

    expect(theirs).not.toBeDisabled();
    await user.click(theirs as HTMLElement);

    expect(theirs).toHaveAttribute("data-state", "checked");
    expect(
      screen.getByText(/replaced by .*'s version of this component/i),
    ).toBeInTheDocument();
  });

  it("should_have_no_violations_after_taking_their_contested_version", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    const contested = screen.getByTestId(
      "conflict-change-theirs-node:prompt-1",
    );
    await user.click(
      contested.querySelector('button[role="checkbox"]') as HTMLElement,
    );

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_mark_my_own_changes_as_not_selectable", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    expect(
      screen.getByRole("heading", { name: /your changes/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/always included/i)).toBeInTheDocument();
  });

  it("should_never_render_a_secret_value_in_any_state", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    for (const trigger of screen.queryAllByRole("button", {
      name: /show changes/i,
    })) {
      await user.click(trigger);
    }

    expect(document.body.textContent).not.toContain("sk-base");
    expect(document.body.textContent).not.toContain("sk-rotated");
  });
});

describe("conflict UI during a version preview", () => {
  const previewing = (label: string | null) =>
    useVersionPreviewStore.setState({ previewLabel: label });

  afterEach(() => previewing(null));

  it("should_hide_the_banner_while_a_past_version_is_on_screen", () => {
    useFlowConflictStore.setState({ conflict: conflict() });
    previewing("v3");

    render(<ConflictBanner flowId="flow-1" />);

    // Version history owns the screen with its own overlay, and none of the
    // actions here apply to a read-only view of the past.
    expect(
      screen.queryByTestId("flow-conflict-banner"),
    ).not.toBeInTheDocument();
  });

  it("should_hide_the_canvas_frame_while_a_past_version_is_on_screen", () => {
    useFlowConflictStore.setState({ conflict: conflict() });
    previewing("v3");

    render(<ConflictCanvasFrame flowId="flow-1" />);

    expect(screen.queryByTestId("flow-conflict-frame")).not.toBeInTheDocument();
  });

  it("should_bring_the_banner_back_when_the_preview_closes", () => {
    useFlowConflictStore.setState({ conflict: conflict() });
    previewing("v3");
    const { rerender } = render(<ConflictBanner flowId="flow-1" />);

    previewing(null);
    rerender(<ConflictBanner flowId="flow-1" />);

    // Suppressed, never resolved: the conflict is still unresolved underneath.
    expect(screen.getByTestId("flow-conflict-banner")).toBeInTheDocument();
  });
});
