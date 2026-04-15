import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import Loading from "@/components/ui/loading";
import { useGetDeployment } from "@/controllers/API/queries/deployments/use-get-deployment";
import {
  type DeploymentFlowVersionItem,
  useGetDeploymentAttachments,
} from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import { useGetDeploymentConfigs } from "@/controllers/API/queries/deployments/use-get-deployment-configs";
import type { Deployment } from "../../types";
import DeploymentFlowList from "./deployment-flow-list";
import DeploymentInfoGrid from "./deployment-info-grid";

interface DeploymentDetailsModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  deployment: Deployment | null;
  providerName: string;
}

export default function DeploymentDetailsModal({
  open,
  setOpen,
  deployment,
  providerName,
}: DeploymentDetailsModalProps) {
  const deploymentId = deployment?.id ?? "";

  const { data: details, isFetching: isFetchingDetails } = useGetDeployment(
    { deploymentId },
    { enabled: open && !!deploymentId, refetchOnWindowFocus: false },
  );

  const { data: attachmentsData, isFetching: isFetchingAttachments } =
    useGetDeploymentAttachments(
      { deploymentId },
      { enabled: open && !!deploymentId, refetchOnWindowFocus: false },
    );

  const providerId = details?.provider_id ?? deployment?.provider_id ?? "";

  const { data: configsData, isFetching: isFetchingConfigs } =
    useGetDeploymentConfigs(
      { providerId },
      { enabled: open && !!providerId, refetchOnWindowFocus: false },
    );

  const isLoading =
    isFetchingDetails || isFetchingAttachments || isFetchingConfigs;

  const deploymentData = details?.id === deploymentId ? details : deployment;
  const flowVersions = attachmentsData?.flow_versions ?? [];

  const llm =
    typeof deploymentData?.provider_data?.llm === "string"
      ? deploymentData.provider_data.llm
      : "";

  const configAppIds = useMemo(
    () => new Set((configsData?.configs ?? []).map((cfg) => cfg.app_id)),
    [configsData],
  );

  const getConnectionNames = (fv: DeploymentFlowVersionItem): string[] => {
    const appIds = fv.provider_data?.app_ids ?? [];
    return appIds.filter((id) => id && configAppIds.has(id));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="flex w-[700px] !max-w-none flex-col gap-0 overflow-hidden rounded-xl border bg-background p-0 shadow-lg">
        <div className="flex flex-col items-start border-b px-6 py-4">
          <DialogTitle className="text-lg font-semibold">
            Deployment Details
          </DialogTitle>
          <DialogDescription className="text-sm text-muted-foreground">
            View deployment configuration and attached flows.
          </DialogDescription>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loading />
          </div>
        ) : (
          <div className="flex flex-col gap-5 overflow-y-auto px-6 py-4">
            <DeploymentInfoGrid
              deployment={deploymentData}
              providerName={providerName}
              llm={llm}
            />

            <div className="border-t border-border" />

            <DeploymentFlowList
              flowVersions={flowVersions}
              getConnectionNames={getConnectionNames}
            />
          </div>
        )}

        <div className="flex justify-end border-t px-6 py-4">
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            data-testid="deployment-details-close"
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
