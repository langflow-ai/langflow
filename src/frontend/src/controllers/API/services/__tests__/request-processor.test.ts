// biome-ignore-all lint/suspicious/noExplicitAny: test mocks
const mockQueryClient = {
  invalidateQueries: jest.fn(),
};

let mockCapturedQueryOptions: any = null;
let mockCapturedMutationOptions: any = null;

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(() => mockQueryClient),
  useQuery: jest.fn((options: any) => {
    mockCapturedQueryOptions = options;
    return { data: undefined, isLoading: false };
  }),
  useMutation: jest.fn((options: any) => {
    mockCapturedMutationOptions = options;
    return { mutate: jest.fn(), mutateAsync: jest.fn() };
  }),
}));

import { CanceledError } from "axios";
import {
  getRetryAfterMs,
  isRetryableServerError,
  UseRequestProcessor,
  withTransientErrorRetry,
} from "../request-processor";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// `axios.isAxiosError` checks `error.isAxiosError === true`, so fixtures must
// set that flag to be classified as HTTP errors rather than transient.
const axiosError = (status: number, headers: Record<string, string> = {}) => ({
  isAxiosError: true,
  response: { status, headers },
});
const axiosNetworkError = () => ({
  isAxiosError: true,
  request: {},
  response: undefined,
});
const nonAxiosError = () => new Error("Network Error");

beforeEach(() => {
  jest.clearAllMocks();
  mockCapturedQueryOptions = null;
  mockCapturedMutationOptions = null;
});

// ---------------------------------------------------------------------------
// Queries: retry policy
// ---------------------------------------------------------------------------

describe("UseRequestProcessor.query retry policy", () => {
  const setup = (options: any = {}) => {
    const { query } = UseRequestProcessor();
    query(["k"], async () => ({}), options);
    if (mockCapturedQueryOptions == null) {
      throw new Error("query was not called by UseRequestProcessor");
    }
    return mockCapturedQueryOptions;
  };

  it("does not retry on any 4xx response", () => {
    const { retry } = setup();
    for (const status of [400, 401, 403, 404, 409, 422, 429, 499]) {
      expect(retry(0, axiosError(status))).toBe(false);
    }
  });

  it("retries up to 5 times on 5xx responses", () => {
    const { retry } = setup();
    for (const status of [500, 502, 503, 504]) {
      expect(retry(0, axiosError(status))).toBe(true);
      expect(retry(4, axiosError(status))).toBe(true);
      expect(retry(5, axiosError(status))).toBe(false);
    }
  });

  it("retries up to 5 times on axios errors with no response", () => {
    const { retry } = setup();
    expect(retry(0, axiosNetworkError())).toBe(true);
    expect(retry(4, axiosNetworkError())).toBe(true);
    expect(retry(5, axiosNetworkError())).toBe(false);
  });

  it("treats non-axios / unknown errors as transient (retries)", () => {
    const { retry } = setup();
    expect(retry(0, undefined)).toBe(true);
    expect(retry(0, {})).toBe(true);
    expect(retry(0, { response: {} })).toBe(true);
    expect(retry(0, nonAxiosError())).toBe(true);
  });

  it("allows per-call options.retry to override the default", () => {
    const { retry } = setup({ retry: false });
    expect(retry).toBe(false);
  });

  it("allows per-call options.retry as a number to override the default", () => {
    const { retry } = setup({ retry: 10 });
    expect(retry).toBe(10);
  });

  it("allows per-call options.retryDelay to override the default", () => {
    const customDelay = jest.fn(() => 42);
    const { retryDelay } = setup({ retryDelay: customDelay });
    expect(retryDelay).toBe(customDelay);
  });
});

// ---------------------------------------------------------------------------
// Mutations: retry policy
//
// Mutation retries run inside the mutation function (withTransientErrorRetry)
// rather than through react-query's `retry` option, because react-query's
// retryer pauses between attempts while the document is hidden or the
// browser reports offline — a failing mutation could sit paused forever
// without settling, so the caller's onError (and its toast) never fired for
// a 5xx. The react-query-level `retry` is therefore `false` by default and
// the wrapped mutationFn owns the transient-error replay.
// ---------------------------------------------------------------------------

