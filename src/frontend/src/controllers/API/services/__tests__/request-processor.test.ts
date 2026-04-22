// biome-ignore-all lint/suspicious/noExplicitAny: test mocks
const mockQueryClient = {
  invalidateQueries: jest.fn(),
};

let capturedQueryOptions: any = null;
let capturedMutationOptions: any = null;

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(() => mockQueryClient),
  useQuery: jest.fn((options: any) => {
    capturedQueryOptions = options;
    return { data: undefined, isLoading: false };
  }),
  useMutation: jest.fn((options: any) => {
    capturedMutationOptions = options;
    return { mutate: jest.fn(), mutateAsync: jest.fn() };
  }),
}));

import { UseRequestProcessor } from "../request-processor";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const axiosError = (status: number) => ({ response: { status } });
const networkError = () => new Error("Network Error"); // no `.response`

beforeEach(() => {
  jest.clearAllMocks();
  capturedQueryOptions = null;
  capturedMutationOptions = null;
});

// ---------------------------------------------------------------------------
// Queries: retry policy
// ---------------------------------------------------------------------------

describe("UseRequestProcessor.query retry policy", () => {
  const setup = (options: any = {}) => {
    const { query } = UseRequestProcessor();
    query(["k"], async () => ({}), options);
    return capturedQueryOptions;
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

  it("retries up to 5 times on network errors with no response", () => {
    const { retry } = setup();
    expect(retry(0, networkError())).toBe(true);
    expect(retry(4, networkError())).toBe(true);
    expect(retry(5, networkError())).toBe(false);
  });

  it("treats non-numeric / missing status as transient (retries)", () => {
    const { retry } = setup();
    expect(retry(0, undefined)).toBe(true);
    expect(retry(0, {})).toBe(true);
    expect(retry(0, { response: {} })).toBe(true);
  });

  it("allows per-call options.retry to override the default", () => {
    const { retry } = setup({ retry: false });
    expect(retry).toBe(false);
  });

  it("allows per-call options.retry as a number to override the default", () => {
    const { retry } = setup({ retry: 10 });
    expect(retry).toBe(10);
  });
});

// ---------------------------------------------------------------------------
// Mutations: retry policy
// ---------------------------------------------------------------------------

describe("UseRequestProcessor.mutate retry policy", () => {
  const setup = (options: any = {}) => {
    const { mutate } = UseRequestProcessor();
    mutate(["k"], async () => ({}), options);
    return capturedMutationOptions;
  };

  it("does not retry on any 4xx response", () => {
    const { retry } = setup();
    for (const status of [400, 401, 403, 404, 409, 422, 429, 499]) {
      expect(retry(0, axiosError(status))).toBe(false);
    }
  });

  it("retries up to 3 times on 5xx responses", () => {
    const { retry } = setup();
    expect(retry(0, axiosError(500))).toBe(true);
    expect(retry(2, axiosError(500))).toBe(true);
    expect(retry(3, axiosError(500))).toBe(false);
  });

  it("retries up to 3 times on network errors", () => {
    const { retry } = setup();
    expect(retry(0, networkError())).toBe(true);
    expect(retry(2, networkError())).toBe(true);
    expect(retry(3, networkError())).toBe(false);
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
});

// ---------------------------------------------------------------------------
// retryDelay: exponential backoff capped at 30s
// ---------------------------------------------------------------------------

describe("UseRequestProcessor retryDelay", () => {
  it("uses exponential backoff capped at 30s for queries", () => {
    const { query } = UseRequestProcessor();
    query(["k"], async () => ({}));
    const { retryDelay } = capturedQueryOptions;
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
    const { retryDelay } = capturedMutationOptions;
    expect(retryDelay(0)).toBe(1000);
    expect(retryDelay(1)).toBe(2000);
    expect(retryDelay(2)).toBe(4000);
    expect(retryDelay(10)).toBe(30000);
  });
});
