import { act, fireEvent, render, screen } from "@testing-library/react";
import SideBarFoldersButtonsComponent from "..";

const mockMutateAddFolder = jest.fn();
const mockSetErrorData = jest.fn();

jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useIsFetching: () => 0,
  useIsMutating: () => 0,
}));

jest.mock("react-i18next", () => ({
  initReactI18next: { type: "3rdParty", init: jest.fn() },
  useTranslation: () => ({
    t: (key: string) =>
      key === "sidebar.projectCreateError" ? "Unable to create project." : key,
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
  return {
    Sidebar: Wrapper,
    SidebarContent: Wrapper,
    SidebarFooter: Wrapper,
    SidebarGroup: Wrapper,
    SidebarGroupContent: Wrapper,
    SidebarHeader: Wrapper,
    SidebarMenu: Wrapper,
    SidebarMenuButton: Wrapper,
    SidebarMenuItem: Wrapper,
  };
});

jest.mock("@/contexts/permissionsContext", () => ({
  PermissionsProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useUpdateUser: () => ({ mutate: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/folders", () => ({
  usePatchFolders: () => ({ mutate: jest.fn() }),
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

jest.mock("@/customization/components/custom-store-button", () => ({
  CustomStoreButton: () => null,
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
      folders: never[];
      folderIdDragging: null;
      myCollectionId: string;
    }) => unknown,
  ) =>
    selector({
      folders: [],
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
  InputEditFolderName: () => null,
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
});
