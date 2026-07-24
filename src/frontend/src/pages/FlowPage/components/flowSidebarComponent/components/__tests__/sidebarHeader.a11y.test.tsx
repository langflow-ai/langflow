import { render, screen } from "@testing-library/react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import type { SidebarHeaderComponentProps } from "../../types";
import { SidebarHeaderComponent } from "../sidebarHeader";

// sidebarHeader.test.tsx mocks Button/ShadTooltip/sidebar/disclosure for
// interaction testing. This suite renders the real Button, ShadTooltip, and
// @/components/ui/sidebar primitives to check the actual DOM/ARIA output —
// child sections (FeatureToggles, SearchInput, SidebarFilterComponent) have
// their own a11y coverage, so they stay mocked here.
jest.mock("../featureTogglesComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="feature-toggles" />,
}));

jest.mock("../searchInput", () => ({
  SearchInput: () => <div data-testid="search-input" />,
}));

jest.mock("../sidebarFilterComponent", () => ({
  SidebarFilterComponent: () => <div data-testid="sidebar-filter" />,
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_NEW_SIDEBAR: false,
}));

// The global jest.setup.js mock for genericIconComponent only stubs the
// default export, not the named ForwardedIconComponent this component uses.
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
  ForwardedIconComponent: ({ name }: { name?: string }) => (
    <span data-testid={`icon-${name}`} aria-hidden="true" />
  ),
}));

const defaultProps: SidebarHeaderComponentProps = {
  showConfig: false,
  setShowConfig: jest.fn(),
  showBeta: false,
  setShowBeta: jest.fn(),
  showLegacy: false,
  setShowLegacy: jest.fn(),
  searchInputRef: { current: null },
  isInputFocused: false,
  search: "",
  handleInputFocus: jest.fn(),
  handleInputBlur: jest.fn(),
  handleInputChange: jest.fn(),
  filterName: "",
  filterDescription: "",
  resetFilters: jest.fn(),
};

const renderHeader = (props: Partial<SidebarHeaderComponentProps> = {}) =>
  render(
    <TooltipProvider>
      <SidebarProvider>
        <SidebarHeaderComponent {...defaultProps} {...props} />
      </SidebarProvider>
    </TooltipProvider>,
  );

describe("SidebarHeaderComponent accessibility (real Button/ShadTooltip/sidebar, unmocked)", () => {
  it("should_have_no_axe_violations when config is closed", async () => {
    const { container } = renderHeader();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations when config is open", async () => {
    const { container } = renderHeader({ showConfig: true });

    expect(await axe(container)).toHaveNoViolations();
  });

  it("names the settings trigger button", () => {
    renderHeader();

    expect(screen.getByTestId("sidebar-options-trigger")).toHaveAccessibleName(
      "Component settings",
    );
  });
});
