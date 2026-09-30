import { useTranslation } from "react-i18next";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import Loading from "@/components/ui/loading";
import { TableCell, TableRow } from "@/components/ui/table";
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";

interface DeploymentExpandedRowProps {
  deploymentId: string;
  colSpan: number;
}

export default function DeploymentExpandedRow({
  deploymentId,
  colSpan,
}: DeploymentExpandedRowProps) {
  const { t } = useTranslation();
  const { data, isLoading, isError } = useGetDeploymentAttachments({
    deploymentId,
  });

  const flows = data?.flow_versions ?? [];

  return (
    <TableRow className="hover:bg-transparent">
      <TableCell colSpan={colSpan} className="p-0">
        <div className="border-t bg-muted/30 px-8 py-3">
          {isLoading ? (
            <div className="flex items-center gap-2 py-2">
              <Loading size={14} className="text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                {t("deployments.loadingAttachedFlows")}
              </span>
            </div>
          ) : isError ? (
            <span className="text-sm text-destructive">
              {t("deployments.failedToLoadFlows")}
            </span>
          ) : flows.length === 0 ? (
            <span className="text-sm text-muted-foreground">
              {t("deployments.noFlowsAttached")}
            </span>
          ) : (
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                {t("deployments.attachedFlowsLabel")}
              </span>
              <div className="flex flex-wrap gap-2">
                {flows.map((flow) => (
                  <Badge
                    key={flow.id}
                    variant="secondaryStatic"
                    size="tag"
                    className="gap-1.5"
                  >
                    <ForwardedIconComponent
                      name="Workflow"
                      className="h-3 w-3 text-muted-foreground"
                    />
                    <span>{flow.flow_name ?? t("deployments.untitled")}</span>
                    <span className="text-muted-foreground">
                      v{flow.version_number}
                    </span>
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
