import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { convertTestName } from "@/components/common/storeCardComponent/utils/convert-test-name";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { cn } from "@/utils/utils";
import { useIsMobile } from "../../../../hooks/use-mobile";
import type { NavProps } from "../../../../types/templates/types";

export function Nav({ categories, currentTab, setCurrentTab }: NavProps) {
  const isMobile = useIsMobile();

  return (
    <Sidebar collapsible={isMobile ? "icon" : "none"} className="max-w-[230px]">
      <SidebarContent className="gap-0">
        <p
          className={cn("text-primary-font font-bold text-lg mb-6")}
          data-testid="modal-title"
        >
          Templates
        </p>

        {categories.map((category, index) => (
          <SidebarGroup key={index}>
            <SidebarGroupLabel
              className={`${
                index === 0
                  ? "hidden"
                  : "my-3 text-sm font-semibold text-primary-font"
              }`}
            >
              {category.title}
            </SidebarGroupLabel>
            <SidebarGroupContent className="last:overflow-auto">
              <SidebarMenu>
                {category.items.map((link) => (
                  <SidebarMenuItem key={link.id}>
                    <SidebarMenuButton
                      onClick={() => setCurrentTab(link.id)}
                      isActive={currentTab === link.id}
                      data-testid={`side_nav_options_${link.title
                        .toLowerCase()
                        .replace(/\s+/g, "-")}`}
                      tooltip={link.title}
                    >
                      {/* <ForwardedIconComponent
                        name={link.icon}
                        className={`h-4 w-4 stroke-2 ${
                          currentTab === link.id
                            ? "text-accent-pink-foreground"
                            : "text-muted-foreground"
                        }`}
                      /> */}
                      <span
                        data-testid={`category_title_${convertTestName(
                          link.title
                        )}`}
                      >
                        {link.title}
                      </span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
    </Sidebar>
  );
}