describe("UseRequestProcessor.mutate retry policy", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  const setup = (options: any = {}, fn: any = async () => ({})) => {
    const { mutate } = UseRequestProcessor();
    mutate(["k"], fn, options);
    if (mockCapturedMutationOptions == null) {
      throw new Error("mutate was not called by UseRequestProcessor");
    }
    return mockCapturedMutationOptions;
  };

  it("disables react-query-level retries by default (in-band retry instead)", () => {
    const { retry } = setup();
    expect(retry).toBe(false);
  });

  it("wraps the default mutationFn with in-band transient retry", async () => {
    const inner = jest
      .fn()
      .mockRejectedValueOnce(axiosError(503, { "retry-after": "0" }))
      .mockResolvedValue("ok");
    const { mutationFn } = setup({}, inner);
    expect(mutationFn).not.toBe(inner);
    await expect(mutationFn(undefined)).resolves.toBe("ok");
    expect(inner).toHaveBeenCalledTimes(2);
  });

  it("does not wrap the mutationFn when the caller sets its own retry", () => {
    const inner = jest.fn();
    const { mutationFn } = setup({ retry: 2 }, inner);
    expect(mutationFn).toBe(inner);
  });

  it("respects options.retry === false", () => {
    const { retry } = setup({ retry: false });
    expect(retry).toBe(false);
  });

  it("respects options.retry === 0 (nullish coalescing, not falsy)", () => {
    const { retry } = setup({ retry: 0 });
    expect(retry).toBe(0);
  });

  it("respects a custom options.retry callback", () => {
    const customRetry = jest.fn(() => true);
    const { retry } = setup({ retry: customRetry });
    expect(retry).toBe(customRetry);
  });

  it("uses a custom options.retryDelay for in-band retries", async () => {
    jest.useFakeTimers();
    const error = axiosError(503, { "retry-after": "7" });
    const inner = jest
      .fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValue("ok");
    const customDelay = jest.fn(() => 42);
    const { mutationFn } = setup({ retryDelay: customDelay }, inner);
    const promise = mutationFn(undefined);

    await jest.advanceTimersByTimeAsync(0);
    expect(inner).toHaveBeenCalledTimes(1);
    expect(customDelay).toHaveBeenCalledWith(0, error);
    await jest.advanceTimersByTimeAsync(41);
    expect(inner).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(1);
    await expect(promise).resolves.toBe("ok");
    expect(inner).toHaveBeenCalledTimes(2);
  });
});

// ---------------------------------------------------------------------------
// retryDelay: exponential backoff capped at 30s
// ---------------------------------------------------------------------------

describe("UseRequestProcessor retryDelay", () => {
  it("uses exponential backoff capped at 30s for queries", () => {
    const { query } = UseRequestProcessor();
    query(["k"], async () => ({}));
    const { retryDelay } = mockCapturedQueryOptions;
    expect(retryDelay(0)).toBe(1000);
    expect(retryDelay(1)).toBe(2000);
    expect(retryDelay(2)).toBe(4000);
    expect(retryDelay(3)).toBe(8000);
    expect(retryDelay(4)).toBe(16000);
    expect(retryDelay(5)).toBe(30000);
    expect(retryDelay(10)).toBe(30000);
  });

  it("uses exponential backoff capped at 30s for mutations", () => {
    const { mutate } = UseRequestProcessor();
    mutate(["k"], async () => ({}));
    const { retryDelay } = mockCapturedMutationOptions;
    expect(retryDelay(0)).toBe(1000);
    expect(retryDelay(1)).toBe(2000);
    expect(retryDelay(2)).toBe(4000);
    expect(retryDelay(10)).toBe(30000);
  });
});

// ---------------------------------------------------------------------------
// isRetryableServerError
// ---------------------------------------------------------------------------

