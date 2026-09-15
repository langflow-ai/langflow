import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { FlowConflict } from "@/stores/flowConflictStore";
import useFlowConflictStore from "@/stores/flowConflictStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useVersionPreviewStore from "@/stores/versionPreviewStore";
import type { AllNodeType } from "@/types/flow";
import { axe } from "@/utils/a11y-test";
import { readConflictDraft } from "@/utils/conflict-draft";
import { RawDiff } from "../ChangeRow";
import { ConflictBanner, ConflictCanvasFrame } from "../ConflictBanner";
import DuplicateFlowModal from "../DuplicateFlowModal";
import RestoreDraftBanner from "../RestoreDraftBanner";

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

jest.mock("@/utils/conflict-draft", () => ({
  ...jest.requireActual("@/utils/conflict-draft"),
  readConflictDraft: jest.fn(),
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

/** Open a contested component's card, the way the chevron does. */
const openConflict = async (
  user: ReturnType<typeof userEvent.setup>,
  targetKey = "node:prompt-1",
) => {
  await user.click(screen.getByTestId(`conflict-toggle-${targetKey}`));
  return screen.getByTestId(`conflict-resolve-${targetKey}`);
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

describe("load latest confirmation accessibility", () => {
  beforeEach(seedStores);

  const openConfirm = async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");
    await user.click(screen.getByTestId("dialog-load-latest-button"));
    await screen.findByTestId("load-latest-confirm");
    return user;
  };

  it("should_have_no_violations_while_asking_for_confirmation", async () => {
    await openConfirm();

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_replace_the_actions_rather_than_stack_a_second_layer", async () => {
    await openConfirm();

    // The band it replaces is the one the reader was already looking at, so the
    // exits it is asking about must not still be clickable behind it.
    expect(
      screen.queryByTestId("confirm-overwrite-flow"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("load-latest-confirm-button"),
    ).toHaveAccessibleName(/load latest/i);
  });

  it("should_go_back_to_the_exits_when_cancelled", async () => {
    const user = await openConfirm();

    await user.click(
      within(screen.getByTestId("load-latest-confirm")).getByRole("button", {
        name: /cancel/i,
      }),
    );

    expect(screen.queryByTestId("load-latest-confirm")).not.toBeInTheDocument();
    expect(screen.getByTestId("confirm-overwrite-flow")).toBeInTheDocument();
  });
});

describe("restore draft banner accessibility", () => {
  beforeEach(() => {
    useFlowConflictStore.setState({
      conflict: null,
      dialogOpen: false,
      abandonedFlowIds: new Set<string>(),
    });
    (readConflictDraft as jest.Mock).mockReturnValue({
      savedAt: new Date("2026-01-01T14:39:00Z").toISOString(),
      versionToken: "token-1",
      secretsCleared: true,
      data: { nodes: [], edges: [] },
    });
  });

  it("should_have_no_violations_when_offering_stranded_work", async () => {
    render(<RestoreDraftBanner flowId="flow-1" />);
    await screen.findByTestId("restore-draft-banner");

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_expose_both_choices_as_named_buttons", async () => {
    render(<RestoreDraftBanner flowId="flow-1" />);
    const banner = await screen.findByTestId("restore-draft-banner");

    expect(
      within(banner).getByRole("button", { name: /restore/i }),
    ).toBeInTheDocument();
    expect(
      within(banner).getByRole("button", { name: /discard/i }),
    ).toBeInTheDocument();
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

    await openConflict(user);
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

  it("should_let_me_take_their_version_of_a_component_we_both_changed", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // Both sides edited prompt-1, so it is raised out of the plain list into a
    // choice between the two versions.
    const resolve = await openConflict(user);
    await user.click(
      within(resolve).getByRole("radio", { name: /keep carlos's version/i }),
    );

    // Answered, so the card folds back down and its header carries the verdict.
    expect(
      within(screen.getByTestId("conflict-resolve-node:prompt-1")).getByText(
        /keeping carlos's version/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("radio", { name: /keep carlos's version/i }),
    ).not.toBeInTheDocument();
  });

  it("should_have_no_violations_after_taking_their_contested_version", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    const resolve = await openConflict(user);
    await user.click(
      within(resolve).getByRole("radio", { name: /keep carlos's version/i }),
    );

    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_mark_my_own_changes_as_not_selectable", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    expect(
      screen.getByRole("heading", { name: /your changes/i }),
    ).toBeInTheDocument();
  });

  it("should_start_a_conflict_with_neither_version_chosen", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    const resolve = await openConflict(user);

    // No standing answer. A preselected side is a decision made for the reader
    // and then saved under their name, which is what this whole dialog exists
    // to prevent.
    for (const radio of within(resolve).getAllByRole("radio")) {
      expect(radio).not.toBeChecked();
    }
  });

  it("should_let_me_switch_a_contested_component_back_to_my_version", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    await user.click(
      within(await openConflict(user)).getByRole("radio", {
        name: /keep carlos's version/i,
      }),
    );
    expect(
      within(screen.getByTestId("conflict-resolve-node:prompt-1")).getByText(
        /keeping carlos's version/i,
      ),
    ).toBeInTheDocument();

    await user.click(
      within(await openConflict(user)).getByRole("radio", {
        name: /keep my version/i,
      }),
    );
    expect(
      within(screen.getByTestId("conflict-resolve-node:prompt-1")).getByText(
        /keeping my version/i,
      ),
    ).toBeInTheDocument();
  });

  it("should_offer_the_raw_diff_only_where_a_version_is_being_chosen", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // prompt-1 is contested, so comparing the two versions is the point, and
    // the comparison lives inside the card that offers the choice.
    expect(
      within(await openConflict(user)).getAllByRole("button", {
        name: /show changes/i,
      }).length,
    ).toBe(2);

    // kb-1 is theirs alone: an ordinary change to include or not, with no
    // version of mine to weigh it against, so the control would only add noise.
    expect(
      within(
        screen.getByTestId("conflict-change-theirs-node:kb-1"),
      ).queryByRole("button", { name: /show changes/i }),
    ).not.toBeInTheDocument();
  });

  it("should_keep_values_out_of_the_two_versions_it_compares", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    const card = await openConflict(user);

    // Both sides name the field and stop there. Quoting each value inside the
    // card turns a comparison into two paragraphs of prose.
    expect(within(card).getAllByText(/template updated\.$/i).length).toBe(2);
    expect(within(card).queryByText(/updated from/i)).not.toBeInTheDocument();
  });

  it("should_keep_a_conflict_closed_until_it_is_asked_for", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // A conflict is a decision, not a diff to read. Opening every comparison at
    // once buries the one thing the reader has to do.
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(screen.getByTestId("conflict-toggle-node:prompt-1")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    // The header still says an answer is owed.
    expect(
      within(screen.getByTestId("conflict-resolve-node:prompt-1")).getByText(
        /action required/i,
      ),
    ).toBeInTheDocument();
  });

  it("should_refuse_to_update_the_flow_while_a_conflict_is_unanswered", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // Writing the original overwrites somebody else, so it stays shut until
    // every contested component has been answered.
    expect(screen.getByTestId("confirm-overwrite-flow")).toBeDisabled();
    expect(screen.getByTestId("conflict-blocked-hint")).toBeInTheDocument();

    await user.click(
      within(await openConflict(user)).getByRole("radio", {
        name: /keep my version/i,
      }),
    );

    expect(screen.getByTestId("confirm-overwrite-flow")).toBeEnabled();
    expect(
      screen.queryByTestId("conflict-blocked-hint"),
    ).not.toBeInTheDocument();
  });

  it("should_leave_duplicating_open_while_a_conflict_is_unanswered", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // The way out for somebody who cannot decide. It costs nobody their work,
    // so blocking it would leave them with only Cancel and Load Latest — and
    // Load Latest throws away the very edits they came here to keep.
    expect(screen.getByTestId("confirm-duplicate-flow")).toBeEnabled();
  });

  it("should_put_the_component_name_before_its_badge", async () => {
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    // Titles share a starting column and the badges follow them, so the list
    // can be read down its left edge.
    const row = screen.getByTestId("conflict-change-theirs-node:kb-1");
    const text = row.textContent ?? "";
    expect(text.indexOf("Knowledge Base Search")).toBeLessThan(
      text.indexOf("Added"),
    );

    const card = screen.getByTestId("conflict-resolve-node:prompt-1");
    const header = card.textContent ?? "";
    expect(header.indexOf("Prompt Template")).toBeLessThan(
      header.indexOf("Action required"),
    );
  });

  it("should_not_pour_a_whole_source_file_into_the_dialog", () => {
    // The real case is a component's `code` field: its whole Python source,
    // rendered twice in a box capped at 55vh, with the decision the dialog
    // exists for somewhere below it.
    const source = Array.from(
      { length: 400 },
      (_, line) =>
        `    self.value_${line} = "a fairly long line of component source"`,
    ).join("\n");

    render(<RawDiff before={source} after={`${source}\n    self.extra = 1`} />);

    for (const shown of document.querySelectorAll("span.whitespace-pre-wrap")) {
      const text = shown.textContent ?? "";
      expect(text.length).toBeLessThanOrEqual(800);
      expect(text.split("\n").length).toBeLessThanOrEqual(12);
    }
    // And it says it was cut, on both sides, rather than ending mid-line.
    expect(screen.getAllByText(/shown in part/i)).toHaveLength(2);
  });

  it("should_never_render_a_secret_value_in_any_state", async () => {
    const user = userEvent.setup();
    render(<DuplicateFlowModal />);
    await screen.findByTestId("duplicate-flow-modal");

    for (const toggle of screen.queryAllByTestId(/^conflict-toggle-/)) {
      await user.click(toggle);
    }
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
