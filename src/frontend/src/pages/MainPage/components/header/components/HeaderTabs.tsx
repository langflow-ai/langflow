import { Button } from "@/components/ui/button";
import { FlowType } from "../types";

const getTabLabel = (type: string): string => {
  if (type === "mcp") return "MCP Server";
  return type.charAt(0).toUpperCase() + type.slice(1);
};

interface HeaderTabsProps {
  flowType: FlowType;
  setFlowType: (flowType: FlowType) => void;
  tabTypes: string[];
}

const HeaderTabs = ({ flowType, setFlowType, tabTypes }: HeaderTabsProps) => (
  <div className="flex flex-row-reverse">
    <div className="w-full border-b dark:border-border" />
    {tabTypes.map((type) => (
      <Button
        key={type}
        unstyled
        id={`${type}-btn`}
        data-testid={`${type}-btn`}
        onClick={() => setFlowType(type as FlowType)}
        className={`border-b ${
          flowType === type
            ? "border-b-2 border-foreground text-foreground"
            : "border-border text-muted-foreground hover:text-foreground"
        } text-nowrap px-2 pb-2 pt-1 text-mmd`}
      >
        <span className="flex flex-col items-center overflow-hidden">
          <span
            aria-hidden
            className="invisible h-0 overflow-hidden font-semibold"
          >
            {getTabLabel(type)}
          </span>
          <span className={flowType === type ? "font-semibold" : ""}>
            {getTabLabel(type)}
          </span>
        </span>
      </Button>
    ))}
  </div>
);

export default HeaderTabs;
