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

type SideBarButtonsComponentProps = {
  items: {
    href?: string;
    title: string;
    icon: React.ReactNode;
  }[];
  handleOpenNewFolderModal?: () => void;
};

const SideBarButtonsComponent = ({ items }: SideBarButtonsComponentProps) => {
  const location = useLocation();
  const pathname = location.pathname;

  const isMobile = useIsMobile();

  return (
    <Sidebar
      collapsible={isMobile ? "icon" : "none"}
      className="border border-primary-border p-4 rounded-lg shadow-[0_1px_8px_0_rgba(var(--boxshadow),0.1)] mr-4"
    >
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item, index) => (
                <SidebarMenuItem key={index}>
                  <CustomLink to={item.href!} replace>
                    <SidebarMenuButton
                      size="md"
                      isActive={
                        item.href ? pathname.endsWith(item.href) : false
                      }
                      data-testid={`sidebar-nav-${item.title}`}
                      tooltip={item.title}
                    >
                      <span>{item.icon}</span>
                      <span className="block max-w-full truncate">
                        {item.title}
                      </span>
                    </SidebarMenuButton>
                  </CustomLink>
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
