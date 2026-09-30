import { render, screen } from "@testing-library/react";
import { AddFolderButton } from "../add-folder-button";

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    "aria-label": ariaLabel,
    disabled,
    loading,
    ...props
  }: {
    children: React.ReactNode;
    "aria-label"?: string;
    disabled?: boolean;
    loading?: boolean;
    [key: string]: unknown;
  }) => (
    <button
      aria-label={ariaLabel}
      disabled={disabled}
      data-loading={loading}
      {...props}
    >
      {children}
    </button>
  ),
}));

describe("AddFolderButton", () => {
  const defaultProps = { onClick: jest.fn(), disabled: false, loading: false };

  it("renders the add project button", () => {
    render(<AddFolderButton {...defaultProps} />);
    expect(screen.getByTestId("add-project-button")).toBeInTheDocument();
  });

  it("has an aria-label for screen readers", () => {
    render(<AddFolderButton {...defaultProps} />);
    const btn = screen.getByTestId("add-project-button");
    expect(btn).toHaveAttribute("aria-label", "folder.createNewProject");
  });

  it("is disabled when disabled prop is true", () => {
    render(<AddFolderButton {...defaultProps} disabled />);
    expect(screen.getByTestId("add-project-button")).toBeDisabled();
  });
});
