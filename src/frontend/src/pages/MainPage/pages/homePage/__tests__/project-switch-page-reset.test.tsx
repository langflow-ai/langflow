import { fireEvent, render, screen } from "@testing-library/react";
import HomePage from "..";

const mockFolders = [
  { id: "alpha-id", name: "Alpha", description: "", parent_id: "" },
  { id: "beta-id", name: "Beta", description: "", parent_id: "" },
];
const mockFlows = [];
const mockNavigate = jest.fn();
let mockFolderId = "alpha-id";
const mockUseGetFolderQuery = jest.fn();

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-router-dom", () => ({
  useLocation: () => ({ state: undefined }),
  useParams: () => ({ folderId: mockFolderId }),
}));
jest.mock(
  "@/components/common/paginatorComponent",
  () =>
    ({ pageIndex, pageSize, paginate }) => (
      <button
        type="button"
        data-testid="next-page"
        onClick={() => paginate(pageIndex + 1, pageSize)}
      >
        {pageIndex}
      </button>
    ),
);
jest.mock("@/components/core/cardsWrapComponent", () => ({ children }) => (
  <>{children}</>
));
jest.mock(
  "@/components/core/flowBuilderWelcome/hooks/use-start-new-flow",
  () => ({ useStartNewFlow: () => jest.fn() }),
);
jest.mock("@/constants/constants", () => ({ IS_MAC: false }));
jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }) => <>{children}</>,
}));
jest.mock("@/controllers/API/queries/folders/use-get-folder", () => ({
  useGetFolderQuery: (params) => mockUseGetFolderQuery(params),
}));
jest.mock("@/customization/components/custom-banner", () => ({
  CustomBanner: () => null,
}));
jest.mock("@/customization/components/custom-McpServerTab", () => ({
  CustomMcpServerTab: () => null,
}));
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_DATASTAX_LANGFLOW: false,
  ENABLE_MCP: true,
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector) => selector({ flows: mockFlows }),
}));
jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector) =>
    selector({ myCollectionId: "alpha-id", folders: mockFolders }),
}));
jest.mock("@/pages/MainPage/components/header", () => () => null);
jest.mock("@/pages/MainPage/components/list", () => () => null);
jest.mock("@/pages/MainPage/components/listSkeleton", () => () => null);
jest.mock("@/pages/MainPage/components/modalsComponent", () => () => null);
jest.mock("@/pages/MainPage/hooks/use-on-file-drop", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));
jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/deployments-page",
  () => () => null,
);
jest.mock("@/pages/MainPage/pages/emptyFolder", () => () => null);

const lastRequest = () => mockUseGetFolderQuery.mock.lastCall?.[0];

describe("HomePage paging across projects", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFolderId = "alpha-id";
    // One result per request, as the query cache gives: a new `items` array on
    // every render would re-run the page's selection effect forever.
    const results = new Map();
    mockUseGetFolderQuery.mockImplementation((params) => {
      const key = `${params.id}:${params.page}`;
      if (!results.has(key)) {
        results.set(key, {
          data: {
            folder: mockFolders[0],
            flows: {
              items: [],
              page: params.page,
              size: 12,
              total: 30,
              pages: 3,
            },
          },
          isLoading: false,
        });
      }
      return results.get(key);
    });
  });

  it("opens the next project at its first page, and its next page still works", () => {
    const { rerender } = render(<HomePage type="flows" />);
    fireEvent.click(screen.getByTestId("next-page"));
    expect(lastRequest()).toMatchObject({ id: "alpha-id", page: 2 });

    mockFolderId = "beta-id";
    rerender(<HomePage type="flows" />);
    expect(lastRequest()).toMatchObject({ id: "beta-id", page: 1 });

    fireEvent.click(screen.getByTestId("next-page"));
    expect(lastRequest()).toMatchObject({ id: "beta-id", page: 2 });
  });
});
