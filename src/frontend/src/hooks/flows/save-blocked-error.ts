/**
 * Raised when a save was not attempted at all, because the flow is in conflict.
 *
 * Returning quietly instead let every caller's success path run: Ctrl+S and the
 * flow settings dialog both announced "saved" over a write that never happened,
 * at the exact moment the person most needed to be told otherwise.
 *
 * It lives in its own module because the callers that must recognise it also mock
 * ``use-save-flow`` in their tests, and a mocked module exports no class.
 */
export class FlowSaveBlockedError extends Error {
  readonly flowId: string;

  constructor(flowId: string) {
    super(
      "This flow is in conflict, so it cannot be saved until that is resolved.",
    );
    // Required when the build target predates native class semantics: extending
    // Error there loses the prototype chain, so `instanceof` answers false for a
    // genuine instance and every caller's guard falls through — which is exactly
    // the "saved!" over a write that never happened this class exists to stop.
    Object.setPrototypeOf(this, FlowSaveBlockedError.prototype);
    this.name = "FlowSaveBlockedError";
    this.flowId = flowId;
  }
}
