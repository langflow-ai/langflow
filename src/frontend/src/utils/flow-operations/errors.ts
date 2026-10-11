/** The errors the editor's flow operation applier raises, named and coded as the engine's are. */

export type FlowOperationErrorName =
  | "FlowOperationValidationError"
  | "FlowOperationPreconditionError"
  | "FlowDataValidationError";

export class FlowOperationError extends Error {
  constructor(
    public readonly name: FlowOperationErrorName,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    // Keep instanceof working when compiled to an ES5 target.
    Object.setPrototypeOf(this, FlowOperationError.prototype);
  }
}

export function invalidOperation(
  message: string,
  code = "FLOW_OPERATION_INVALID",
): FlowOperationError {
  return new FlowOperationError("FlowOperationValidationError", code, message);
}

export function failedExpectation(message: string): FlowOperationError {
  return new FlowOperationError(
    "FlowOperationPreconditionError",
    "EXPECTATION_FAILED",
    message,
  );
}

export function invalidGraph(message: string): FlowOperationError {
  return new FlowOperationError(
    "FlowDataValidationError",
    "FLOW_GRAPH_INVALID",
    message,
  );
}
