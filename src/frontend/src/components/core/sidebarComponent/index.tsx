import { useLocation } from "react-router-dom";
import { CustomLink } from "@/customization/components/custom-link";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "../../ui/sidebar";

export type SidebarNavItem = {
  href?: string;
  title: string;
  icon: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
};
type SideBarButtonsComponentProps = {
  items: SidebarNavItem[];
  handleOpenNewFolderModal?: () => void;
};

const SideBarButtonsComponent = ({ items }: SideBarButtonsComponentProps) => {
  const location = useLocation();
  const pathname = location.pathname;

  const isMobile = useIsMobile();

  return (
    <Sidebar collapsible={isMobile ? "icon" : "none"} className="border-none">
      <SidebarContent className="pr-6">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item, index) => (
                <SidebarMenuItem key={index}>
                  {item.href ? (
                    <CustomLink to={item.href} replace>
                      <SidebarMenuButton
                        size="md"
                        isActive={pathname.endsWith(item.href)}
                        data-testid={`sidebar-nav-${item.title}`}
                        tooltip={item.title}
                      >
                        {item.icon}
                        <span className="block max-w-full truncate">
                          {item.title}
                        </span>
                      </SidebarMenuButton>
                    </CustomLink>
                  ) : (
                    <SidebarMenuButton
                      size="md"
                      onClick={item.onClick}
                      disabled={item.disabled}
                      data-testid={`sidebar-nav-${item.title}`}
                      tooltip={item.title}
                      className="disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {item.icon}
                      <span className="block max-w-full truncate">
                        {item.title}
                      </span>
                    </SidebarMenuButton>
                  )}
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
};

export default SideBarButtonsComponent;
