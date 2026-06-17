import { render, screen } from "@testing-library/react";
import { UploadFolderButton } from "../upload-folder-button";

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
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children?: React.ReactNode }) => (
    <button aria-label={ariaLabel} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}));

describe("UploadFolderButton", () => {
  const defaultProps = { onClick: jest.fn(), disabled: false };

  it("renders the upload project button", () => {
    render(<UploadFolderButton {...defaultProps} />);
    expect(screen.getByTestId("upload-project-button")).toBeInTheDocument();
  });

  it("has an aria-label for screen readers", () => {
    render(<UploadFolderButton {...defaultProps} />);
    const btn = screen.getByTestId("upload-project-button");
    expect(btn).toHaveAttribute("aria-label", "folder.uploadFlow");
  });

  it("is disabled when disabled prop is true", () => {
    render(<UploadFolderButton {...defaultProps} disabled />);
    expect(screen.getByTestId("upload-project-button")).toBeDisabled();
  });
});
