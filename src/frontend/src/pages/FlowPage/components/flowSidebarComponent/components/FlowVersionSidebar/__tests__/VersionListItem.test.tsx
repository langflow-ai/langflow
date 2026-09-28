/**
 * The dropdown menu content renders inside the row's button, so a menu click
 * bubbles to the row's onSelect unless it is stopped. Browser testing caught
 * this: entering compare mode swapped the canvas to the version being compared.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import type { FlowVersionEntry } from "@/types/flow/version";
import VersionListItem from "../components/VersionListItem";

/** Minimal shape the mocked primitives receive; keeps the doubles untyped-free. */
type MockProps = {
  children?: React.ReactNode;
  className?: string;
  onClick?: (event: React.MouseEvent) => void;
};

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/common/versionLabelComponent", () => ({
  __esModule: true,
  default: ({ versionTag }: { versionTag: string }) => (
    <span>{versionTag}</span>
  ),
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarMenuItem: ({ children, className }: MockProps) => (
    <li className={className}>{children}</li>
  ),
  // Mirrors the real component: the row is a button wrapping its own content,
  // which is exactly why menu clicks inside it can bubble into onClick.
  SidebarMenuButton: ({ children, onClick }: MockProps) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: MockProps) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: MockProps) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: MockProps) => (
    <div role="menuitem" onClick={onClick}>
      {children}
    </div>
  ),
  DropdownMenuTrigger: ({ children }: MockProps) => <div>{children}</div>,
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: unknown[]) => args.filter(Boolean).join(" "),
}));

const entry: FlowVersionEntry = {
  id: "entry-1",
  flow_id: "flow-1",
  user_id: "user-1",
  version_number: 1,
  version_tag: "v1",
  description: "baseline",
  created_at: "2026-01-01T00:00:00Z",
};

function renderItem(
  props: Partial<React.ComponentProps<typeof VersionListItem>> = {},
) {
  const handlers = {
    onSelect: jest.fn(),
    onCompareClick: jest.fn(),
    onExport: jest.fn(),
    onDeleteClick: jest.fn(),
  };
  render(
    <VersionListItem
      entry={entry}
      isSelected={false}
      isAnimating={false}
      {...handlers}
      {...props}
    />,
  );
  return handlers;
}

describe("VersionListItem", () => {
  it("offers Compare with… as a menu action", () => {
    renderItem();

    expect(screen.getByText("Compare with…")).toBeInTheDocument();
  });

  it("starts a comparison without also selecting the row", () => {
    const handlers = renderItem();

    fireEvent.click(screen.getByText("Compare with…"));

    expect(handlers.onCompareClick).toHaveBeenCalledWith(entry);
    // The regression: without stopPropagation this also fires, previewing the
    // version on the canvas the moment compare mode is entered.
    expect(handlers.onSelect).not.toHaveBeenCalled();
  });

  it("selects the row when the row itself is clicked", () => {
    const handlers = renderItem();

    // The row button is the one wrapping the version label; the other is the
    // menu trigger.
    fireEvent.click(screen.getByText("v1").closest("button") as HTMLElement);

    expect(handlers.onSelect).toHaveBeenCalledWith("entry-1");
  });

  it("hides the menu while a comparison target is being picked", () => {
    renderItem({ compareMode: true });

    expect(screen.queryByText("Compare with…")).not.toBeInTheDocument();
  });

  it("dims and disables the row that the comparison starts from", () => {
    const { container } = render(
      <VersionListItem
        entry={entry}
        isSelected={false}
        isAnimating={false}
        compareMode
        isCompareBase
        onSelect={jest.fn()}
        onCompareClick={jest.fn()}
        onExport={jest.fn()}
        onDeleteClick={jest.fn()}
      />,
    );

    expect(container.querySelector("li")?.className).toContain(
      "pointer-events-none",
    );
  });
});
