import { useState } from "react";
import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { SidebarMenuButton, useSidebar } from "@/components/ui/sidebar";
import { useIsFlowReadOnly } from "@/contexts/permissionsContext";
import { ENABLE_NEW_SIDEBAR } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import AddMcpServerModal from "@/modals/addMcpServerModal";
import useFlowStore from "@/stores/flowStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { cn } from "@/utils/utils";

const SidebarMenuButtons = ({
  customComponent,
  addComponent,
  isLoading = false,
}) => {
  const { t } = useTranslation();
  const { activeSection } = useSidebar();
  const [addMcpOpen, setAddMcpOpen] = useState(false);
  const navigate = useCustomNavigate();
  const allowCustomComponents = useUtilityStore(
    (state) => state.allowCustomComponents,
  );
  // Same flow id `useAddComponent` gates on, so the affordance and the gate
  // can never disagree about which flow is being evaluated.
  const currentFlowId = useFlowStore((state) => state.currentFlow?.id);
  const isFlowReadOnly = useIsFlowReadOnly(currentFlowId);

  // One flag for every reason the add is refused: the component types are
  // still loading, there is nothing to add yet, the permission answer is in
  // flight, or it denies write. Dimming only some of them would leave the
  // same control looking disabled for one cause and enabled for another,
  // which reads as a bug not a policy.
  const isUnavailable = isLoading || isFlowReadOnly || !customComponent;

  const handleAddMcpServerClick = () => {
    setAddMcpOpen(true);
  };

  // Hide custom component button when custom components are blocked
  if (
    !allowCustomComponents &&
    !(ENABLE_NEW_SIDEBAR && activeSection === "mcp")
  ) {
    return null;
  }

  return ENABLE_NEW_SIDEBAR && activeSection === "mcp" ? (
    <>
      <SidebarMenuButton asChild>
        <Button
          unstyled
          disabled={isLoading}
          onClick={handleAddMcpServerClick}
          data-testid="sidebar-add-mcp-server-button"
          className="flex items-center w-full h-full gap-3 hover:bg-muted"
        >
          <ForwardedIconComponent
            name="Plus"
            className="h-4 w-4 text-muted-foreground"
          />
          <ShadTooltip content={t("sidebar.mcp.add")} styleClasses="z-50">
            <span className="group-data-[state=open]/collapsible:font-semibold">
              {t("sidebar.mcp.add")}
            </span>
          </ShadTooltip>
        </Button>
      </SidebarMenuButton>
      <SidebarMenuButton asChild>
        <Button
          unstyled
          disabled={isLoading}
          onClick={() => {
            navigate("/settings/mcp-servers");
          }}
          data-testid="sidebar-manage-servers-button"
          className="flex items-center w-full h-full gap-3 hover:bg-muted"
        >
          <ForwardedIconComponent
            name="ArrowUpRight"
            className="h-4 w-4 text-muted-foreground"
          />
          <ShadTooltip content={t("sidebar.mcp.manage")} styleClasses="z-50">
            <span className="group-data-[state=open]/collapsible:font-semibold">
              {t("sidebar.mcp.manage")}
            </span>
          </ShadTooltip>
        </Button>
      </SidebarMenuButton>
      <AddMcpServerModal open={addMcpOpen} setOpen={setAddMcpOpen} />
    </>
  ) : (
    <SidebarMenuButton asChild className="group">
      <Button
        unstyled
        disabled={isUnavailable}
        onClick={() => {
          if (customComponent) {
            addComponent(customComponent, "CustomComponent");
          }
        }}
        data-testid="sidebar-custom-component-button"
        // `unstyled` opts out of the base class that carries
        // `disabled:opacity-70`, so the disabled look has to be spelled out
        // here — otherwise the control blocks the click while still looking
        // exactly like a working one, which is the defect being fixed.
        className={cn(
          "flex items-center w-full h-full gap-3 hover:bg-muted",
          isUnavailable && "cursor-not-allowed opacity-70",
        )}
      >
        <ForwardedIconComponent
          name="Plus"
          className="h-4 w-4 text-muted-foreground"
        />
        <ShadTooltip
          content={t("sidebar.newCustomComponent")}
          styleClasses="z-50"
        >
          <span className="group-data-[state=open]/collapsible:font-semibold">
            {t("sidebar.newCustomComponent")}
          </span>
        </ShadTooltip>
      </Button>
    </SidebarMenuButton>
  );
};

export default SidebarMenuButtons;
