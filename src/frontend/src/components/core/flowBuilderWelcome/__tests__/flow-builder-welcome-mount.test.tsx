/**
 * Tests for the welcome-overlay mount, focused on the placeholder-cleanup
 * behavior.
 *
 * Bug: clicking "New Flow" eagerly creates an empty placeholder flow and opens
 * the welcome overlay on it. Picking a template via "Browse more…" spins up a
 * SECOND flow and navigates to it, leaving the blank placeholder orphaned — so
 * the user ends up with two flows when they wanted one. The mount must delete
 * the orphaned placeholder when the user navigates away from it.
 */

import { render } from "@testing-library/react";
import { FlowBuilderWelcomeMount } from "../flow-builder-welcome-mount";

// Heavy children — render nothing, we only exercise the mount's effects.
jest.mock("../flow-builder-welcome", () => ({
  __esModule: true,
  FlowBuilderWelcome: () => null,
}));
jest.mock("../../../../modals/templatesModal", () => ({
  __esModule: true,
  default: () => null,
}));

const close = jest.fn();
const setPendingMessage = jest.fn();
let welcomeState: {
  isOpen: boolean;
  openedForFlowId: string | null;
};
jest.mock("@/stores/flowBuilderWelcomeStore", () => ({
  __esModule: true,
  default: jest.fn((selector?: (state: unknown) => unknown) => {
    const state = {
      ...welcomeState,
      close,
      setPendingMessage,
    };
    return selector ? selector(state) : state;
  }),
}));

let flowsManagerState: {
  currentFlowId: string | null;
  flows: Array<{ id: string; data?: { nodes?: unknown[] } }>;
};
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector?: (state: unknown) => unknown) => {
    return selector ? selector(flowsManagerState) : flowsManagerState;
  }),
}));

const setAssistantSidebarOpen = jest.fn();
jest.mock("@/stores/assistantManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector?: (state: unknown) => unknown) => {
    const state = { setAssistantSidebarOpen };
    return selector ? selector(state) : state;
  }),
}));

jest.mock("@/components/ui/sidebar", () => ({
  __esModule: true,
  useSidebar: () => ({ setOpen: jest.fn(), setActiveSection: jest.fn() }),
}));

const applyTemplate = jest.fn();
jest.mock("../hooks/use-apply-template-to-current-flow", () => ({
  __esModule: true,
  useApplyTemplateToCurrentFlow: () => applyTemplate,
}));

const deleteFlow = jest.fn().mockResolvedValue(undefined);
jest.mock("@/hooks/flows/use-delete-flow", () => ({
  __esModule: true,
  default: () => ({ deleteFlow, isDeleting: false }),
}));

describe("FlowBuilderWelcomeMount placeholder cleanup", () => {
  beforeEach(() => {
    close.mockClear();
    deleteFlow.mockClear();
    welcomeState = { isOpen: true, openedForFlowId: "flow-placeholder" };
    flowsManagerState = {
      currentFlowId: "flow-placeholder",
      flows: [{ id: "flow-placeholder", data: { nodes: [] } }],
    };
  });

  it("should_delete_the_blank_placeholder_when_user_navigates_to_a_different_template_flow", () => {
    // Arrange — welcome opened for the blank placeholder, but the user picked a
    // template that spun up "flow-template" and navigated to it.
    welcomeState = { isOpen: true, openedForFlowId: "flow-placeholder" };
    flowsManagerState = {
      currentFlowId: "flow-template",
      flows: [
        { id: "flow-placeholder", data: { nodes: [] } },
        { id: "flow-template", data: { nodes: [{ id: "n1" }] } },
      ],
    };

    // Act
    render(<FlowBuilderWelcomeMount />);

    // Assert — the orphaned blank placeholder is deleted (single flow remains)
    expect(deleteFlow).toHaveBeenCalledWith({ id: "flow-placeholder" });
    expect(close).toHaveBeenCalled();
  });

  it("should_not_delete_anything_when_still_on_the_placeholder_flow", () => {
    // Quick-template path mutates the placeholder in place — same flow id, so
    // there is nothing to clean up.
    welcomeState = { isOpen: true, openedForFlowId: "flow-placeholder" };
    flowsManagerState = {
      currentFlowId: "flow-placeholder",
      flows: [{ id: "flow-placeholder", data: { nodes: [] } }],
    };

    render(<FlowBuilderWelcomeMount />);

    expect(deleteFlow).not.toHaveBeenCalled();
  });

  it("should_not_delete_the_placeholder_when_it_already_has_nodes", () => {
    // Safety guard: never delete a flow the user actually built on.
    welcomeState = { isOpen: true, openedForFlowId: "flow-placeholder" };
    flowsManagerState = {
      currentFlowId: "flow-template",
      flows: [
        { id: "flow-placeholder", data: { nodes: [{ id: "kept" }] } },
        { id: "flow-template", data: { nodes: [{ id: "n1" }] } },
      ],
    };

    render(<FlowBuilderWelcomeMount />);

    expect(deleteFlow).not.toHaveBeenCalled();
  });
});
