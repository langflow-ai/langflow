import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton } from "@/components/ui/sidebar";
import { CustomLink } from "@/customization/components/custom-link";
import React from "react";

const SidebarMenuButtons = ({
  hasStore = false,
  customComponent,
  addComponent,
}) => {
  return (
    <>
      {hasStore && (
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
                className="h-4 w-4 text-muted-foreground"
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
            className="h-4 w-4 text-muted-foreground"
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
