import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { AuthContext } from "@/contexts/authContext";

const mockUseGetTagsQuery = jest.fn();
const mockRefreshStars = jest.fn();
const mockRefreshDiscordCount = jest.fn();
const mockRefetchExamples = jest.fn();

jest.mock("react-router-dom", () => ({
  Outlet: () => <div data-testid="outlet" />,
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useGetAuthSession: () => ({ data: undefined, isFetched: true }),
  useGetAutoLogin: () => ({ isFetched: true }),
}));

jest.mock("@/controllers/API/queries/config/use-get-config", () => ({
  useGetConfig: () => ({ isFetched: true }),
}));

jest.mock("@/controllers/API/queries/flows/use-get-basic-examples", () => ({
  useGetBasicExamplesQuery: () => ({
    isFetched: true,
    refetch: mockRefetchExamples,
  }),
}));

jest.mock("@/controllers/API/queries/folders/use-get-folders", () => ({
  useGetFoldersQuery: jest.fn(),
}));

jest.mock("@/controllers/API/queries/store", () => ({
  useGetTagsQuery: (options: unknown) => mockUseGetTagsQuery(options),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: jest.fn(),
}));

jest.mock("@/controllers/API/queries/version", () => ({
  useGetVersionQuery: jest.fn(),
}));

jest.mock("@/customization/hooks/use-custom-primary-loading", () => ({
  useCustomPrimaryLoading: () => ({ isFetched: true }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      autoLogin: true,
      isAuthenticated: true,
      setIsAuthenticated: jest.fn(),
      setIsAdmin: jest.fn(),
    }),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({
      refreshStars: mockRefreshStars,
      refreshDiscordCount: mockRefreshDiscordCount,
    }),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ isLoading: false }),
}));

jest.mock("@/customization/components/custom-loading-page", () => ({
  CustomLoadingPage: () => <div data-testid="custom-loading" />,
}));

jest.mock("../../LoadingPage", () => ({
  LoadingPage: () => <div data-testid="loading" />,
}));

import { AppInitPage } from "../index";

const AuthWrapper = ({ children }: { children: ReactNode }) => (
  <AuthContext.Provider
    value={
      {
        accessToken: null,
        apiKey: null,
        authenticationErrorCount: 0,
        clearAuthSession: jest.fn(),
        getUser: jest.fn(),
        login: jest.fn(),
        setApiKey: jest.fn(),
        setUserData: jest.fn(),
        storeApiKey: jest.fn(),
        userData: null,
      } as React.ContextType<typeof AuthContext>
    }
  >
    {children}
  </AuthContext.Provider>
);

describe("AppInitPage Store bootstrap", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("keeps the legacy Store tags query disabled in the OSS frontend", () => {
    render(<AppInitPage />, { wrapper: AuthWrapper });

    expect(mockUseGetTagsQuery).toHaveBeenCalledWith({ enabled: false });
  });
});
