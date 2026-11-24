import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const location = useLocation();
  const pathname = location.pathname;

  const isMobile = useIsMobile();

  return (
    <Sidebar
      collapsible={isMobile ? "icon" : "none"}
      className="border-none"
      role="navigation"
      aria-label={t("settings.nav.label")}
    >
      <SidebarContent className="pr-6">
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item, index) => (
                <SidebarMenuItem key={index}>
                  <SidebarMenuButton
                    asChild
                    size="md"
                    // Longer translations wrap onto a second line instead of
                    // being cut off.
                    className="h-auto min-h-9 py-2"
                    isActive={item.href ? pathname.endsWith(item.href) : false}
                    tooltip={item.title}
                  >
                    <CustomLink
                      to={item.href!}
                      replace
                      data-testid={`sidebar-nav-${item.title}`}
                    >
                      {item.icon}
                      {/* A div, not a span: the menu button truncates its last
                          span child, which cut "Chaves de API do Langflow". */}
                      <div className="min-w-0 break-words leading-tight">
                        {item.title}
                      </div>
                    </CustomLink>
                  </SidebarMenuButton>
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
