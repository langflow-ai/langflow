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

// Project names are truncated with an ellipsis and the sidebar cannot be
// widened. With one default project per user the list fills with same-prefixed
// entries — "Starter Project — u_vie...", "Starter Project — u_edi..." — where
// the truncated portion is the only part that distinguishes one row from
// another. The full name has to stay reachable (LE-1905 finding 12).
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

// Someone else's project: the display name is the composed
// "<name> — <owner>" form, which is exactly the shape that truncates.
const SHARED_FOLDER = {
  ...OWN_FOLDER,
  id: "shared-id",
  name: "Starter Project",
  owner_username: "u_editor_with_a_long_name",
  is_owner: false,
};

const nameCellFor = (folderId: string) =>
  screen.getByTestId(`sidebar-nav-${folderId}`).querySelector("span");

describe("project name tooltip", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCan.mockReturnValue(true);
    mockFolders = [OWN_FOLDER, SHARED_FOLDER];
  });

  it("exposes the full display name as a title on every project row", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    expect(nameCellFor(OWN_FOLDER.id)).toHaveAttribute(
      "title",
      "Starter Project",
    );
    expect(nameCellFor(SHARED_FOLDER.id)).toHaveAttribute(
      "title",
      "Starter Project — u_editor_with_a_long_name",
    );
  });

  it("keeps the title identical to the rendered name", () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);

    for (const folder of [OWN_FOLDER, SHARED_FOLDER]) {
      const cell = nameCellFor(folder.id);
      // A title that drifts from the text is worse than none: the tooltip
      // would claim a different project than the row it belongs to.
      expect(cell).toHaveAttribute("title", cell?.textContent ?? "");
    }
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
