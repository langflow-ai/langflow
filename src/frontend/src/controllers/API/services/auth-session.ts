import { api } from "../api";
import { getURL } from "../helpers/constants";

export interface RefreshAccessTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

let sessionQueue: Promise<void> = Promise.resolve();
let pendingRefresh: Promise<RefreshAccessTokenResponse> | undefined;

export function withAuthSessionLock<T>(request: () => Promise<T>): Promise<T> {
  const run = async (): Promise<T> => {
    // Hold the origin-wide lock until response cookies have been applied.
    if (navigator.locks?.request) {
      const endpoint = new URL(
        api.getUri({ url: getURL("REFRESH") }),
        window.location.href,
      ).href;
      return navigator.locks.request(
        `langflow-auth-session:${endpoint}`,
        request,
      );
    }
    return request();
  };

  const operation = sessionQueue.then(run);
  sessionQueue = operation.then(
    () => undefined,
    () => undefined,
  );
  return operation;
}

export function refreshAccessToken(): Promise<RefreshAccessTokenResponse> {
  if (!pendingRefresh) {
    pendingRefresh = withAuthSessionLock(async () => {
      const response = await api.post<RefreshAccessTokenResponse>(
        getURL("REFRESH"),
      );
      return response.data;
    }).finally(() => {
      pendingRefresh = undefined;
    });
  }
  return pendingRefresh;
}
