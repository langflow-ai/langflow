import { Cookies } from "react-cookie";

// Mock all complex dependencies to avoid import issues
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({})),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: {
    getState: () => ({ refreshStars: jest.fn() }),
    setState: jest.fn(),
    subscribe: jest.fn(),
    destroy: jest.fn(),
  },
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({})),
}));

jest.mock("@/utils/styleUtils", () => ({}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent/components/tableAutoCellRender",
  () => () => null,
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/tableComponent/components/tableDropdownCellEditor",
  () => () => null,
);

// Jest can't find this module to mock it, let's skip this mock

// Jest can't find this module either

// Mock react-cookie
jest.mock("react-cookie");

import { getAuthCookie } from "@/utils/utils";

describe("getAuthCookie", () => {
  let mockCookies: jest.Mocked<Cookies>;

  beforeEach(() => {
    mockCookies = {
      get: jest.fn(),
      set: jest.fn(),
      remove: jest.fn(),
    } as any;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should return the cookie value when cookie exists", () => {
    const mockTokenValue = "test-access-token";
    mockCookies.get.mockReturnValue(mockTokenValue);

    const result = getAuthCookie(mockCookies, "access_token");

    expect(mockCookies.get).toHaveBeenCalledWith("access_token");
    expect(result).toBe(mockTokenValue);
  });

  it("should return undefined when cookie does not exist", () => {
    mockCookies.get.mockReturnValue(undefined);

    const result = getAuthCookie(mockCookies, "nonexistent_token");

    expect(mockCookies.get).toHaveBeenCalledWith("nonexistent_token");
    expect(result).toBeUndefined();
  });

  it("should handle different token names", () => {
    const testCases = [
      { tokenName: "access_token_lf", value: "access-123" },
      { tokenName: "refresh_token_lf", value: "refresh-456" },
      { tokenName: "apikey_tkn_lflw", value: "api-789" },
    ];

    testCases.forEach(({ tokenName, value }) => {
      mockCookies.get.mockReturnValue(value);

      const result = getAuthCookie(mockCookies, tokenName);

      expect(mockCookies.get).toHaveBeenCalledWith(tokenName);
      expect(result).toBe(value);
    });
  });

  it("should handle empty string token names", () => {
    const _result = getAuthCookie(mockCookies, "");

    expect(mockCookies.get).toHaveBeenCalledWith("");
  });

  it("should handle null values from cookies", () => {
    mockCookies.get.mockReturnValue(null);

    const result = getAuthCookie(mockCookies, "test_token");

    expect(mockCookies.get).toHaveBeenCalledWith("test_token");
    expect(result).toBeNull();
  });
});
