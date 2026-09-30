import { act, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useUtilityStore } from "@/stores/utilityStore";
import { HeaderButtons } from "../header-buttons";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("@/controllers/API/queries/auth", () => ({
  useUpdateUser: () => ({ mutate: jest.fn() }),
}));

jest.mock(
  "@/customization/components/custom-get-started-progress",
  () => () => <div data-testid="custom-get-started-progress" />,
);

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: () => undefined,
}));

jest.mock("../add-folder-button", () => ({
  AddFolderButton: ({ disabled }: { disabled?: boolean }) => (
    <button data-testid="add-folder-btn" disabled={disabled}>
      Add folder
    </button>
  ),
}));

jest.mock("../upload-folder-button", () => ({
  UploadFolderButton: ({ disabled }: { disabled?: boolean }) => (
    <button data-testid="upload-folder-btn" disabled={disabled}>
      Upload folder
    </button>
  ),
}));

describe("HeaderButtons", () => {
  const props = {
    handleUploadFlowsToFolder: jest.fn(),
    isUpdatingFolder: false,
    isPending: false,
    addNewFolder: jest.fn(),
  };

  beforeEach(() => {
    act(() => {
      useUtilityStore.setState({
        hideGettingStartedProgress: true,
        hideNewProjectButton: false,
      });
    });
  });

  afterEach(() => {
    act(() => {
      useUtilityStore.setState({
        hideGettingStartedProgress: false,
        hideNewProjectButton: false,
      });
    });
  });

  it("shows add folder button when hideNewProjectButton is false", () => {
    render(<HeaderButtons {...props} />);

    expect(screen.getByTestId("add-folder-btn")).toBeInTheDocument();
  });

  it("hides add folder button when hideNewProjectButton is true", () => {
    act(() => {
      useUtilityStore.setState({ hideNewProjectButton: true });
    });

    render(<HeaderButtons {...props} />);

    expect(screen.queryByTestId("add-folder-btn")).not.toBeInTheDocument();
    expect(screen.getByTestId("upload-folder-btn")).toBeInTheDocument();
  });
});
