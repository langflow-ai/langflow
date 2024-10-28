import ForwardedIconComponent from "@/components/genericIconComponent";
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
import { NavProps } from "../../../../types/templates/types";

export function Nav({ categories, currentTab, setCurrentTab }: NavProps) {
  return (
    <Sidebar>
      <SidebarContent className="gap-0 p-2">
        {categories.map((category, index) => (
          <SidebarGroup key={index}>
            <SidebarGroupLabel
              className={`${
                index === 0
                  ? "mb-3 text-lg font-semibold leading-none tracking-tight text-primary"
                  : "mb-1 text-sm font-semibold text-muted-foreground"
              }`}
              data-testid={index === 0 ? "modal-title" : undefined}
            >
              {category.title}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {category.items.map((link) => (
                  <SidebarMenuItem key={link.id}>
                    <SidebarMenuButton
                      tabIndex={1}
                      variant="menu"
                      onClick={() => setCurrentTab(link.id)}
                      isActive={currentTab === link.id}
                      data-testid={`side_nav_options_${link.title.toLowerCase().replace(/\s+/g, "_")}`}
                    >
                      <ForwardedIconComponent
                        name={link.icon}
                        className={`mr-2 h-4 w-4 stroke-2 ${
                          currentTab === link.id
                            ? "x-gradient"
                            : "text-muted-foreground"
                        }`}
                      />
                      <span>{link.title}</span>
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