describe("isRetryableServerError", () => {
  it("retries 5xx responses", () => {
    expect(isRetryableServerError(axiosError(500))).toBe(true);
    expect(isRetryableServerError(axiosError(503))).toBe(true);
  });

  it("does not retry 4xx responses", () => {
    expect(isRetryableServerError(axiosError(401))).toBe(false);
    expect(isRetryableServerError(axiosError(422))).toBe(false);
  });

  it("retries axios errors that got no response", () => {
    expect(isRetryableServerError(axiosNetworkError())).toBe(true);
  });

  it("does not retry cancellations or non-axios errors", () => {
    expect(isRetryableServerError(new CanceledError("canceled"))).toBe(false);
    expect(isRetryableServerError(nonAxiosError())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// getRetryAfterMs
// ---------------------------------------------------------------------------

describe("getRetryAfterMs", () => {
  it("parses delta-seconds", () => {
    expect(getRetryAfterMs(axiosError(503, { "retry-after": "1" }))).toBe(1000);
  });

  it("caps the delay at 30 seconds", () => {
    expect(getRetryAfterMs(axiosError(503, { "retry-after": "3600" }))).toBe(
      30000,
    );
  });

  it("parses HTTP-dates relative to now", () => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    const header = new Date("2026-01-01T00:00:05Z").toUTCString();
    expect(getRetryAfterMs(axiosError(503, { "retry-after": header }))).toBe(
      5000,
    );
    jest.useRealTimers();
  });

  it("returns undefined when the header is missing or unparseable", () => {
    expect(getRetryAfterMs(axiosError(503))).toBeUndefined();
    expect(
      getRetryAfterMs(axiosError(503, { "retry-after": "soon" })),
    ).toBeUndefined();
    expect(getRetryAfterMs(nonAxiosError())).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// withTransientErrorRetry
// ---------------------------------------------------------------------------

describe("withTransientErrorRetry", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  it("resolves without retrying on success", async () => {
    const fn = jest.fn().mockResolvedValue("ok");
    await expect(withTransientErrorRetry(fn)(undefined)).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("settles immediately on a 4xx", async () => {
    const error = axiosError(401);
    const fn = jest.fn().mockRejectedValue(error);
    await expect(withTransientErrorRetry(fn)(undefined)).rejects.toBe(error);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("retries a 5xx up to the budget, then rejects with the last error", async () => {
    const error = axiosError(503, { "retry-after": "0" });
    const fn = jest.fn().mockRejectedValue(error);
    await expect(withTransientErrorRetry(fn)(undefined)).rejects.toBe(error);
    expect(fn).toHaveBeenCalledTimes(4);
  });

  it("recovers when a retry succeeds", async () => {
    const fn = jest
      .fn()
      .mockRejectedValueOnce(axiosError(503, { "retry-after": "0" }))
      .mockResolvedValue("ok");
    await expect(withTransientErrorRetry(fn)(undefined)).resolves.toBe("ok");
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it("honors the server's Retry-After delay", async () => {
    jest.useFakeTimers();
    const error = axiosError(503, { "retry-after": "7" });
    const fn = jest.fn().mockRejectedValue(error);
    const promise = withTransientErrorRetry(
      fn,
      1,
    )(undefined).catch((e: unknown) => e);

    await jest.advanceTimersByTimeAsync(0);
    expect(fn).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(6999);
    expect(fn).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(1);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(await promise).toBe(error);
  });

  it("falls back to exponential backoff without Retry-After", async () => {
    jest.useFakeTimers();
    const error = axiosError(503);
    const fn = jest.fn().mockRejectedValue(error);
    const promise = withTransientErrorRetry(fn)(undefined).catch(
      (e: unknown) => e,
    );

    await jest.advanceTimersByTimeAsync(0);
    expect(fn).toHaveBeenCalledTimes(1);
    await jest.advanceTimersByTimeAsync(1000);
    expect(fn).toHaveBeenCalledTimes(2);
    await jest.advanceTimersByTimeAsync(2000);
    expect(fn).toHaveBeenCalledTimes(3);
    await jest.advanceTimersByTimeAsync(4000);
    expect(fn).toHaveBeenCalledTimes(4);
    expect(await promise).toBe(error);
  });

  it("does not retry non-axios errors", async () => {
    const error = nonAxiosError();
    const fn = jest.fn().mockRejectedValue(error);
    await expect(withTransientErrorRetry(fn)(undefined)).rejects.toBe(error);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("passes all arguments through to the wrapped function", async () => {
    const fn = jest.fn().mockResolvedValue("ok");
    const context = { client: {}, meta: undefined };
    await withTransientErrorRetry(fn)({ id: "flow" }, context);
    expect(fn).toHaveBeenCalledWith({ id: "flow" }, context);
  });
});
