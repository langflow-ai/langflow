import { act, render } from "@testing-library/react";
import HomePage from "..";

const FIRST_PROJECT_ID = "first-project";
const SECOND_PROJECT_ID = "second-project";

const mockFolders = [FIRST_PROJECT_ID, SECOND_PROJECT_ID].map((id) => ({
  id,
  name: id,
  description: "",
  parent_id: "",
  flows: [],
  components: [],
  owner_username: "current-user",
  is_owner: true,
}));
const mockFlows = [];
const mockNavigate = jest.fn();
let mockFolderId: string | undefined = FIRST_PROJECT_ID;
let mockPaginate: ((page: number, size: number) => void) | undefined;
// Results are cached per (project, page) so each render sees a stable
// reference, as React Query would return. A fresh object per render would
// retrigger HomePage effects that depend on the query data.
const mockQueryResults = new Map<string, unknown>();
const mockUseGetFolderQuery = jest.fn(
  (params: { id: string; page: number }) => {
    const key = `${params.id}:${params.page}`;
    if (!mockQueryResults.has(key)) {
      mockQueryResults.set(key, {
        data: {
          folder: mockFolders.find((folder) => folder.id === params.id),
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
    return mockQueryResults.get(key);
  },
);

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, string>) =>
      key === "project.ownedBy" ? `${options?.name} — ${options?.owner}` : key,
  }),
}));
jest.mock("react-router-dom", () => ({
  useLocation: () => ({ state: undefined }),
  useParams: () => ({ folderId: mockFolderId }),
}));
jest.mock("@/components/common/paginatorComponent", () => (props) => {
  mockPaginate = props.paginate;
  return <div data-testid="paginator-page">{props.pageIndex}</div>;
});
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
jest.mock("@/controllers/API/queries/folders/use-get-project-types", () => ({
  useGetProjectTypesQuery: () => ({ data: [] }),
}));
jest.mock("@/customization/components/custom-banner", () => ({
  CustomBanner: () => null,
}));
jest.mock("@/customization/components/custom-McpServerTab", () => ({
  CustomMcpServerTab: ({ folderName }) => (
    <div data-testid="mcp-project-name">{folderName}</div>
  ),
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
    selector({ myCollectionId: FIRST_PROJECT_ID, folders: mockFolders }),
}));
jest.mock("@/pages/MainPage/components/header", () => ({ folderName }) => (
  <div data-testid="header-project-name">{folderName}</div>
));
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

const lastRequestedPage = () =>
  mockUseGetFolderQuery.mock.calls.at(-1)?.[0].page;

const requestedPagesFor = (projectId: string) =>
  mockUseGetFolderQuery.mock.calls
    .map(([params]) => params)
    .filter((params) => params.id === projectId)
    .map((params) => params.page);

describe("HomePage pagination across projects", () => {
  beforeEach(() => {
    mockUseGetFolderQuery.mockClear();
    mockFolderId = FIRST_PROJECT_ID;
    mockPaginate = undefined;
  });

  it("opens the next project at page 1 after paging the previous one", () => {
    const { rerender } = render(<HomePage type="flows" />);
    act(() => mockPaginate?.(2, 12));
    expect(lastRequestedPage()).toBe(2);

    mockFolderId = SECOND_PROJECT_ID;
    rerender(<HomePage type="flows" />);

    expect(requestedPagesFor(SECOND_PROJECT_ID)).not.toContain(2);
    expect(lastRequestedPage()).toBe(1);
  });

  it("moves to page 2 when Next page is used in the new project", () => {
    const { rerender } = render(<HomePage type="flows" />);
    act(() => mockPaginate?.(2, 12));
    mockFolderId = SECOND_PROJECT_ID;
    rerender(<HomePage type="flows" />);

    act(() => mockPaginate?.(2, 12));

    expect(mockUseGetFolderQuery.mock.calls.at(-1)?.[0]).toMatchObject({
      id: SECOND_PROJECT_ID,
      page: 2,
    });
  });

  it("keeps the page when the same project re-renders", () => {
    const { rerender } = render(<HomePage type="flows" />);
    act(() => mockPaginate?.(3, 12));

    rerender(<HomePage type="flows" />);

    expect(lastRequestedPage()).toBe(3);
  });
});
