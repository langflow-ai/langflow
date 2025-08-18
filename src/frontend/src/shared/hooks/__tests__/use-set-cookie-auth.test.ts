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

import { setAuthCookie } from "@/utils/utils";

describe("setAuthCookie", () => {
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

  it("should set a cookie with correct options", () => {
    const tokenName = "access_token_lf";
    const tokenValue = "test-access-token";

    setAuthCookie(mockCookies, tokenName, tokenValue);

    expect(mockCookies.set).toHaveBeenCalledWith(tokenName, tokenValue, {
      path: "/",
      secure: true,
      sameSite: "strict",
    });
  });

  it("should handle different token types", () => {
    const testCases = [
      { tokenName: "access_token_lf", value: "access-123" },
      { tokenName: "refresh_token_lf", value: "refresh-456" },
      { tokenName: "apikey_tkn_lflw", value: "api-789" },
    ];

    testCases.forEach(({ tokenName, value }) => {
      setAuthCookie(mockCookies, tokenName, value);

      expect(mockCookies.set).toHaveBeenCalledWith(tokenName, value, {
        path: "/",
        secure: true,
        sameSite: "strict",
      });
    });
  });

  it("should handle empty string values", () => {
    const tokenName = "test_token";
    const tokenValue = "";

    setAuthCookie(mockCookies, tokenName, tokenValue);

    expect(mockCookies.set).toHaveBeenCalledWith(tokenName, tokenValue, {
      path: "/",
      secure: true,
      sameSite: "strict",
    });
  });

  it("should use correct cookie options for security", () => {
    setAuthCookie(mockCookies, "test_token", "test_value");

    const cookieOptions = mockCookies.set.mock.calls[0][2];

    expect(cookieOptions).toEqual({
      path: "/",
      secure: true,
      sameSite: "strict",
    });

    // Ensure httpOnly is NOT set (removed from utils.ts)
    expect(cookieOptions).not.toHaveProperty("httpOnly");
  });

  it("should handle special characters in token values", () => {
    const tokenName = "test_token";
    const tokenValue = "token-with-special-chars_@#$%";

    setAuthCookie(mockCookies, tokenName, tokenValue);

    expect(mockCookies.set).toHaveBeenCalledWith(tokenName, tokenValue, {
      path: "/",
      secure: true,
      sameSite: "strict",
    });
  });
});
