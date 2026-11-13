import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useFolderStore } from "@/stores/foldersStore";
import HomePage from "..";

const TOTAL_FLOWS = 30;
const mockApiGet = jest.fn();

// The network is the only fake on the paging path: the route, HomePage, the
// folder query on a real query client and the paginator are all real.
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

// Parts of the page that paging does not go through.
jest.mock(
  "@/components/core/flowBuilderWelcome/hooks/use-start-new-flow",
  () => ({ useStartNewFlow: () => jest.fn() }),
);
jest.mock("@/customization/components/custom-McpServerTab", () => ({
  CustomMcpServerTab: () => null,
}));
jest.mock("@/pages/MainPage/components/header", () => () => null);
jest.mock("@/pages/MainPage/components/list", () => () => null);
jest.mock("@/pages/MainPage/components/modalsComponent", () => () => null);
jest.mock("@/pages/MainPage/hooks/use-on-file-drop", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));
jest.mock(
  "@/pages/MainPage/pages/deploymentsPage/deployments-page",
  () => () => null,
);

const projectRequests = () =>
  mockApiGet.mock.calls.map(([url]) => {
    const { pathname, searchParams } = new URL(url, "http://localhost");
    return `${pathname.split("/").pop()} page ${searchParams.get("page")}`;
  });

describe("HomePage paging across projects", () => {
  beforeEach(() => {
    mockApiGet.mockReset();
    // Answers with the page the request asks for, as the server does.
    mockApiGet.mockImplementation(async (url: string) => {
      const { searchParams } = new URL(url, "http://localhost");
      const size = Number(searchParams.get("size"));
      return {
        data: {
          folder: {},
          flows: {
            items: [],
            page: Number(searchParams.get("page")),
            size,
            total: TOTAL_FLOWS,
            pages: Math.ceil(TOTAL_FLOWS / size),
          },
        },
      };
    });
    useFolderStore.setState({
      folders: [
        { id: "alpha-id", name: "Alpha" },
        { id: "beta-id", name: "Beta" },
      ] as never,
    });
    useFlowsManagerStore.setState({ flows: [] });
  });

  it("opens the next project at its first page, and its next page still works", async () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/all/folder/alpha-id"]}>
          <Link to="/all/folder/beta-id">Beta</Link>
          <Routes>
            <Route
              path="/all/folder/:folderId"
              element={<HomePage type="flows" />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const nextPage = () =>
      screen.getByRole("button", { name: "Go to next page" });

    await screen.findByText("1-12");
    fireEvent.click(nextPage());
    await screen.findByText("13-24");

    fireEvent.click(screen.getByRole("link", { name: "Beta" }));
    await screen.findByText("1-12");
    fireEvent.click(nextPage());
    await screen.findByText("13-24");

    expect(projectRequests()).toEqual([
      "alpha-id page 1",
      "alpha-id page 2",
      "beta-id page 1",
      "beta-id page 2",
    ]);
  });
});
