// biome-ignore-all lint/suspicious/noExplicitAny: test doubles
// Integration tests against the real @tanstack/react-query, covering the
// regression where a mutation that received a 5xx never settled: react-query's
// retryer pauses between retry attempts while the document is hidden (or the
// browser reports offline), so neither the retries nor the caller's onError
// ever ran and the failure was silently discarded.
import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { AxiosError } from "axios";
import React from "react";
import { UseRequestProcessor } from "../request-processor";

const makeResponseError = (
  status: number,
  headers: Record<string, string> = {},
) =>
  new AxiosError(
    `Request failed with status code ${status}`,
    status >= 500 ? AxiosError.ERR_BAD_RESPONSE : AxiosError.ERR_BAD_REQUEST,
    undefined as any,
    {},
    {
      status,
      statusText: "",
      headers,
      config: {},
      data: { detail: "The database is busy. Please retry the request." },
    } as any,
  );

const createWrapper = () => {
  const queryClient = new QueryClient();
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("UseRequestProcessor mutations (real react-query)", () => {
  afterEach(() => {
    focusManager.setFocused(undefined);
  });

  it("settles a persistent 5xx and fires onError even while the document is hidden", async () => {
    // Emulates the hidden tab that made react-query's own retryer pause
    // forever between attempts (the reported silent-5xx bug).
    focusManager.setFocused(false);

    const error = makeResponseError(503, { "retry-after": "0" });
    const mutationFn = jest.fn().mockRejectedValue(error);
    const onError = jest.fn();

    const { result } = renderHook(
      () => {
        const { mutate } = UseRequestProcessor();
        return mutate(["request-processor-test"], mutationFn);
      },
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.mutate(undefined, { onError });
    });

    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1));
    expect(onError.mock.calls[0][0]).toBe(error);
    expect(mutationFn).toHaveBeenCalledTimes(4);
    expect(result.current.isError).toBe(true);
  });

  it("settles a 4xx immediately with a single attempt", async () => {
    const error = makeResponseError(401);
    const mutationFn = jest.fn().mockRejectedValue(error);
    const onError = jest.fn();

    const { result } = renderHook(
      () => {
        const { mutate } = UseRequestProcessor();
        return mutate(["request-processor-test"], mutationFn);
      },
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.mutate(undefined, { onError });
    });

    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1));
    expect(mutationFn).toHaveBeenCalledTimes(1);
  });

  it("passes a caller-supplied retry option through to react-query untouched", async () => {
    const error = makeResponseError(503, { "retry-after": "0" });
    const mutationFn = jest.fn().mockRejectedValue(error);
    const onError = jest.fn();

    const { result } = renderHook(
      () => {
        const { mutate } = UseRequestProcessor();
        return mutate(["request-processor-test"], mutationFn, {
          retry: 2,
          retryDelay: 0,
        });
      },
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.mutate(undefined, { onError });
    });

    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1));
    // 1 initial attempt + 2 react-query retries, no in-band retries on top.
    expect(mutationFn).toHaveBeenCalledTimes(3);
  });

  it("does not retry when the caller disables retries", async () => {
    const error = makeResponseError(503, { "retry-after": "0" });
    const mutationFn = jest.fn().mockRejectedValue(error);
    const onError = jest.fn();

    const { result } = renderHook(
      () => {
        const { mutate } = UseRequestProcessor();
        return mutate(["request-processor-test"], mutationFn, {
          retry: false,
        });
      },
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.mutate(undefined, { onError });
    });

    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1));
    expect(mutationFn).toHaveBeenCalledTimes(1);
  });
});
