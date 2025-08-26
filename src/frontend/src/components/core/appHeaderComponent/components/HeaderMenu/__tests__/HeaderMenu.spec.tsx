import { fireEvent, render, screen } from "@testing-library/react";
import {
  HeaderMenu,
  HeaderMenuItemButton,
  HeaderMenuItemLink,
  HeaderMenuItems,
  HeaderMenuItemsSection,
  HeaderMenuItemsTitle,
  HeaderMenuToggle,
} from "../index";

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }) => <div data-testid="dm">{children}</div>,
  DropdownMenuTrigger: ({ children, ...rest }) => (
    <button data-testid="trigger" {...rest}>
      {children}
    </button>
  ),
  DropdownMenuContent: ({ children, ...rest }) => (
    <div data-testid="content" {...rest}>
      {children}
    </div>
  ),
  DropdownMenuItem: ({ children, ...rest }) => (
    <div role="menuitem" {...rest}>
      {children}
    </div>
  ),
  DropdownMenuSeparator: (props) => <hr data-testid="sep" {...props} />,
}));
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }) => <span data-testid="icon">{name}</span>,
}));

// Avoid pulling darkStore via utils
jest.mock("@/utils/utils", () => ({
  __esModule: true,
  cn: (...args) => args.filter(Boolean).join(" "),
}));

describe("HeaderMenu primitives", () => {
  it("renders toggle and items with title and section", () => {
    render(
      <HeaderMenu>
        <HeaderMenuToggle>avatar</HeaderMenuToggle>
        <HeaderMenuItems position="right">
          <HeaderMenuItemsTitle subTitle="sub">Title</HeaderMenuItemsTitle>
          <HeaderMenuItemsSection>
            <HeaderMenuItemLink href="#" newPage>
              Docs
            </HeaderMenuItemLink>
            <HeaderMenuItemButton icon="logout" onClick={() => {}}>
              Logout
            </HeaderMenuItemButton>
          </HeaderMenuItemsSection>
        </HeaderMenuItems>
      </HeaderMenu>,
    );
    expect(screen.getByTestId("user_menu_button")).toBeInTheDocument();
    expect(screen.getByTestId("content")).toBeInTheDocument();
    expect(screen.getAllByRole("menuitem").length).toBeGreaterThan(0);
  });

  it("HeaderMenuItemLink renders anchor with icon when newPage", () => {
    render(
      <HeaderMenu>
        <HeaderMenuItems>
          <HeaderMenuItemLink href="/x" newPage icon="external-link">
            Link
          </HeaderMenuItemLink>
        </HeaderMenuItems>
      </HeaderMenu>,
    );
    const link = screen.getByText("Link").closest("a")!;
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.getByTestId("icon")).toBeInTheDocument();
  });

  it("HeaderMenuItemButton invokes onClick", () => {
    const onClick = jest.fn();
    render(
      <HeaderMenu>
        <HeaderMenuItems>
          <HeaderMenuItemButton onClick={onClick}>Click</HeaderMenuItemButton>
        </HeaderMenuItems>
      </HeaderMenu>,
    );
    fireEvent.click(screen.getByText("Click"));
    expect(onClick).toHaveBeenCalled();
  });
});
