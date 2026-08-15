import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from "../sidebar";

// SidebarProvider persists open/section state in document.cookie, which would
// otherwise leak between test cases.
beforeEach(() => {
  for (const cookie of document.cookie.split(";")) {
    const name = cookie.split("=")[0]?.trim();
    if (name) {
      document.cookie = `${name}=; max-age=0; path=/`;
    }
  }
});

type SidebarShellProps = {
  defaultOpen?: boolean;
  /** Landmark wiring under test: `nav` vs `aside` vs neither. */
  landmark?: "navigation" | "complementary" | "none";
};

const renderSidebar = ({
  defaultOpen = true,
  landmark = "complementary",
}: SidebarShellProps = {}) => {
  const landmarkProps =
    landmark === "navigation"
      ? ({ role: "navigation", "aria-label": "Flow sections" } as const)
      : landmark === "complementary"
        ? ({ "aria-label": "Flow sections" } as const)
        : ({} as const);

  return render(
    <SidebarProvider defaultOpen={defaultOpen}>
      <Sidebar collapsible="none" {...landmarkProps}>
        <SidebarHeader>
          <SidebarInput aria-label="Search components" placeholder="Search…" />
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Inputs</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton isActive>Chat Input</SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton>Text Input</SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter>
          <SidebarTrigger />
        </SidebarFooter>
      </Sidebar>
    </SidebarProvider>,
  );
};

describe("Sidebar accessibility", () => {
  it("should_have_no_axe_violations_when_expanded", async () => {
    const { container } = renderSidebar();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_as_a_navigation_landmark", async () => {
    const { container } = renderSidebar({ landmark: "navigation" });

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_have_no_axe_violations_when_collapsed", async () => {
    const { container } = render(
      <SidebarProvider defaultOpen={false}>
        <Sidebar collapsible="icon" aria-label="Flow sections">
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Inputs</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton>Chat Input</SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_a_named_complementary_landmark_when_given_a_label", () => {
    renderSidebar({ landmark: "complementary" });

    // A labelled Sidebar renders <aside>, so assistive tech can jump to it and
    // hear which sidebar it is (WCAG 1.3.1 / 2.4.1).
    expect(
      screen.getByRole("complementary", { name: "Flow sections" }),
    ).toBeInTheDocument();
  });

  it("should_expose_a_named_navigation_landmark_when_given_that_role", () => {
    renderSidebar({ landmark: "navigation" });

    expect(
      screen.getByRole("navigation", { name: "Flow sections" }),
    ).toBeInTheDocument();
  });

  it("should_not_emit_an_unnamed_landmark_without_a_label", () => {
    renderSidebar({ landmark: "none" });

    // An unlabelled sidebar deliberately renders a plain <div>: a nameless
    // landmark is worse than no landmark, because it clutters the landmark
    // list with an unidentifiable entry.
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("should_give_the_trigger_an_accessible_name_from_its_icon_fallback", () => {
    renderSidebar();

    // The PanelLeft icon is aria-hidden, so the trigger falls back to an
    // sr-only label rather than shipping an unnamed icon button (WCAG 4.1.2).
    expect(
      screen.getByRole("button", { name: /toggle sidebar/i }),
    ).toBeInTheDocument();
  });

  it("should_prefer_a_caller_supplied_trigger_label", () => {
    render(
      <SidebarProvider defaultOpen>
        <SidebarTrigger aria-label="Collapse component panel" />
      </SidebarProvider>,
    );

    expect(
      screen.getByRole("button", { name: "Collapse component panel" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /toggle sidebar/i }),
    ).not.toBeInTheDocument();
  });

  it("should_toggle_the_sidebar_from_the_keyboard", async () => {
    const user = userEvent.setup();
    render(
      <SidebarProvider defaultOpen>
        <Sidebar collapsible="icon" aria-label="Flow sections">
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Inputs</SidebarGroupLabel>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
        <SidebarTrigger />
      </SidebarProvider>,
    );

    const sidebar = screen.getByRole("complementary", {
      name: "Flow sections",
    });
    expect(sidebar).toHaveAttribute("data-state", "expanded");

    // WCAG 2.1.1: the trigger must be operable without a pointer.
    await user.tab();
    const trigger = screen.getByRole("button", { name: /toggle sidebar/i });
    expect(trigger).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(sidebar).toHaveAttribute("data-state", "collapsed");
  });

  it("should_mark_the_active_menu_button", () => {
    renderSidebar();

    expect(screen.getByRole("button", { name: "Chat Input" })).toHaveAttribute(
      "data-active",
      "true",
    );
    expect(screen.getByRole("button", { name: "Text Input" })).toHaveAttribute(
      "data-active",
      "false",
    );
  });

  it("should_name_the_sidebar_search_input", () => {
    renderSidebar();

    expect(
      screen.getByRole("textbox", { name: "Search components" }),
    ).toBeInTheDocument();
  });
});
