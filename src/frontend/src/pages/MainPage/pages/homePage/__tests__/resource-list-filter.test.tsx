import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import type { FlowType } from "@/types/flow";
import HomePage from "..";

const PROJECT_ID = "project-1";
const CURRENT_USER_ID = "me";

const mockFolders = [
  {
    id: PROJECT_ID,
    name: "Starter Project",
    description: "",
    parent_id: "",
    flows: [],
    components: [],
    is_owner: true,
  },
];
let mockFolderFlows: FlowType[] = [];
let mockTotal = 0;
let mockQueryResult: unknown;
const mockFilter = jest.fn();

const flow = (id: string, userId?: string): FlowType =>
  ({
    id,
    name: `Flow ${id}`,
    user_id: userId,
    folder_id: PROJECT_ID,
    is_component: false,
  }) as FlowType;

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));
jest.mock("react-router-dom", () => ({
  useLocation: () => ({ state: undefined }),
  useParams: () => ({ folderId: PROJECT_ID }),
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
  useGetFolderQuery: () => mockQueryResult,
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
  useCustomNavigate: () => jest.fn(),
}));
jest.mock("@/customization/hooks/use-custom-resource-list-filter", () => ({
  useCustomResourceListFilter: (...args: unknown[]) => mockFilter(...args),
}));
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector) => selector({ userData: { id: CURRENT_USER_ID } }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector) => selector({ flows: mockFolderFlows }),
}));
jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (selector) =>
    selector({ myCollectionId: PROJECT_ID, folders: mockFolders }),
}));
jest.mock(
  "@/pages/MainPage/components/header",
  () =>
    ({
      listTools,
      selectedFlows,
    }: {
      listTools?: ReactNode;
      selectedFlows: string[];
    }) => (
      <div data-testid="header" data-selected={selectedFlows.join(",")}>
        {listTools}
      </div>
    ),
);
jest.mock(
  "@/pages/MainPage/components/list",
  () =>
    ({
      flowData,
      isOwned,
      setSelected,
    }: {
      flowData: FlowType;
      isOwned: boolean;
      setSelected: (selected: boolean) => void;
    }) => (
      <div data-testid="flow-row" data-id={flowData.id} data-owned={isOwned}>
        <button type="button" onClick={() => setSelected(true)}>
          {`select ${flowData.id}`}
        </button>
      </div>
    ),
);
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
jest.mock("@/pages/MainPage/pages/emptyFolder", () => () => (
  <div data-testid="empty-folder" />
));

const actualFilter = jest.requireActual(
  "@/customization/hooks/use-custom-resource-list-filter",
).useCustomResourceListFilter;

const ownedOnly = <T,>(
  _type: string,
  items: T[],
  isOwned: (item: T) => boolean,
) => ({
  items: items.filter(isOwned),
  tools: <button type="button">Owned</button>,
});

const setFlows = (flows: FlowType[]) => {
  mockFolderFlows = flows;
  mockTotal = flows.length;
  // A stable reference, as React Query returns, so effects don't loop.
  mockQueryResult = {
    data: {
      folder: mockFolders[0],
      flows: {
        items: flows,
        page: 1,
        size: 12,
        total: mockTotal,
        pages: 1,
      },
    },
    isLoading: false,
  };
};

const renderPage = async () => {
  render(<HomePage type="flows" />);
  await act(async () => {});
};

const renderedIds = () =>
  screen.getAllByTestId("flow-row").map((row) => row.getAttribute("data-id"));

