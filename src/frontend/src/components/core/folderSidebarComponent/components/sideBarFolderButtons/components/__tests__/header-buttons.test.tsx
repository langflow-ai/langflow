import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { useUtilityStore } from "@/stores/utilityStore";
import { HeaderButtons } from "../header-buttons";

jest.mock("react-i18next", () => ({
  initReactI18next: { type: "3rdParty", init: jest.fn() },
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

let mockUserData: { optins: Record<string, boolean> } | undefined;

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: () => mockUserData,
}));

let mockNewProjectButton: { blockedReason: string | null } = {
  blockedReason: null,
};

jest.mock("@/customization/hooks/use-custom-new-project-button", () => ({
  useCustomNewProjectButton: () => mockNewProjectButton,
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
    mockUserData = undefined;
    mockNewProjectButton = { blockedReason: null };
    act(() => {
      useUtilityStore.setState({
        hideGettingStartedProgress: false,
        hideNewProjectButton: false,
      });
    });
  });

  it("shows an unblocked add button with no inline reason by default", () => {
    render(<HeaderButtons {...props} />);

    const btn = screen.getByTestId("add-project-button");
    expect(btn).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText("Plan limit reached")).not.toBeInTheDocument();
  });

  it("blocks the button, keeps it focusable and shows the reason", () => {
    mockNewProjectButton = { blockedReason: "Plan limit reached" };

    render(<HeaderButtons {...props} />);

    const btn = screen.getByTestId("add-project-button");
    expect(btn).toHaveAttribute("aria-disabled", "true");
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveAccessibleDescription("Plan limit reached");
    expect(
      screen
        .getAllByText("Plan limit reached")
        .some((el) => el.tagName === "P"),
    ).toBe(true);

    fireEvent.click(btn);
    expect(props.addNewFolder).not.toHaveBeenCalled();
  });

  it("treats an empty reason as not blocked", () => {
    mockNewProjectButton = { blockedReason: "" };

    const { container } = render(<HeaderButtons {...props} />);

    expect(screen.getByTestId("add-project-button")).not.toHaveAttribute(
      "aria-disabled",
    );
    expect(container.querySelector("p")).not.toBeInTheDocument();
  });

  it("hides the button and inline reason when hideNewProjectButton is true", () => {
    mockNewProjectButton = { blockedReason: "Plan limit reached" };
    act(() => {
      useUtilityStore.setState({ hideNewProjectButton: true });
    });

    render(<HeaderButtons {...props} />);

    expect(screen.queryByTestId("add-project-button")).not.toBeInTheDocument();
    expect(screen.queryByText("Plan limit reached")).not.toBeInTheDocument();
    expect(screen.getByTestId("upload-folder-btn")).toBeInTheDocument();
  });

  it("leaves the checklist divider to the get-started seam", () => {
    mockUserData = { optins: {} };
    act(() => {
      useUtilityStore.setState({ hideGettingStartedProgress: false });
    });

    const { container } = render(<HeaderButtons {...props} />);

    expect(
      screen.getByTestId("custom-get-started-progress"),
    ).toBeInTheDocument();
    expect(container.querySelector("hr")).not.toBeInTheDocument();
  });
});
