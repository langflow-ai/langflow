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
    expect(screen.getByText("Settings content")).toBeInTheDocument();
  });
});
