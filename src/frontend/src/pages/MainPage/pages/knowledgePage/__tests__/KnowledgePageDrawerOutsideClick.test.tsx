import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: ({ children }: { children?: React.ReactNode }) => (
    <button data-testid="sidebar-trigger">{children}</button>
  ),
}));

jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => jest.fn(),
}));

jest.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

jest.mock("../components/KnowledgeBaseDrawer", () => ({
  __esModule: true,
  default: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="knowledge-base-drawer">Drawer</div> : null,
}));

// biome-ignore lint/suspicious/noExplicitAny: legacy
let capturedOnRowClick: ((kb: any) => void) | null = null;
jest.mock("../components/KnowledgeBasesTab", () => ({
  __esModule: true,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  default: ({ onRowClick }: { onRowClick: (kb: any) => void }) => {
    capturedOnRowClick = onRowClick;
    return (
      <button
        data-testid="open-drawer"
        onClick={() => onRowClick({ name: "Test", dir_name: "test" })}
      >
        Open
      </button>
    );
  },
}));

import { KnowledgePage } from "../index";

const openDrawer = () => {
  fireEvent.click(screen.getByTestId("open-drawer"));
  expect(screen.getByTestId("knowledge-base-drawer")).toBeInTheDocument();
};

describe("KnowledgePage outside-click drawer dismissal", () => {
  beforeEach(() => {
    capturedOnRowClick = null;
    document.body.innerHTML = "";
  });

  it("keeps drawer open when mousedown lands on a Radix popper portal", () => {
    render(<KnowledgePage />);
    openDrawer();

    const portal = document.createElement("div");
    portal.setAttribute("data-radix-popper-content-wrapper", "");
    const menuItem = document.createElement("div");
    menuItem.setAttribute("role", "menuitem");
    menuItem.textContent = "View Chunks";
    portal.appendChild(menuItem);
    document.body.appendChild(portal);

    fireEvent.mouseDown(menuItem);

    expect(screen.getByTestId("knowledge-base-drawer")).toBeInTheDocument();
  });

  it("keeps drawer open when mousedown lands on a role=menu element", () => {
    render(<KnowledgePage />);
    openDrawer();

    const menu = document.createElement("div");
    menu.setAttribute("role", "menu");
    document.body.appendChild(menu);

    fireEvent.mouseDown(menu);

    expect(screen.getByTestId("knowledge-base-drawer")).toBeInTheDocument();
  });

  it("keeps drawer open when mousedown lands on a role=dialog element", () => {
    render(<KnowledgePage />);
    openDrawer();

    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    document.body.appendChild(dialog);

    fireEvent.mouseDown(dialog);

    expect(screen.getByTestId("knowledge-base-drawer")).toBeInTheDocument();
  });

  it("closes drawer when mousedown lands on a plain outside element", () => {
    render(<KnowledgePage />);
    openDrawer();

    const stray = document.createElement("div");
    document.body.appendChild(stray);

    fireEvent.mouseDown(stray);

    expect(
      screen.queryByTestId("knowledge-base-drawer"),
    ).not.toBeInTheDocument();
  });
});
