import { render } from "@testing-library/react";
import { SidebarProvider } from "@/components/ui/sidebar";
import { axe } from "@/utils/a11y-test";
import SidebarSegmentedNav from "../sidebarSegmentedNav";

// sidebarSegmentedNav.test.tsx mocks @/components/ui/sidebar and ShadTooltip
// entirely for interaction testing. This suite renders the real sidebar
// primitives and ShadTooltip to check actual DOM/ARIA output.
const mockSetSearch = jest.fn();
jest.mock("../../index", () => ({
  useSearchContext: () => ({
    focusSearch: jest.fn(),
    isSearchFocused: false,
    setSearch: mockSetSearch,
  }),
}));

jest.mock("@/stores/playgroundStore", () => ({
  usePlaygroundStore: (selector: (state: Record<string, unknown>) => unknown) =>
    selector({ setIsOpen: jest.fn(), setIsFullscreen: jest.fn() }),
}));

const renderNav = () =>
  render(
    <SidebarProvider>
      <SidebarSegmentedNav />
    </SidebarProvider>,
  );

describe("SidebarSegmentedNav accessibility (real sidebar primitives/ShadTooltip, unmocked)", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = renderNav();

    expect(await axe(container)).toHaveNoViolations();
  });
});
