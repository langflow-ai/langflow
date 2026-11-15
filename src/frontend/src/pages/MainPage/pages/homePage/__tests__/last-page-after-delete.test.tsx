import { fireEvent, render, screen } from "@testing-library/react";
import HomePage from "..";

const PROJECT = {
  id: "project-id",
  name: "Starter Project",
  description: "",
  parent_id: "",
  flows: [],
  components: [],
};
const mockFolders = [PROJECT];
let mockTotalFlows = 13;
let mockIsFetching = false;
const mockRequestedPages: number[] = [];

// Answers with the page the request asks for, as the server does: a page past
// the end comes back with no items and the real page count. Each answer is
// built once, as a cached query result would be.
const mockAnswers = new Map<string, unknown>();
const mockFolderPage = ({ page, size }: { page: number; size: number }) => {
  mockRequestedPages.push(page);
  const key = `${page}/${size}/${mockTotalFlows}`;
  if (!mockAnswers.has(key)) {
    const names = Array.from(
      { length: mockTotalFlows },
      (_, index) => `Flow ${index + 1}`,
    );
    mockAnswers.set(key, {
      data: {
        folder: PROJECT,
        flows: {
          items: names
            .slice((page - 1) * size, page * size)
            .map((name) => ({ id: name, name })),
          page,
          size,
          total: mockTotalFlows,
          pages: Math.ceil(mockTotalFlows / size),
        },
      },
      isLoading: false,
    });
  }
  return { ...(mockAnswers.get(key) as object), isFetching: mockIsFetching };
};

jest.mock("react-router-dom", () => ({
  useLocation: () => ({ state: undefined }),
  useParams: () => ({ folderId: "project-id" }),
}));
jest.mock("@/components/core/cardsWrapComponent", () => ({ children }) => (
  <>{children}</>
));
jest.mock(
  "@/components/core/flowBuilderWelcome/hooks/use-start-new-flow",
  () => ({ useStartNewFlow: () => jest.fn() }),
);
jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }) => <>{children}</>,
}));
jest.mock("@/controllers/API/queries/folders/use-get-folder", () => ({
  useGetFolderQuery: (params) => mockFolderPage(params),
}));
jest.mock("@/customization/components/custom-banner", () => ({
  CustomBanner: () => null,
}));
jest.mock("@/customization/components/custom-McpServerTab", () => ({
  CustomMcpServerTab: () => null,
}));
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector) =>
    selector({ flows: [{ id: "Flow 1", folder_id: "project-id" }] }),
}));
jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector) =>
    selector({ myCollectionId: "project-id", folders: mockFolders }),
}));
jest.mock("@/pages/MainPage/components/header", () => () => null);
jest.mock("@/pages/MainPage/components/list", () => ({ flowData }) => (
  <div data-testid="flow-row">{flowData.name}</div>
));
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

const shownFlows = () =>
  screen.queryAllByTestId("flow-row").map((row) => row.textContent);

describe("HomePage paging after the last page empties", () => {
  beforeEach(() => {
    mockTotalFlows = 13;
    mockIsFetching = false;
    mockRequestedPages.length = 0;
  });

  it("steps back to the last page that still has flows", () => {
    const { rerender } = render(<HomePage type="flows" />);
    fireEvent.click(screen.getByRole("button", { name: "Go to next page" }));
    expect(shownFlows()).toEqual(["Flow 13"]);

    // The only flow on page 2 is deleted and the list is read again.
    mockTotalFlows = 12;
    rerender(<HomePage type="flows" />);

    expect(shownFlows()).toHaveLength(12);
    expect(shownFlows()).toContain("Flow 12");
    expect(screen.getByText("1-12")).toBeInTheDocument();
    expect(mockRequestedPages.at(-1)).toBe(1);
  });

  it("stays on the current page while it still has flows", () => {
    mockTotalFlows = 14;
    const { rerender } = render(<HomePage type="flows" />);
    fireEvent.click(screen.getByRole("button", { name: "Go to next page" }));
    expect(shownFlows()).toEqual(["Flow 13", "Flow 14"]);

    mockTotalFlows = 13;
    rerender(<HomePage type="flows" />);

    expect(shownFlows()).toEqual(["Flow 13"]);
    expect(mockRequestedPages.at(-1)).toBe(2);
  });

  it("stays on a page whose cached page count is outdated until it is read again", () => {
    const { rerender } = render(<HomePage type="flows" />);
    fireEvent.click(screen.getByRole("button", { name: "Go to next page" }));

    // The cache still holds an answer from when there was a single page.
    mockTotalFlows = 12;
    mockIsFetching = true;
    rerender(<HomePage type="flows" />);
    expect(mockRequestedPages.at(-1)).toBe(2);

    // The fresh answer has a second page.
    mockTotalFlows = 13;
    mockIsFetching = false;
    rerender(<HomePage type="flows" />);

    expect(shownFlows()).toEqual(["Flow 13"]);
    expect(mockRequestedPages.at(-1)).toBe(2);
  });
});
