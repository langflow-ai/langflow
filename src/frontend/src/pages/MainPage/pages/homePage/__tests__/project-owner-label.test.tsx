import { render, screen } from "@testing-library/react";
import HomePage from "..";

const mockFolders = [
  {
    id: "foreign-id",
    name: "Starter Project",
    description: "",
    parent_id: "",
    flows: [],
    components: [],
    owner_username: "other-user",
    is_owner: false,
  },
  {
    id: "own-id",
    name: "Starter Project",
    description: "",
    parent_id: "",
    flows: [],
    components: [],
    owner_username: "current-user",
    is_owner: true,
  },
];
const mockFlows = [];
const mockNavigate = jest.fn();
let mockFolderId: string | undefined = "foreign-id";
const mockFolderQuery = {
  data: {
    folder: mockFolders[0],
    flows: { items: [], page: 1, size: 12, total: 1, pages: 1 },
  },
  isLoading: false,
};

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
jest.mock("@/components/common/paginatorComponent", () => () => null);
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
  useGetFolderQuery: () => mockFolderQuery,
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
    selector({ myCollectionId: "own-id", folders: mockFolders }),
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

describe("HomePage project names", () => {
  beforeEach(() => {
    mockFolderId = "foreign-id";
  });

  it("qualifies the visible header while preserving the canonical MCP name", async () => {
    render(<HomePage type="mcp" />);

    expect(screen.getByTestId("header-project-name")).toHaveTextContent(
      "Starter Project — other-user",
    );
    expect(await screen.findByTestId("mcp-project-name")).toHaveTextContent(
      "Starter Project",
    );
  });

  it("uses the caller-owned collection name when the default route has no folder id", () => {
    mockFolderId = undefined;

    render(<HomePage type="flows" />);

    expect(screen.getByTestId("header-project-name")).toHaveTextContent(
      "Starter Project",
    );
    expect(screen.getByTestId("header-project-name")).not.toHaveTextContent(
      "other-user",
    );
  });
});
