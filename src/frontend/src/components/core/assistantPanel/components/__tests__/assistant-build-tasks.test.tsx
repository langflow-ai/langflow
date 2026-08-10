import { render, screen } from "@testing-library/react";
import type {
  BuildTask,
  InProgressBuildTask,
} from "../../assistant-panel.types";
import { AssistantBuildTasks } from "../assistant-build-tasks";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
  initReactI18next: { type: "3rdParty", init: jest.fn() },
}));

function makeTask(overrides: Partial<BuildTask>): BuildTask {
  return {
    action: "add_component",
    receivedAt: 1,
    ...overrides,
  };
}

function makeInProgress(
  overrides: Partial<InProgressBuildTask> = {},
): InProgressBuildTask {
  return {
    tool: "add_component",
    componentType: "ChatInput",
    receivedAt: 2,
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

  describe("in-progress row", () => {
    it("should_render_a_spinner_row_while_a_tool_is_executing", () => {
      const { container } = render(
        <AssistantBuildTasks tasks={[]} inProgressTask={makeInProgress()} />,
      );
      expect(
        screen.getByTestId("assistant-build-task-in-progress"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("assistant.buildTasks.inProgress.adding"),
      ).toBeInTheDocument();
      expect(container.querySelector(".animate-spin")).not.toBeNull();
    });

    it("should_render_completed_tasks_and_the_in_progress_row_together", () => {
      render(
        <AssistantBuildTasks
          tasks={[
            makeTask({ action: "add_component", componentType: "ChatInput" }),
          ]}
          inProgressTask={makeInProgress({
            tool: "connect_components",
            componentType: undefined,
          })}
        />,
      );
      expect(screen.getByText(/Added ChatInput/i)).toBeInTheDocument();
      expect(
        screen.getByText("assistant.buildTasks.inProgress.wiring"),
      ).toBeInTheDocument();
    });

    it("should_not_render_the_row_when_no_tool_is_in_progress", () => {
      render(
        <AssistantBuildTasks
          tasks={[makeTask({ action: "configure", componentId: "Agent-xyz" })]}
        />,
      );
      expect(
        screen.queryByTestId("assistant-build-task-in-progress"),
      ).not.toBeInTheDocument();
    });

    it("should_freeze_with_an_alert_icon_instead_of_a_spinner_on_error", () => {
      const { container } = render(
        <AssistantBuildTasks
          tasks={[]}
          inProgressTask={makeInProgress()}
          hasError
        />,
      );
      expect(
        screen.getByText("assistant.buildTasks.inProgress.adding"),
      ).toBeInTheDocument();
      expect(container.querySelector(".animate-spin")).toBeNull();
      expect(container.querySelector(".text-destructive")).not.toBeNull();
    });

    it("should_fall_back_to_the_backend_label_for_unknown_tools", () => {
      render(
        <AssistantBuildTasks
          tasks={[]}
          inProgressTask={makeInProgress({
            tool: "future_tool",
            label: "Doing something new",
          })}
        />,
      );
      expect(screen.getByText("Doing something new")).toBeInTheDocument();
    });

    it("should_use_the_i18n_label_for_use_template", () => {
      render(
        <AssistantBuildTasks
          tasks={[]}
          inProgressTask={makeInProgress({
            tool: "use_template",
            label: "Applying template Memory Chatbot",
            componentType: undefined,
          })}
        />,
      );
      expect(
        screen.getByText("assistant.buildTasks.inProgress.applyingTemplate"),
      ).toBeInTheDocument();
    });
  });

  describe("i18n key coverage", () => {
    const locales = ["de", "en", "es", "fr", "ja", "pt", "zh-Hans"];

    it.each(locales)(
      "locale %s has every inProgress key used by the component",
      (locale) => {
        // Divergence guard: a key missing in one language is a bug.
        const messages = require(`@/locales/${locale}.json`);
        const requiredKeys = [
          "assistant.buildTasks.inProgress.adding",
          "assistant.buildTasks.inProgress.removing",
          "assistant.buildTasks.inProgress.wiring",
          "assistant.buildTasks.inProgress.configuring",
          "assistant.buildTasks.inProgress.buildingFlow",
          "assistant.buildTasks.inProgress.proposingEdit",
          "assistant.buildTasks.inProgress.applyingTemplate",
          "assistant.buildTasks.inProgress.working",
          "assistant.buildTasks.inProgress.component",
        ];
        for (const key of requiredKeys) {
          expect(messages[key]).toBeTruthy();
        }
      },
    );
  });
});
