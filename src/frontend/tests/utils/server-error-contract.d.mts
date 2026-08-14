export type ServerErrorExpectation = {
  method: string;
  path: string;
  status: number;
  count: number;
};

export type ObservedServerError = Omit<ServerErrorExpectation, "count"> & {
  responseBody?: string;
};

export type ServerErrorContract = {
  expected: Array<ServerErrorExpectation & { observed: number }>;
  unexpected: ObservedServerError[];
  droppedUnexpected: number;
};

export type PendingRequestTracker<T> = {
  start(request: T): void;
  stop(): void;
  finish(request: T): void;
  drain(timeoutMs: number): Promise<T[]>;
  snapshot(): T[];
};

export type ResponseBodyReadResult =
  | { status: "success"; body: string }
  | { status: "timeout" | "error"; diagnostic: string };

export function createPendingRequestTracker<T>(): PendingRequestTracker<T>;
export function shouldTrackApiRequest(rawUrl: string): boolean;
export function shouldSettleApiRequestOnResponse(
  rawUrl: string,
  contentType: string,
): boolean;
export function sanitizeResponseExcerpt(
  body: string,
  maxLength?: number,
): string;
export function readResponseBodyWithTimeout(
  response: { text(): Promise<string> },
  options: { timeoutMs: number; label: string },
): Promise<ResponseBodyReadResult>;
export function createServerErrorContract(): ServerErrorContract;
export function expectServerError(
  contract: ServerErrorContract,
  expectation: ServerErrorExpectation,
): void;
export function observeServerError(
  contract: ServerErrorContract,
  observed: ObservedServerError,
): void;
export function getServerErrorContractFailures(contract: ServerErrorContract): {
  unexpected: ObservedServerError[];
  droppedUnexpected: number;
  missing: Array<ServerErrorExpectation & { observed: number }>;
};
