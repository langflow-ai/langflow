import { fireEvent, render, screen } from "@testing-library/react";
import { FlowEditCarousel } from "../assistant-flow-edit-card";

jest.mock("@/stores/flowStore", () => {
  const state = {
    nodes: [],
    edges: [],
    setNodes: jest.fn(),
  };
  const fn = (selector?: (s: typeof state) => unknown) =>
    selector ? selector(state) : state;
  fn.getState = () => state;
  return { __esModule: true, default: fn };
});

// eslint-disable-next-line @typescript-eslint/no-var-requires
const flowStoreState = (
  require("@/stores/flowStore") as {
    default: { getState: () => { setNodes: jest.Mock } };
  }
).default.getState();

const LONG =
  "Set system_prompt to 'You are an animal onomatopoeia assistant. Your job is to help the user identify the sound an animal makes by using the AnimalSoundComponent tool whenever an animal name is provided or inferred from the request. Always use the tool before answering.'";
const SHORT = "Set temperature to 0.7";

function makeAction(description: string) {
  return {
    id: "a1",
    type: "edit_field" as const,
    description,
    component_id: "Agent-1",
    component_type: "Agent",
    field: "system_prompt",
    old_value: "old",
    new_value: "new",
    patch: [],
    status: "pending" as const,
  };
}

function renderCard(description: string) {
  render(
    <FlowEditCarousel
      actions={[makeAction(description) as never]}
      onUpdateAction={jest.fn()}
    />,
  );
}

// The summary is now a short, clean one-line preview (backend collapses
// whitespace + truncates), so it no longer trips the description-length
// clamp. The user must STILL be able to review the FULL proposed value
// before approving — Show more must key off the value, not the summary,
// and expand to the complete value with real line breaks.
const CLEAN_SUMMARY =
  'Set system_prompt to "You are an animal onomatopoeia assistant. Use the tool…" on Agent';
const FULL_VALUE =
  "You are an animal onomatopoeia assistant.\nUse the tool.\n- rule one\n- rule two\nUNIQUE_TAIL_MARKER_42";

function renderValueCard() {
  const action = {
    id: "a1",
    type: "edit_field" as const,
    description: CLEAN_SUMMARY,
    component_id: "Agent-1",
    component_type: "Agent",
    field: "system_prompt",
    old_value: "You are an old assistant.",
    new_value: FULL_VALUE,
    patch: [],
    status: "pending" as const,
  };
  render(
    <FlowEditCarousel actions={[action as never]} onUpdateAction={jest.fn()} />,
  );
}

describe("FlowEditCard — full value review (regression)", () => {
  it("should_offer_show_more_when_value_is_long_even_if_summary_is_short", () => {
    renderValueCard();
    expect(screen.getByText(CLEAN_SUMMARY)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /show more/i }),
    ).toBeInTheDocument();
  });

  it("should_reveal_the_full_value_only_after_show_more", () => {
    renderValueCard();
    expect(screen.queryByText(/UNIQUE_TAIL_MARKER_42/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /show more/i }));

    expect(screen.getByText(/UNIQUE_TAIL_MARKER_42/)).toBeInTheDocument();
    expect(screen.getByText(/rule one/)).toBeInTheDocument();
  });

  it("should_use_the_same_ghost_emerald_button_pattern_as_other_cards", () => {
    renderValueCard();
    const accept = screen.getByRole("button", { name: /accept/i });
    const dismiss = screen.getByRole("button", { name: /dismiss/i });
    // Affirmative action matches the emerald ghost pattern used by the
    // plan / flow / component cards — NOT the old solid bg-primary.
    expect(accept.className).toContain("text-accent-emerald-foreground");
    expect(accept.className).not.toContain("bg-primary");
    expect(dismiss.className).not.toContain("bg-secondary-foreground");
  });
});

describe("FlowEditCarousel — Accept All applies patches (data-loss regression)", () => {
  // Bug: handleAcceptAll only marked actions "applied" and never ran the
  // JSON-Patch setNodes logic. The user saw green checks, the
  // edit-continuation fired, saveFlow() persisted the UNCHANGED canvas,
  // and the backend ran against pre-edit values — silent data loss.
  function patchedAction(id: string, idx: number) {
    return {
      id,
      type: "edit_field" as const,
      description: `Set system_prompt on node ${idx}`,
      component_id: `Agent-${idx}`,
      component_type: "Agent",
      field: "system_prompt",
      old_value: "old",
      new_value: "new",
      patch: [
        {
          op: "replace",
          path: `/data/nodes/${idx}/data/node/template/system_prompt/value`,
          value: `NEW_${id}`,
        },
      ],
      status: "pending" as const,
    };
  }

  it("should_apply_every_pending_patch_when_accept_all_is_clicked", () => {
    flowStoreState.setNodes.mockClear();
    const onUpdateAction = jest.fn();
    render(
      <FlowEditCarousel
        actions={[patchedAction("a1", 0), patchedAction("a2", 1)] as never}
        onUpdateAction={onUpdateAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /accept all/i }));

    // The patch MUST be applied to the canvas for every pending action,
    // not merely flagged as applied.
    expect(flowStoreState.setNodes).toHaveBeenCalledTimes(2);
    expect(onUpdateAction).toHaveBeenCalledWith("a1", "applied");
    expect(onUpdateAction).toHaveBeenCalledWith("a2", "applied");
  });
});

describe("FlowEditCarousel — hooks order (crash regression)", () => {
  // Bug: `if (!current) return null` ran BEFORE the useCallback hooks.
  // `actions` grows incrementally as edit_field SSE events land, so the
  // card first renders with 0 actions (early-return, 0 hooks) then with
  // N actions (hooks run) — React: "Rendered more hooks than during the
  // previous render", crashing the panel mid-stream.
  it("should_not_crash_when_actions_grow_from_empty_to_populated", () => {
    const { rerender } = render(
      <FlowEditCarousel actions={[]} onUpdateAction={jest.fn()} />,
    );

    expect(() =>
      rerender(
        <FlowEditCarousel
          actions={[makeAction(SHORT) as never]}
          onUpdateAction={jest.fn()}
        />,
      ),
    ).not.toThrow();

    expect(screen.getByText(SHORT)).toBeInTheDocument();
  });
});

describe("FlowEditCard — long description collapsing", () => {
  it("should_show_short_description_without_a_toggle", () => {
    renderCard(SHORT);
    expect(screen.getByText(SHORT)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /show more/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /show less/i })).toBeNull();
  });

  it("should_collapse_long_description_and_offer_show_more", () => {
    renderCard(LONG);
    // Full text stays in the DOM (CSS clamps it visually) so nothing is lost.
    expect(screen.getByText(LONG)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /show more/i }),
    ).toBeInTheDocument();
  });

  it("should_toggle_between_show_more_and_show_less", () => {
    renderCard(LONG);
    const moreBtn = screen.getByRole("button", { name: /show more/i });

    fireEvent.click(moreBtn);
    expect(
      screen.getByRole("button", { name: /show less/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /show more/i })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /show less/i }));
    expect(
      screen.getByRole("button", { name: /show more/i }),
    ).toBeInTheDocument();
  });
});
