import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import type { FlowVersionEntry } from "@/types/flow/version";
import VersionListItem from "../components/VersionListItem";

jest.mock("@/components/ui/sidebar", () => ({
  SidebarMenuItem: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  SidebarMenuButton: ({
    children,
    onClick,
  }: {
    children: ReactNode;
    onClick: () => void;
  }) => (
    <div role="button" onClick={onClick}>
      {children}
    </div>
  ),
}));

// Shows the tooltip text inline, so a test can read it without hovering.
jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({
    content,
    children,
  }: {
    content: string;
    children: ReactNode;
  }) => <span data-tooltip={content}>{children}</span>,
}));

const baseEntry: FlowVersionEntry = {
  id: "v1",
  flow_id: "f1",
  user_id: "u1",
  version_number: 1,
  version_tag: "v1",
  description: null,
  created_at: "2026-11-20T10:00:00Z",
};

function renderItem(entry: FlowVersionEntry) {
  const onDeleteClick = jest.fn();
  render(
    <VersionListItem
      entry={entry}
      isSelected={false}
      isAnimating={false}
      onSelect={jest.fn()}
      onExport={jest.fn()}
      onDeleteClick={onDeleteClick}
    />,
  );
  return { onDeleteClick };
}

async function openMenu() {
  await userEvent.click(screen.getByTitle("More options"));
  return screen.findByTestId("version-delete-item");
}

describe("VersionListItem", () => {
  it("shows no badge and lets the user delete an unretained version", async () => {
    const { onDeleteClick } = renderItem(baseEntry);

    expect(screen.queryByTestId("version-protected-badge")).toBeNull();
    await userEvent.click(await openMenu());

    expect(onDeleteClick).toHaveBeenCalledWith(baseEntry);
  });

  it("marks a retained version Protected and blocks its Delete", async () => {
    const entry = {
      ...baseEntry,
      retained: true,
      retained_reason: "A deployment ships this version or is about to",
    };
    const { onDeleteClick } = renderItem(entry);
    const reason =
      "A deployment ships this version or is about to. This version can't be deleted.";

    const badge = screen.getByTestId("version-protected-badge");
    expect(badge).toHaveTextContent("Protected");
    expect(screen.getByText(reason)).toHaveClass("sr-only");
    expect(badge.closest("[data-tooltip]")).toHaveAttribute(
      "data-tooltip",
      reason,
    );

    const deleteItem = await openMenu();
    expect(deleteItem).toHaveAttribute("data-disabled");
    expect(deleteItem.closest("[data-tooltip]")).toHaveAttribute(
      "data-tooltip",
      reason,
    );
    await userEvent.click(deleteItem, { pointerEventsCheck: 0 });
    expect(onDeleteClick).not.toHaveBeenCalled();
  });
});
