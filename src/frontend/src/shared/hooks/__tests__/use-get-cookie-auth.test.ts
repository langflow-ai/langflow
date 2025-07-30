import { Cookies } from "react-cookie";
import useGetCookieAuth from "../use-get-cookie-auth";

// Mock react-cookie
jest.mock("react-cookie");

describe("useGetCookieAuth", () => {
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

  it("should return the cookie value when cookie exists", () => {
    const mockTokenValue = "test-access-token";
    mockCookies.get.mockReturnValue(mockTokenValue);

    const result = useGetCookieAuth("access_token");

    expect(mockCookies.get).toHaveBeenCalledWith("access_token");
    expect(result).toBe(mockTokenValue);
  });

  it("should return undefined when cookie does not exist", () => {
    mockCookies.get.mockReturnValue(undefined);

    const result = useGetCookieAuth("nonexistent_token");

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

      const result = useGetCookieAuth(tokenName);

      expect(mockCookies.get).toHaveBeenCalledWith(tokenName);
      expect(result).toBe(value);
    });
  });

  it("should handle empty string token names", () => {
    const result = useGetCookieAuth("");

    expect(mockCookies.get).toHaveBeenCalledWith("");
  });

  it("should handle null values from cookies", () => {
    mockCookies.get.mockReturnValue(null);

    const result = useGetCookieAuth("test_token");

    expect(mockCookies.get).toHaveBeenCalledWith("test_token");
    expect(result).toBeNull();
  });
});
