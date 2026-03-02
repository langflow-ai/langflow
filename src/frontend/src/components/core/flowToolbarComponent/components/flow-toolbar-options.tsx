import { useState } from "react";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useFlowDeploymentStatus } from "@/hooks/flows/use-flow-deployment-status";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useHistoryPreviewStore from "@/stores/historyPreviewStore";
import PublishDropdown from "./deploy-dropdown";
import FlowDeployModal from "./flow-deploy-modal";
import PlaygroundButton from "./playground-button";

type FlowToolbarOptionsProps = {
  openApiModal: boolean;
  setOpenApiModal: (open: boolean | ((prev: boolean) => boolean)) => void;
};
const FlowToolbarOptions = ({
  openApiModal,
  setOpenApiModal,
}: FlowToolbarOptionsProps) => {
  const hasIO = useFlowStore((state) => state.hasIO);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const previewId = useHistoryPreviewStore((state) => state.previewId);
  const [openDeployModal, setOpenDeployModal] = useState(false);
  const { toolbarStatus } = useFlowDeploymentStatus({
    flowId: currentFlow?.id,
    selectedEntryId: previewId,
  });

  const statusLabelMap = {
    loading: "Checking...",
    deployed: "Deployed",
    changes_not_deployed: "Changes not deployed",
    not_deployed: "Not deployed",
  } as const;

  const statusClassMap = {
    loading: "border-border text-muted-foreground",
    deployed:
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    changes_not_deployed:
      "border-yellow-500/30 bg-yellow-500/10 text-yellow-700 dark:text-yellow-400",
    not_deployed: "border-border text-muted-foreground",
  } as const;

  return (
    <>
      <div className="flex items-center gap-1">
        <PlaygroundButton hasIO={hasIO} />
        <PublishDropdown
          openApiModal={openApiModal}
          setOpenApiModal={setOpenApiModal}
        />
        <Badge
          variant="outline"
          className={`h-8 rounded-md px-2.5 text-xs font-medium ${statusClassMap[toolbarStatus]}`}
        >
          {statusLabelMap[toolbarStatus]}
        </Badge>
        <Button
          variant="secondary"
          size="md"
          className="!px-2.5 font-normal"
          onClick={() => setOpenDeployModal(true)}
          data-testid="deploy-button"
        >
          Deploy
          <IconComponent name="EllipsisVertical" className="!h-4 !w-4" />
        </Button>
      </div>
      {currentFlow?.id && (
        <FlowDeployModal
          open={openDeployModal}
          onOpenChange={setOpenDeployModal}
          flowId={currentFlow.id}
          flowName={currentFlow.name || "Untitled Flow"}
        />
      )}
    </>
  );
};

export default FlowToolbarOptions;
