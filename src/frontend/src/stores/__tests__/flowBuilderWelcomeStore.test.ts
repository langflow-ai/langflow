/**
 * Tests for the FlowBuilderWelcome store — the small piece of state that
 * coordinates the "welcome overlay" on a freshly-created empty flow with the
 * AssistantPanel hand-off.
 */

import useFlowBuilderWelcomeStore from "../flowBuilderWelcomeStore";

describe("useFlowBuilderWelcomeStore", () => {
  beforeEach(() => {
    // Reset to a known clean baseline so cross-test pollution can't mask a
    // regression in the default state contract.
    useFlowBuilderWelcomeStore.setState({
      isOpen: false,
      pendingMessage: null,
    });
  });

  describe("default state", () => {
    it("should_start_closed_with_no_pending_message", () => {
      const state = useFlowBuilderWelcomeStore.getState();
      expect(state.isOpen).toBe(false);
      expect(state.pendingMessage).toBeNull();
    });
  });

  describe("open / close", () => {
    it("should_set_isOpen_true_when_open_is_called", () => {
      useFlowBuilderWelcomeStore.getState().open();
      expect(useFlowBuilderWelcomeStore.getState().isOpen).toBe(true);
    });

    it("should_set_isOpen_false_when_close_is_called", () => {
      useFlowBuilderWelcomeStore.setState({ isOpen: true });
      useFlowBuilderWelcomeStore.getState().close();
      expect(useFlowBuilderWelcomeStore.getState().isOpen).toBe(false);
    });

    it("should_clear_pendingMessage_when_close_is_called", () => {
      // Defensive contract: closing the overlay must also drop any unconsumed
      // pending message so a subsequent open doesn't replay stale input.
      useFlowBuilderWelcomeStore.setState({
        isOpen: true,
        pendingMessage: "stale",
      });
      useFlowBuilderWelcomeStore.getState().close();
      expect(useFlowBuilderWelcomeStore.getState().pendingMessage).toBeNull();
    });
  });

  describe("pendingMessage handoff", () => {
    it("should_store_the_message_when_setPendingMessage_is_called", () => {
      useFlowBuilderWelcomeStore
        .getState()
        .setPendingMessage("build me a chatbot");
      expect(useFlowBuilderWelcomeStore.getState().pendingMessage).toBe(
        "build me a chatbot",
      );
    });

    it("should_clear_only_the_pendingMessage_when_clearPendingMessage_is_called", () => {
      useFlowBuilderWelcomeStore.setState({
        isOpen: true,
        pendingMessage: "build me a chatbot",
      });
      useFlowBuilderWelcomeStore.getState().clearPendingMessage();
      const state = useFlowBuilderWelcomeStore.getState();
      expect(state.pendingMessage).toBeNull();
      // isOpen is untouched — clearing is an independent operation from closing.
      expect(state.isOpen).toBe(true);
    });
  });

  describe("dismissForNavigation", () => {
    it("should_hide_the_overlay_immediately", () => {
      useFlowBuilderWelcomeStore.setState({
        isOpen: true,
        openedForFlowId: "flow-placeholder",
      });

      useFlowBuilderWelcomeStore.getState().dismissForNavigation();

      // The sidebar keys off isOpen, so this MUST be false before the new flow
      // paints — otherwise it stays at display:none and ReactFlow fits against
      // a canvas width it is about to lose.
      expect(useFlowBuilderWelcomeStore.getState().isOpen).toBe(false);
    });

    it("should_retain_openedForFlowId_so_the_placeholder_can_still_be_reaped", () => {
      useFlowBuilderWelcomeStore.setState({
        isOpen: true,
        openedForFlowId: "flow-placeholder",
      });

      useFlowBuilderWelcomeStore.getState().dismissForNavigation();

      // Unlike close(), this keeps the id — the mount's cleanup effect is the
      // only thing that knows how to delete the orphaned blank placeholder.
      expect(useFlowBuilderWelcomeStore.getState().openedForFlowId).toBe(
        "flow-placeholder",
      );
    });

    it("should_drop_a_stale_pendingMessage", () => {
      useFlowBuilderWelcomeStore.setState({
        isOpen: true,
        pendingMessage: "stale",
      });

      useFlowBuilderWelcomeStore.getState().dismissForNavigation();

      expect(useFlowBuilderWelcomeStore.getState().pendingMessage).toBeNull();
    });
  });
});
