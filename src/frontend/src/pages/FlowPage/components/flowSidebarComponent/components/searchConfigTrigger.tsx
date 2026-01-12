import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";

interface SearchConfigTriggerProps {
  showConfig: boolean;
  setShowConfig: (show: boolean) => void;
}

export const SearchConfigTrigger = ({
  showConfig,
  setShowConfig,
}: SearchConfigTriggerProps) => {
  return (
    <div className="flex items-center justify-center">
      <ShadTooltip content="Component settings" styleClasses="z-50">
        <Button
          variant={showConfig ? "ghostActive" : "ghost"}
          size="iconMd"
          data-testid="sidebar-options-trigger"
          onClick={() => setShowConfig(!showConfig)}
          className="hover:text-primary text-muted-foreground"
          style={{ padding: "0px" }}
        >
          <ForwardedIconComponent name="Settings2" className="h-4 w-4" />
        </Button>
      </ShadTooltip>
    </div>
  );
};
