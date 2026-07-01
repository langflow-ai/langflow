import { fireEvent, render, screen } from "@testing-library/react";
import type { PlanLink, PlanNode } from "@/controllers/API/queries/lothal";
import { NodeLinksCard } from "../plan/NodeLinksCard";

const node = (id: string, name: string): PlanNode => ({
  id,
  parent_id: null,
  kind: "story",
  state: "draft",
  name,
  depth: 1,
});

const link = (source_id: string, target_id: string): PlanLink => ({
  id: `${source_id}->${target_id}`,
  source_id,
  target_id,
  link_type: "blocks",
});

describe("NodeLinksCard", () => {
  it("navigates to a resolvable peer on click", () => {
    const onSelect = jest.fn();
    render(
      <NodeLinksCard
        nodeId="a"
        nodes={[node("a", "Alpha"), node("b", "Bravo")]}
        links={[link("a", "b")]}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByText("Bravo"));
    expect(onSelect).toHaveBeenCalledWith("b");
  });

  it("disables a link whose peer is missing from the snapshot and never selects it", () => {
    const onSelect = jest.fn();
    render(
      <NodeLinksCard
        nodeId="a"
        nodes={[node("a", "Alpha")]} // the "ghost" peer isn't in the snapshot
        links={[link("a", "ghost")]}
        onSelect={onSelect}
      />,
    );
    // The row shows the unresolved peer id (sliced) but is disabled; guarded twice
    // (the `disabled` attr + the onClick check), a click never navigates.
    const row = screen.getByText("ghost").closest("button");
    expect(row).toBeDisabled();
    fireEvent.click(row as HTMLElement);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("shows the empty state when the node has no typed links", () => {
    render(
      <NodeLinksCard
        nodeId="a"
        nodes={[node("a", "Alpha")]}
        links={[]}
        onSelect={jest.fn()}
      />,
    );
    expect(
      screen.getByText("No typed links on this node."),
    ).toBeInTheDocument();
  });
});
