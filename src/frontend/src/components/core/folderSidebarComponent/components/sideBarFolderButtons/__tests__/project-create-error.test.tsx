import { act, fireEvent, render, screen } from "@testing-library/react";
import SideBarFoldersButtonsComponent from "..";

const mockMutateAddFolder = jest.fn();
const mockMutateUpdateFolder = jest.fn();
const mockSetErrorData = jest.fn();
const mockCan = jest.fn(
  (_projectId: string | undefined | null, _action: string) => true,
);
let mockFolders: Array<{
  id: string;
  name: string;
  description: string;
  parent_id: string;
  flows: never[];
  components: never[];
  owner_username: string;
  is_owner: boolean;
}> = [];

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useIsFetching: () => 0,
  useIsMutating: () => 0,
}));

jest.mock("react-i18next", () => ({
  initReactI18next: { type: "3rdParty", init: jest.fn() },
  useTranslation: () => ({
    t: (key: string, options?: Record<string, string>) => {
      if (key === "sidebar.projectCreateError") {
        return "Unable to create project.";
      }
      if (key === "project.ownedBy") {
        return `${options?.name} — ${options?.owner}`;
      }
      return key;
    },
  }),
}));

jest.mock("react-router-dom", () => ({
  useLocation: () => ({ pathname: "/flows" }),
  useParams: () => ({}),
}));

jest.mock("@/components/ui/sidebar", () => {
  const Wrapper = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  );
  const SidebarMenuButton = ({
    children,
    isActive: _isActive,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    isActive?: boolean;
    size?: string;
  }) => (
    <button type="button" {...props}>
      {children}
    </button>
  );
  return {
    Sidebar: Wrapper,
    SidebarContent: Wrapper,
    SidebarFooter: Wrapper,
    SidebarGroup: Wrapper,
    SidebarGroupContent: Wrapper,
    SidebarHeader: Wrapper,
    SidebarMenu: Wrapper,
    SidebarMenuButton,
    SidebarMenuItem: Wrapper,
  };
});

jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  usePermissions: () => ({ can: mockCan }),
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useUpdateUser: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/folders", () => ({
  usePatchFolders: () => ({ mutate: mockMutateUpdateFolder }),
  usePostFolders: () => ({
    mutate: mockMutateAddFolder,
    isPending: false,
  }),
  usePostUploadFolders: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/folders/use-get-download-folders", () => ({
  useGetDownloadFolders: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_CUSTOM_PARAM: false,
  ENABLE_DATASTAX_LANGFLOW: false,
  ENABLE_FILE_MANAGEMENT: false,
  ENABLE_KNOWLEDGE_BASES: false,
  ENABLE_MCP_NOTICE: false,
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({ track: jest.fn() }));
jest.mock("@/hooks/flows/use-upload-flow", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));
jest.mock("@/hooks/use-mobile", () => ({ useIsMobile: () => false }));
jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: { userData: undefined }) => unknown) =>
    selector({ userData: undefined }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      setErrorData: jest.Mock;
      setSuccessData: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: jest.fn(),
    }),
}));
jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { takeSnapshot: jest.Mock }) => unknown) =>
    selector({ takeSnapshot: jest.fn() }),
}));
jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: (
    selector: (state: {
      folders: typeof mockFolders;
      folderIdDragging: null;
      myCollectionId: string;
    }) => unknown,
  ) =>
    selector({
      folders: mockFolders,
      folderIdDragging: null,
      myCollectionId: "root",
    }),
}));
jest.mock("../../../hooks/use-on-file-drop", () => ({
  __esModule: true,
  default: () => ({
    dragOver: jest.fn(),
    dragEnter: jest.fn(),
    dragLeave: jest.fn(),
    onDrop: jest.fn(),
  }),
}));
jest.mock("../components/header-buttons", () => ({
  HeaderButtons: ({ addNewFolder }: { addNewFolder: () => void }) => (
    <button type="button" onClick={addNewFolder}>
      New Project
    </button>
  ),
}));
jest.mock("../components/input-edit-folder-name", () => ({
  InputEditFolderName: ({
    item,
    foldersNames,
    handleEditFolderName,
    handleEditNameFolder,
  }: {
    item: { id: string };
    foldersNames: Record<string, string>;
    handleEditFolderName: (
      event: React.ChangeEvent<HTMLInputElement>,
      folderId: string,
    ) => void;
    handleEditNameFolder: (item: { id: string }) => void;
  }) => (
    <input
      data-testid={`input-project-${item.id}`}
      value={foldersNames[item.id] ?? ""}
      onChange={(event) => handleEditFolderName(event, item.id)}
      onBlur={() => handleEditNameFolder(item)}
    />
  ),
}));
jest.mock("../components/mcp-server-notice", () => ({
  MCPServerNotice: () => null,
}));
jest.mock("../components/select-options", () => ({
  SelectOptions: () => null,
}));
jest.mock("../../sidebarFolderSkeleton", () => ({
  SidebarFolderSkeleton: () => null,
}));

describe("project creation errors", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCan.mockReturnValue(true);
    mockFolders = [];
  });

  it("surfaces a backend permission denial in the alert UI", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "New Project" }));
    const mutationOptions = mockMutateAddFolder.mock.calls[0][1];

    act(() => {
      mutationOptions.onError({
        response: { data: { detail: "Not enough permissions" } },
      });
    });

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "Unable to create project.",
      list: ["Not enough permissions"],
    });
  });

  it("qualifies foreign duplicate names and only renames writable projects by id", () => {
    mockFolders = [
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
    ];

    mockCan.mockImplementation(
      (projectId: string | undefined | null, action: string) =>
        action !== "write" || projectId !== "foreign-id",
    );

    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    expect(screen.getByTestId("sidebar-nav-own-id")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-nav-foreign-id")).toBeInTheDocument();
    const ownLabel = screen.getByText("Starter Project");
    const foreignLabel = screen.getByText("Starter Project — other-user");
    fireEvent.doubleClick(foreignLabel);

    expect(
      screen.queryByTestId("input-project-foreign-id"),
    ).not.toBeInTheDocument();
    expect(mockMutateUpdateFolder).not.toHaveBeenCalled();

    fireEvent.doubleClick(ownLabel);

    const ownInput = screen.getByTestId("input-project-own-id");
    expect(
      screen.queryByTestId("input-project-foreign-id"),
    ).not.toBeInTheDocument();
    expect(ownInput).toHaveValue("Starter Project");

    fireEvent.change(ownInput, { target: { value: "Renamed Project" } });
    fireEvent.blur(ownInput);

    expect(mockMutateUpdateFolder).toHaveBeenCalledWith(
      {
        data: expect.objectContaining({ name: "Renamed Project" }),
        folderId: "own-id",
      },
      expect.any(Object),
    );
  });
});
