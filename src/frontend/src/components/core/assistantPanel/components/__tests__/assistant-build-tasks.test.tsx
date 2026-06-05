import { render, screen } from "@testing-library/react";
import type { BuildTask } from "../../assistant-panel.types";
import { AssistantBuildTasks } from "../assistant-build-tasks";

function makeTask(overrides: Partial<BuildTask>): BuildTask {
  return {
    action: "add_component",
    receivedAt: 1,
    ...overrides,
  };
}

describe("AssistantBuildTasks", () => {
  it("should_render_nothing_when_tasks_is_empty", () => {
    const { container } = render(<AssistantBuildTasks tasks={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("should_render_one_row_per_task", () => {
    const tasks: BuildTask[] = [
      makeTask({ action: "add_component", componentType: "ChatInput" }),
      makeTask({
        action: "connect",
        sourceId: "ChatInput-a",
        targetId: "Agent-b",
        receivedAt: 2,
      }),
    ];
    render(<AssistantBuildTasks tasks={tasks} />);
    expect(screen.getAllByTestId(/^assistant-build-task-/)).toHaveLength(2);
  });

  it("should_label_add_component_with_the_component_type", () => {
    const tasks = [
      makeTask({ action: "add_component", componentType: "ChatInput" }),
    ];
    render(<AssistantBuildTasks tasks={tasks} />);
    expect(screen.getByText(/Added ChatInput/i)).toBeInTheDocument();
  });

  it("should_label_connect_with_source_and_target_ids", () => {
    const tasks = [
      makeTask({
        action: "connect",
        sourceId: "ChatInput-a",
        targetId: "Agent-b",
      }),
    ];
    render(<AssistantBuildTasks tasks={tasks} />);
    expect(screen.getByText(/ChatInput-a/)).toBeInTheDocument();
    expect(screen.getByText(/Agent-b/)).toBeInTheDocument();
  });

  it("should_label_configure_with_component_id", () => {
    const tasks = [makeTask({ action: "configure", componentId: "Agent-xyz" })];
    render(<AssistantBuildTasks tasks={tasks} />);
    expect(screen.getByText(/Configured Agent-xyz/i)).toBeInTheDocument();
  });

  it("should_label_remove_component_with_component_id", () => {
    const tasks = [
      makeTask({ action: "remove_component", componentId: "ChatInput-abc" }),
    ];
    render(<AssistantBuildTasks tasks={tasks} />);
    expect(screen.getByText(/Removed ChatInput-abc/i)).toBeInTheDocument();
  });

  // Build tasks are pure RESULTS (completed ops, no human-in-the-loop), so
  // they must NOT be wrapped in the bordered "card" box — just compact text
  // lines with a green check. The box is reserved for gated/HITL cards.
  it("should_render_compact_without_a_bordered_box", () => {
    const { container } = render(
      <AssistantBuildTasks
        tasks={[makeTask({ action: "configure", componentId: "Agent-xyz" })]}
      />,
    );
    const root = container.firstChild as HTMLElement;
    expect(root.className).not.toMatch(/\bborder\b/);
    expect(root.className).not.toMatch(/bg-muted/);
  });

  it("should_keep_a_green_check_per_task", () => {
    const { container } = render(
      <AssistantBuildTasks
        tasks={[makeTask({ action: "configure", componentId: "Agent-xyz" })]}
      />,
    );
    expect(
      container.querySelector(".text-accent-emerald-foreground"),
    ).not.toBeNull();
  });
});
