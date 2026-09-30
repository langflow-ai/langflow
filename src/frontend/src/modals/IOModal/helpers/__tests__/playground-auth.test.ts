import { isAuthenticatedPlayground } from "../playground-auth";

// Mock the stores
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(),
  },
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: {
    getState: jest.fn(),
  },
}));

import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";

const mockFlowStore = useFlowStore as unknown as {
  getState: jest.Mock;
};
const mockAuthStore = useAuthStore as unknown as {
  getState: jest.Mock;
};

describe("isAuthenticatedPlayground", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should_return_true_when_playground_authenticated_not_autologin_and_has_user_data", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: true,
      autoLogin: false,
      userData: { id: "user-123" },
    });

    expect(isAuthenticatedPlayground()).toBe(true);
  });

  it("should_return_false_when_not_playground_page", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: true,
      autoLogin: false,
      userData: { id: "user-123" },
    });

    expect(isAuthenticatedPlayground()).toBe(false);
  });

  it("should_return_false_when_not_authenticated", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: false,
      autoLogin: false,
      userData: null,
    });

    expect(isAuthenticatedPlayground()).toBe(false);
  });

  it("should_return_false_when_autologin_is_true", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: true,
      autoLogin: true,
      userData: { id: "user-123" },
    });

    expect(isAuthenticatedPlayground()).toBe(false);
  });

  it("should_return_false_when_user_data_not_loaded_yet", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: true,
      autoLogin: false,
      userData: null,
    });

    // userData null means user data hasn't loaded yet
    // Falls back to anonymous mode to avoid UUID mismatch
    expect(isAuthenticatedPlayground()).toBe(false);
  });

  it("should_return_false_when_autologin_is_null_to_avoid_race_condition", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: true,
      autoLogin: null,
      userData: { id: "user-123" },
    });

    // autoLogin null means query hasn't resolved yet.
    // Must return false to avoid UUID mismatch race condition.
    expect(isAuthenticatedPlayground()).toBe(false);
  });

  it("should_return_false_when_all_conditions_are_false", () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockAuthStore.getState.mockReturnValue({
      isAuthenticated: false,
      autoLogin: true,
      userData: null,
    });

    expect(isAuthenticatedPlayground()).toBe(false);
  });
});
