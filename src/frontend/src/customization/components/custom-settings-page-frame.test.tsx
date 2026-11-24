import { render, screen } from "@testing-library/react";
import CustomSettingsPageFrame from "./custom-settings-page-frame";

jest.mock("@/components/common/pageLayout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="settings-page-layout">{children}</div>
  ),
}));

jest.mock("@/components/core/sidebarComponent", () => ({
  __esModule: true,
  default: ({ items }: { items: Array<{ title: string }> }) => (
    <nav>
      {items.map((item) => (
        <span key={item.title}>{item.title}</span>
      ))}
    </nav>
  ),
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarProvider: ({ children }: { children: React.ReactNode }) => children,
}));

describe("CustomSettingsPageFrame", () => {
  it("preserves the community Settings list and content", () => {
    render(
      <CustomSettingsPageFrame
        title="Settings"
        description="Preferences"
        items={[{ title: "General", href: "/settings/general", icon: null }]}
      >
        <div>Settings content</div>
      </CustomSettingsPageFrame>,
    );

    expect(screen.getByTestId("settings-page-layout")).toBeInTheDocument();
    expect(screen.getByText("General")).toBeInTheDocument();
    const content = screen.getByText("Settings content");
    expect(content).toBeInTheDocument();
    expect(content.parentElement).toHaveClass("min-w-0", "overflow-x-clip");
    expect(content.parentElement?.parentElement).toHaveClass(
      "min-w-0",
      "overflow-x-clip",
    );
  });

  it("scrolls only the content so the header and the menu stay in view", () => {
    render(
      <CustomSettingsPageFrame
        title="Settings"
        description="Preferences"
        items={[{ title: "General", href: "/settings/general", icon: null }]}
      >
        <div>Settings content</div>
      </CustomSettingsPageFrame>,
    );

    const scroller = screen.getByTestId("settings-content-scroll");
    expect(scroller).toContainElement(screen.getByText("Settings content"));
    expect(scroller).toHaveClass("min-h-0", "overflow-y-auto");
    expect(scroller).not.toContainElement(screen.getByText("General"));
  });
});
