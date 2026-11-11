import {
  focusManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { useGetAuthSession } from "../use-get-auth-session";

const mockGet = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockGet(...args) },
}));

const maintenanceError = {
  isAxiosError: true,
  response: {
    status: 503,
    data: { detail: { code: "external_auth_maintenance" } },
    headers: { "retry-after": "1" },
  },
};

let client: QueryClient;

beforeEach(() => {
  mockGet.mockReset();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
});

afterEach(() => {
  client.clear();
  focusManager.setFocused(undefined);
});

function showSession() {
  return renderHook(() => useGetAuthSession(), {
    wrapper: ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client }, children),
  });
}

it("preserves the temporary maintenance refusal instead of returning signed out", async () => {
  mockGet.mockRejectedValue(maintenanceError);
  const { result } = showSession();

  await waitFor(() =>
    expect(result.current.isExternalAuthenticationPaused).toBe(true),
  );
  expect(result.current.data).not.toHaveProperty("authenticated");
});

it("revalidates the existing session when maintenance ends", async () => {
  focusManager.setFocused(true);
  const session = {
    authenticated: true,
    user: {
      id: "viewer",
      username: "viewer",
      is_active: true,
      is_superuser: false,
    },
  };
  mockGet
    .mockRejectedValueOnce(maintenanceError)
    .mockResolvedValue({ data: session });
  const { result } = showSession();
  await waitFor(() =>
    expect(result.current.isExternalAuthenticationPaused).toBe(true),
  );

  await waitFor(() => expect(result.current.data).toEqual(session), {
    timeout: 3000,
  });
  expect(result.current.error).toBeNull();
  expect(mockGet).toHaveBeenCalledTimes(2);
});

it("still reports invalid credentials as signed out", async () => {
  mockGet.mockRejectedValue({ isAxiosError: true, response: { status: 401 } });
  const { result } = showSession();

  await waitFor(() =>
    expect(result.current.data).toEqual({ authenticated: false }),
  );
});

it("keeps maintenance visible through a pending retry until the session is definitive", async () => {
  focusManager.setFocused(true);
  const session = {
    authenticated: true,
    user: {
      id: "viewer",
      username: "viewer",
      is_active: true,
      is_superuser: false,
    },
  };
  let finishRetry!: (response: { data: typeof session }) => void;
  const retry = new Promise<{ data: typeof session }>((resolve) => {
    finishRetry = resolve;
  });
  mockGet.mockRejectedValueOnce(maintenanceError).mockReturnValueOnce(retry);
  const { result } = showSession();
  await waitFor(() =>
    expect(result.current.isExternalAuthenticationPaused).toBe(true),
  );
  await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2), {
    timeout: 3000,
  });
  await waitFor(() => expect(result.current.isFetching).toBe(true));

  expect(result.current.error).toBeNull();
  expect(result.current.isExternalAuthenticationPaused).toBe(true);

  finishRetry({ data: session });
  await waitFor(() => expect(result.current.data).toEqual(session));
  expect(result.current.isExternalAuthenticationPaused).toBe(false);
});

it.each([
  ["network", { isAxiosError: true, request: {} }],
  ["server", { isAxiosError: true, response: { status: 503 } }],
])(
  "keeps retrying through a %s failure after maintenance",
  async (_name, transientError) => {
    focusManager.setFocused(true);
    const session = { authenticated: false };
    mockGet
      .mockRejectedValueOnce(maintenanceError)
      .mockRejectedValueOnce(transientError)
      .mockResolvedValue({ data: session });
    const { result } = showSession();
    await waitFor(() =>
      expect(result.current.isExternalAuthenticationPaused).toBe(true),
    );
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2), {
      timeout: 3000,
    });
    await waitFor(() => expect(result.current.isFetching).toBe(false));

    expect(result.current.isExternalAuthenticationPaused).toBe(true);
    expect(result.current.data?.authenticated).not.toBe(false);

    await waitFor(() => expect(result.current.data).toEqual(session), {
      timeout: 3000,
    });
    expect(result.current.isExternalAuthenticationPaused).toBe(false);
    expect(mockGet).toHaveBeenCalledTimes(3);
  },
);

it.each([401, 403])(
  "ends the maintenance pause on a definitive %s rejection",
  async (status) => {
    focusManager.setFocused(true);
    mockGet
      .mockRejectedValueOnce(maintenanceError)
      .mockRejectedValue({ isAxiosError: true, response: { status } });
    const { result } = showSession();
    await waitFor(() =>
      expect(result.current.isExternalAuthenticationPaused).toBe(true),
    );

    await waitFor(
      () => expect(result.current.data).toEqual({ authenticated: false }),
      {
        timeout: 3000,
      },
    );
    expect(result.current.isExternalAuthenticationPaused).toBe(false);
    expect(mockGet).toHaveBeenCalledTimes(2);
  },
);
