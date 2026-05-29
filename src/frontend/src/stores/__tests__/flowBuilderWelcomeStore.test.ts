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
});
