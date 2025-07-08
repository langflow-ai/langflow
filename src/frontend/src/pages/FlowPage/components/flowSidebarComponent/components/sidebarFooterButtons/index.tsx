import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { CustomLink } from "@/customization/components/custom-link";
import { ENABLE_LANGFLOW_STORE } from "@/customization/feature-flags";

const SidebarMenuButtons = ({
  hasStore = false,
  customComponent,
  addComponent,
  isLoading = false,
}) => {
  return (
    <>
      {/* TODO: Remove this on cleanup */}
      {ENABLE_LANGFLOW_STORE && hasStore && (
        <SidebarMenuButton asChild>
          <CustomLink
            to="/store"
            target="_blank"
            rel="noopener noreferrer"
            className="group/discover"
          >
            <div className="flex w-full items-center gap-2">
              <ForwardedIconComponent
                name="Store"
                className="text-muted-foreground h-4 w-4"
              />
              <span className="flex-1 group-data-[state=open]/collapsible:font-semibold">
                Discover more components
              </span>
              <ForwardedIconComponent
                name="SquareArrowOutUpRight"
                className="h-4 w-4 opacity-0 transition-all group-hover/discover:opacity-100"
              />
            </div>
          </CustomLink>
        </SidebarMenuButton>
      )}
      <SidebarMenuButton asChild>
        <Button
          unstyled
          disabled={isLoading}
          onClick={() => {
            if (customComponent) {
              addComponent(customComponent, "CustomComponent");
            }
          }}
          data-testid="sidebar-custom-component-button"
          className="flex items-center gap-2"
        >
          <ForwardedIconComponent
            name="Plus"
            className="text-muted-foreground h-4 w-4"
          />
          <span className="group-data-[state=open]/collapsible:font-semibold">
            New Custom Component
          </span>
        </Button>
      </SidebarMenuButton>
    </>
  );
};

export default SidebarMenuButtons;