describe("HomePage flow list filter seam", () => {
  beforeEach(() => {
    localStorage.clear();
    mockFilter.mockReset();
    mockFilter.mockImplementation(actualFilter);
  });

  it("should_render_every_flow_in_order_with_no_tools_when_the_seam_is_the_default", async () => {
    setFlows([flow("a", CURRENT_USER_ID), flow("b", "other"), flow("c")]);

    await renderPage();

    expect(renderedIds()).toEqual(["a", "b", "c"]);
    expect(screen.getByTestId("header")).toBeEmptyDOMElement();
    expect(screen.queryByTestId("empty-folder")).not.toBeInTheDocument();
  });

  it("should_pass_the_flow_type_and_the_page_flows_to_the_seam", async () => {
    const flows = [flow("a", CURRENT_USER_ID)];
    setFlows(flows);

    await renderPage();

    expect(mockFilter).toHaveBeenCalledWith(
      "flow",
      flows,
      expect.any(Function),
    );
  });

  it("should_compute_isOwned_from_user_id_for_owner_non_owner_and_missing", async () => {
    setFlows([
      flow("mine", CURRENT_USER_ID),
      flow("theirs", "other"),
      flow("legacy"),
    ]);

    await renderPage();

    const isOwned = mockFilter.mock.calls.at(-1)?.[2];
    expect(isOwned(flow("mine", CURRENT_USER_ID))).toBe(true);
    expect(isOwned(flow("theirs", "other"))).toBe(false);
    expect(isOwned(flow("legacy"))).toBe(true);
    const owned = screen
      .getAllByTestId("flow-row")
      .map((row) => row.getAttribute("data-owned"));
    expect(owned).toEqual(["true", "false", "true"]);
  });

  it("should_render_only_filtered_flows_and_the_tools_when_the_seam_filters", async () => {
    setFlows([
      flow("mine", CURRENT_USER_ID),
      flow("theirs", "other"),
      flow("legacy"),
    ]);
    mockFilter.mockImplementation(ownedOnly);

    await renderPage();

    expect(renderedIds()).toEqual(["mine", "legacy"]);
    expect(
      screen.getByRole("button", { name: "Owned" }).closest("[data-testid]"),
    ).toBe(screen.getByTestId("header"));
  });

  it("should_show_the_empty_folder_and_give_the_seam_an_empty_list_when_the_project_has_no_flows", async () => {
    setFlows([]);
    mockFilter.mockImplementation(ownedOnly);

    await renderPage();

    expect(mockFilter).toHaveBeenCalledWith("flow", [], expect.any(Function));
    expect(screen.getByTestId("empty-folder")).toBeInTheDocument();
    expect(screen.queryByTestId("flow-row")).not.toBeInTheDocument();
  });

  it("should_render_one_row_per_flow_in_the_grid_view_with_many_flows", async () => {
    localStorage.setItem("view", "grid");
    const flows = Array.from({ length: 25 }, (_, index) =>
      flow(`f${index}`, index % 2 ? "other" : CURRENT_USER_ID),
    );
    setFlows(flows);
    mockFilter.mockImplementation(ownedOnly);

    await renderPage();

    expect(renderedIds()).toEqual(
      flows.filter((_, index) => index % 2 === 0).map((item) => item.id),
    );
  });

  it("should_shift_select_a_range_of_visible_flows_without_the_hidden_ones", async () => {
    setFlows([flow("a", CURRENT_USER_ID), flow("hidden", "other"), flow("c")]);
    mockFilter.mockImplementation(ownedOnly);
    await renderPage();

    fireEvent.click(screen.getByRole("button", { name: "select a" }));
    fireEvent.keyDown(document, { key: "Shift" });
    fireEvent.click(screen.getByRole("button", { name: "select c" }));

    expect(screen.getByTestId("header")).toHaveAttribute(
      "data-selected",
      "a,c",
    );
  });

  it("should_drop_a_selected_flow_from_the_selection_when_the_filter_hides_it", async () => {
    setFlows([flow("a", CURRENT_USER_ID), flow("theirs", "other")]);
    const { rerender } = render(<HomePage type="flows" />);
    await act(async () => {});
    fireEvent.click(screen.getByRole("button", { name: "select theirs" }));
    expect(screen.getByTestId("header")).toHaveAttribute(
      "data-selected",
      "theirs",
    );

    mockFilter.mockImplementation(ownedOnly);
    rerender(<HomePage type="flows" />);
    await act(async () => {});

    expect(screen.getByTestId("header")).toHaveAttribute("data-selected", "");
  });
});
