import { Cookies } from "react-cookie";
import useSetCookieAuth from "../use-set-cookie-auth";

// Mock react-cookie
jest.mock("react-cookie");

describe("useSetCookieAuth", () => {
  let mockCookies: jest.Mocked<Cookies>;

  beforeEach(() => {
    mockCookies = {
      get: jest.fn(),
      set: jest.fn(),
      remove: jest.fn(),
    } as any;
    (Cookies as jest.MockedClass<typeof Cookies>).mockImplementation(
      () => mockCookies,
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("should set a cookie with correct options", () => {
    const tokenName = "access_token_lf";
    const tokenValue = "test-access-token";

    useSetCookieAuth(tokenName, tokenValue);

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
      useSetCookieAuth(tokenName, value);

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

    useSetCookieAuth(tokenName, tokenValue);

    expect(mockCookies.set).toHaveBeenCalledWith(tokenName, tokenValue, {
      path: "/",
      secure: true,
      sameSite: "strict",
    });
  });

  it("should use correct cookie options for security", () => {
    useSetCookieAuth("test_token", "test_value");

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

    useSetCookieAuth(tokenName, tokenValue);

    expect(mockCookies.set).toHaveBeenCalledWith(tokenName, tokenValue, {
      path: "/",
      secure: true,
      sameSite: "strict",
    });
  });
});
