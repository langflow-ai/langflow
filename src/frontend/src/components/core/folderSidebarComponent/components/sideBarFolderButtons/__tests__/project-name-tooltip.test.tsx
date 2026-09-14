import { fireEvent, render, screen } from "@testing-library/react";
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
  is_owner?: boolean;
}> = [];
let mockPermissionsResourceIds: string[] = [];

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
  PermissionsProvider: ({
    children,
    resourceIds,
  }: {
    children: React.ReactNode;
    resourceIds: string[];
  }) => {
    mockPermissionsResourceIds = resourceIds;
    return <>{children}</>;
  },
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
    // Mirrors the real input's autoFocus, which is what makes the unmount drop
    // focus to <body> in the first place.
    <input
      autoFocus
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

// The sidebar lists only the current user's own projects — everything else
// (explicitly shared, or visible via a broad role/scope grant) has its own
// home in "Shared with me" / "Visible via your role" instead. Previously a
// non-owned row rendered here too, disambiguated only by a "<name> —
// <owner>" suffix that became unreadable once truncated by the sidebar's
// fixed width, with one default project per user filling the list with
// same-prefixed entries (LE-1905 finding 12). Scoping the sidebar to owned
// projects removes the suffix's reason to exist here at all, not just its
// truncation problem.
const OWN_FOLDER = {
  id: "own-id",
  name: "Starter Project",
  description: "",
  parent_id: "",
  flows: [] as never[],
  components: [] as never[],
  owner_username: "current-user",
  is_owner: true,
};

// Someone else's project — reachable via a role grant or an explicit share,
// neither of which makes it "mine". Must never render in the sidebar.
const OTHER_FOLDER = {
  ...OWN_FOLDER,
  id: "other-id",
  name: "Someone Else's Project",
  owner_username: "u_editor_with_a_long_name",
  is_owner: false,
};

// A caller that doesn't populate is_owner at all — the filter's `!== false`
// check must treat this as owned (matching getProjectDisplayName's own
// existing fallback), not silently drop it from the sidebar.
const UNDEFINED_OWNER_FOLDER = {
  id: "undefined-owner-id",
  name: "Legacy Project",
  description: "",
  parent_id: "",
  flows: [] as never[],
  components: [] as never[],
  owner_username: "current-user",
};

const nameCellFor = (folderId: string) =>
  screen.getByTestId(`sidebar-nav-${folderId}`).querySelector("span");

describe("project name tooltip", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCan.mockReturnValue(true);
    mockFolders = [OWN_FOLDER, OTHER_FOLDER];
  });

  it("renders only the caller's own projects, never a non-owned one", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    expect(
      screen.getByTestId(`sidebar-nav-${OWN_FOLDER.id}`),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId(`sidebar-nav-${OTHER_FOLDER.id}`),
    ).not.toBeInTheDocument();
  });

  it("treats a folder with no is_owner field at all as owned", () => {
    mockFolders = [UNDEFINED_OWNER_FOLDER, OTHER_FOLDER];

    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    expect(
      screen.getByTestId(`sidebar-nav-${UNDEFINED_OWNER_FOLDER.id}`),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId(`sidebar-nav-${OTHER_FOLDER.id}`),
    ).not.toBeInTheDocument();
  });

  it("only requests permissions for the projects it actually renders", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    expect(mockPermissionsResourceIds).toEqual([OWN_FOLDER.id]);
    expect(mockPermissionsResourceIds).not.toContain(OTHER_FOLDER.id);
  });

  it("exposes the plain project name as a title, with no ownership suffix", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    expect(nameCellFor(OWN_FOLDER.id)).toHaveAttribute(
      "title",
      "Starter Project",
    );
  });

  it("keeps the title identical to the rendered name", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    const cell = nameCellFor(OWN_FOLDER.id);
    // A title that drifts from the text is worse than none: the tooltip
    // would claim a different project than the row it belongs to.
    expect(cell).toHaveAttribute("title", cell?.textContent ?? "");
  });

  it("does not render a title on the rename input that replaces the name", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);
    fireEvent.doubleClick(screen.getByTestId(`sidebar-nav-${OWN_FOLDER.id}`));

    // While editing there is no truncated label to explain.
    expect(nameCellFor(OWN_FOLDER.id)).toBeNull();
    expect(
      screen.getByTestId(`input-project-${OWN_FOLDER.id}`),
    ).toBeInTheDocument();
  });
});
