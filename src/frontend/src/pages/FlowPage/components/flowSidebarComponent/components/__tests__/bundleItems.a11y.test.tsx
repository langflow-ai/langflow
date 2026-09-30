import { render } from "@testing-library/react";
import { SidebarMenu, SidebarProvider } from "@/components/ui/sidebar";
import type { BundleItemProps } from "@/pages/FlowPage/components/flowSidebarComponent/types";
import { axe } from "@/utils/a11y-test";
import { BundleItem } from "../bundleItems";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("../sidebarItemsList", () => ({
  __esModule: true,
  default: () => <div>items</div>,
}));

jest.mock("../bundleHeaderActions", () => ({
  __esModule: true,
  default: () => <div>actions</div>,
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: jest.fn((selector) =>
    selector ? selector({ enableExtensionReload: false }) : false,
  ),
}));

const defaultProps = {
  item: {
    name: "openai",
    display_name: "OpenAI",
    icon: "OpenAI",
  },
  openCategories: [],
  setOpenCategories: jest.fn(),
  dataFilter: {
    openai: {
      TestComponent: {
        description: "Test component",
        template: {},
        display_name: "Test Component",
        documentation: "Test docs",
      },
    },
  },
  nodeColors: {},
  onDragStart: jest.fn(),
  sensitiveSort: jest.fn(),
  handleKeyDownInput: jest.fn(),
} as unknown as BundleItemProps;

function renderInSidebar() {
  return render(
    <SidebarProvider>
      <SidebarMenu>
        <BundleItem {...defaultProps} />
      </SidebarMenu>
    </SidebarProvider>,
  );
}

describe("BundleItem list structure accessibility", () => {
  it("should_render_li_as_the_direct_child_of_the_sidebar_menu_ul", () => {
    const { container } = renderInSidebar();

    const ul = container.querySelector("ul");
    expect(ul).not.toBeNull();
    // Regression guard: a <div> wrapper (from Disclosure) must not sit
    // directly between the <ul> and its <li>, which axe's "list" rule flags.
    expect(ul!.children).toHaveLength(1);
    expect(ul!.children[0].tagName).toBe("LI");
  });

  it("should_have_no_axe_list_violations", async () => {
    const { container } = renderInSidebar();

    expect(await axe(container)).toHaveNoViolations();
  });
});
