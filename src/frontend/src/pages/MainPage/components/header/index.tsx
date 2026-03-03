import { useEffect } from "react";
import { ENABLE_DEPLOYMENTS, ENABLE_MCP } from "@/customization/feature-flags";
import HeaderTabs from "./components/HeaderTabs";
import HeaderTitle from "./components/HeaderTitle";
import { FlowType } from "./types";

const TAB_TYPES_MCP: FlowType[] = ["flows", "mcp", "deployments"];
const TAB_TYPES_DEFAULT: FlowType[] = ["flows", "components", "deployments"];

interface HeaderComponentProps {
  flowType: FlowType;
  setFlowType: (flowType: FlowType) => void;
  folderName?: string;
  isEmptyFolder: boolean;
}

const HeaderComponent = ({
  folderName = "",
  flowType,
  setFlowType,
  isEmptyFolder,
}: HeaderComponentProps) => {
  const isMCPEnabled = ENABLE_MCP;
  const rawTabTypes = isMCPEnabled ? TAB_TYPES_MCP : TAB_TYPES_DEFAULT;
  const tabTypes = ENABLE_DEPLOYMENTS
    ? rawTabTypes
    : rawTabTypes.filter((t) => t !== "deployments");

  useEffect(() => {
    if (
      (flowType === "mcp" && !isMCPEnabled) ||
      (flowType === "components" && isMCPEnabled) ||
      (flowType === "deployments" && !ENABLE_DEPLOYMENTS)
    ) {
      setFlowType("flows");
    }
  }, [flowType, isMCPEnabled, setFlowType]);

  return (
    <div className="bg-background pt-6">
      <div className="3xl:container">
        <HeaderTitle folderName={folderName} />
      </div>
      {!isEmptyFolder && (
        <HeaderTabs
          flowType={flowType}
          setFlowType={setFlowType}
          tabTypes={tabTypes}
        />
      )}
    </div>
  );
};

export default HeaderComponent;
