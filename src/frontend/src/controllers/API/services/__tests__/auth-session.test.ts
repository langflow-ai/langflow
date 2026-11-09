import { waitFor } from "@testing-library/react";
import type { RefreshAccessTokenResponse } from "../auth-session";

const mockPost = jest.fn();
const mockGetUri = jest.fn(() => "/api/v1/refresh");
jest.mock("../../api", () => ({
  api: { post: mockPost, getUri: mockGetUri },
}));

const response: RefreshAccessTokenResponse = {
  access_token: "access-token",
  refresh_token: "refresh-token",
  token_type: "bearer",
};

function tab() {
  let coordinator!: typeof import("../auth-session");
  jest.isolateModules(() => {
    coordinator = jest.requireActual("../auth-session");
  });
  return coordinator;
}

function installOriginLocks() {
  const queues = new Map<string, Promise<void>>();
  const request = jest.fn((name: string, operation: () => Promise<unknown>) => {
    const pending = (queues.get(name) ?? Promise.resolve()).then(operation);
    queues.set(
      name,
      pending.then(
        () => undefined,
        () => undefined,
      ),
    );
    return pending;
  });
  Object.defineProperty(navigator, "locks", {
    configurable: true,
    value: { request },
  });
  return request;
}

describe("native session request coordination", () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockGetUri.mockClear();
    Object.defineProperty(navigator, "locks", {
      configurable: true,
      value: undefined,
    });
  });

  afterEach(() => {
    Object.defineProperty(navigator, "locks", {
      configurable: true,
      value: undefined,
    });
  });

  it("shares one response across concurrent refresh consumers", async () => {
    const coordinator = tab();
    mockPost.mockResolvedValue({ data: response });

    const first = coordinator.refreshAccessToken();
    const second = coordinator.refreshAccessToken();
    expect(second).toBe(first);
    await expect(Promise.all([first, second])).resolves.toEqual([
      response,
      response,
    ]);

    expect(mockPost).toHaveBeenCalledTimes(1);
  });

  it("releases a failed flight before a later refresh attempt", async () => {
    const coordinator = tab();
    const error = new Error("network unavailable");
    mockPost.mockRejectedValueOnce(error).mockResolvedValue({ data: response });

    const first = coordinator.refreshAccessToken();
    const second = coordinator.refreshAccessToken();
    const failures = await Promise.allSettled([first, second]);
    expect(failures).toEqual([
      { status: "rejected", reason: error },
      { status: "rejected", reason: error },
    ]);
    await expect(coordinator.refreshAccessToken()).resolves.toEqual(response);

    expect(mockPost).toHaveBeenCalledTimes(2);
  });

  it("serializes shared-cookie tabs until the previous response updates cookies", async () => {
    const lock = installOriginLocks();
    const firstTab = tab();
    const secondTab = tab();
    let cookie = "initial";
    let complete!: () => void;
    const firstResponse = new Promise<void>((resolve) => {
      complete = resolve;
    });
    const presented: string[] = [];
    mockPost.mockImplementation(async () => {
      presented.push(cookie);
      if (presented.length === 1) {
        await firstResponse;
        cookie = "rotated";
      }
      return { data: response };
    });

    const first = firstTab.refreshAccessToken();
    const second = secondTab.refreshAccessToken();
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(presented).toEqual(["initial"]);
    complete();
    await Promise.all([first, second]);

    expect(presented).toEqual(["initial", "rotated"]);
    expect(lock).toHaveBeenCalledTimes(2);
    expect(lock.mock.calls[0][0]).toBe(lock.mock.calls[1][0]);
    expect(lock.mock.calls[0][0]).toContain("/api/v1/refresh");
  });

  it("keeps logout behind an in-flight refresh without Web Locks", async () => {
    const coordinator = tab();
    let complete!: (value: { data: RefreshAccessTokenResponse }) => void;
    mockPost.mockReturnValue(
      new Promise<{ data: RefreshAccessTokenResponse }>((resolve) => {
        complete = resolve;
      }),
    );
    const logout = jest.fn().mockResolvedValue(undefined);

    const refreshing = coordinator.refreshAccessToken();
    const loggingOut = coordinator.withAuthSessionLock(logout);
    await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(1));
    expect(logout).not.toHaveBeenCalled();
    complete({ data: response });
    await Promise.all([refreshing, loggingOut]);

    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("releases a rejected session operation before logout", async () => {
    const coordinator = tab();
    mockPost.mockRejectedValue(new Error("connection lost"));
    const logout = jest.fn().mockResolvedValue(undefined);

    const refreshing = coordinator.refreshAccessToken();
    const loggingOut = coordinator.withAuthSessionLock(logout);
    await expect(refreshing).rejects.toThrow("connection lost");
    await loggingOut;

    expect(logout).toHaveBeenCalledTimes(1);
  });
});
