import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
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
    <nav aria-label="Desktop settings">
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
  it("preserves the community Settings list and content and supports mobile navigation", async () => {
    render(
      <CustomSettingsPageFrame
        title="Settings"
        description="Preferences"
        items={[{ title: "General", href: "/settings/general", icon: null }]}
      >
        <div>Settings content</div>
      </CustomSettingsPageFrame>,
      { wrapper: MemoryRouter },
    );

    expect(screen.getByTestId("settings-page-layout")).toBeInTheDocument();
    const desktop = screen.getByRole("navigation", {
      name: "Desktop settings",
    });
    expect(within(desktop).getByText("General")).toBeInTheDocument();
    const mobile = screen.getByRole("combobox");
    await userEvent.selectOptions(mobile, "/settings/general");
    expect(mobile).toHaveValue("/settings/general");
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
      { wrapper: MemoryRouter },
    );

    const scroller = screen.getByTestId("settings-content-scroll");
    expect(scroller).toContainElement(screen.getByText("Settings content"));
    expect(scroller).toHaveClass("min-h-0", "overflow-y-auto");
    expect(scroller).not.toContainElement(
      screen.getByRole("navigation", { name: "Desktop settings" }),
    );
  });
});
