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
  useGetProjectTypesQuery: () => ({ data: undefined, isLoading: false }),
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

const FOLDER = {
  id: "own-id",
  name: "Starter Project",
  description: "",
  parent_id: "",
  flows: [] as never[],
  components: [] as never[],
  owner_username: "current-user",
  is_owner: true,
};

// Committing a rename unmounts the focused input. Without a handoff focus falls
// to <body>, forcing a keyboard user to tab from the top of the page back to the
// project they just renamed (WCAG 2.4.3).
describe("project rename focus handling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCan.mockReturnValue(true);
    mockFolders = [FOLDER];
  });

  const startRenaming = () => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);
    fireEvent.doubleClick(screen.getByTestId(`sidebar-nav-${FOLDER.id}`));
    return screen.getByTestId(`input-project-${FOLDER.id}`);
  };

  it("returns focus to the project nav item after a rename is committed", () => {
    const input = startRenaming();
    expect(input).toHaveFocus();

    fireEvent.blur(input);

    expect(screen.getByTestId(`sidebar-nav-${FOLDER.id}`)).toHaveFocus();
  });

  it("does not steal focus when the user moves to another control", () => {
    const input = startRenaming();
    const newProjectButton = screen.getByRole("button", {
      name: "New Project",
    });

    newProjectButton.focus();
    fireEvent.blur(input);

    expect(newProjectButton).toHaveFocus();
  });
});

// A rejected rename used to be swallowed: the mutation had no onError, so the old
// name reappeared with nothing on screen explaining why. The backend rejects a
// rename when the project's MCP server name collides with another project's.
describe("project rename error feedback", () => {
  const CONFLICT_DETAIL =
    "MCP server name conflict: 'lf-unnamed' already exists for a different project.";

  beforeEach(() => {
    jest.clearAllMocks();
    mockCan.mockReturnValue(true);
    mockFolders = [FOLDER];
    jest.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  const renameTo = (newName: string) => {
    render(<SideBarFoldersButtonsComponent handleChangeFolder={jest.fn()} />);
    fireEvent.doubleClick(screen.getByTestId(`sidebar-nav-${FOLDER.id}`));
    const input = screen.getByTestId(`input-project-${FOLDER.id}`);
    fireEvent.change(input, { target: { value: newName } });
    fireEvent.blur(input);
  };

  it("shows the backend reason when the rename is rejected", () => {
    mockMutateUpdateFolder.mockImplementation((_payload, options) => {
      options?.onError?.({ response: { data: { detail: CONFLICT_DETAIL } } });
    });

    renameTo("繁體中文專案");

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "sidebar.renameError",
      list: [CONFLICT_DETAIL],
    });
  });

  it("falls back to the error message when the response carries no detail", () => {
    mockMutateUpdateFolder.mockImplementation((_payload, options) => {
      options?.onError?.(new Error("Network Error"));
    });

    renameTo("繁體中文專案");

    expect(mockSetErrorData).toHaveBeenCalledWith({
      title: "sidebar.renameError",
      list: ["Network Error"],
    });
  });

  it("puts the stored name back in the input after a failure", () => {
    mockMutateUpdateFolder.mockImplementation((_payload, options) => {
      options?.onError?.({ response: { data: { detail: CONFLICT_DETAIL } } });
    });

    renameTo("繁體中文專案");
    fireEvent.doubleClick(screen.getByTestId(`sidebar-nav-${FOLDER.id}`));

    // Without the restore the rejected name would still be sitting in the input
    expect(screen.getByTestId(`input-project-${FOLDER.id}`)).toHaveValue(
      FOLDER.name,
    );
  });

  it("stays quiet when the rename succeeds", () => {
    mockMutateUpdateFolder.mockImplementation((_payload, options) => {
      options?.onSuccess?.({ ...FOLDER, name: "繁體中文專案" });
    });

    renameTo("繁體中文專案");

    expect(mockSetErrorData).not.toHaveBeenCalled();
  });
});
