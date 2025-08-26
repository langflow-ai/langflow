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
    <div>
      <ShadTooltip content="Component settings" styleClasses="z-50">
        <Button
          variant={showConfig ? "ghostActive" : "ghost"}
          size="iconMd"
          data-testid="sidebar-options-trigger"
          onClick={() => setShowConfig(!showConfig)}
        >
          <ForwardedIconComponent
            name="SlidersHorizontal"
            className="h-4 w-4"
          />
        </Button>
      </ShadTooltip>
    </div>
  );
};
