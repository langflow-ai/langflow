import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useGetDeployment } from "@/controllers/API/queries/deployments/use-get-deployment";
import { useGetDeploymentAttachments } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import useFlowStore from "@/stores/flowStore";
import { useFolderStore } from "@/stores/foldersStore";
import { DeploymentStepperProvider } from "../contexts/deployment-stepper-context";
import type { Deployment, DeploymentProvider, ProviderAccount } from "../types";
import DeploymentStepperModalContent from "./deployment-stepper-modal-content";

interface DeploymentStepperModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  onTestDeployment?: (
    deployment: { id: string; name: string },
    providerId: string,
  ) => void;
  initialFlowId?: string;
  initialVersionByFlow?: Map<string, { versionId: string; versionTag: string }>;
  initialProvider?: DeploymentProvider;
  initialInstance?: ProviderAccount;
  /** When provided, the modal opens in edit mode. */
  editingDeployment?: Deployment | null;
}

export default function DeploymentStepperModal({
  open,
  setOpen,
  onTestDeployment,
  initialFlowId,
  initialVersionByFlow,
  initialProvider,
  initialInstance,
  editingDeployment,
}: DeploymentStepperModalProps) {
  const [isDeploying, setIsDeploying] = useState(false);
  const isEditMode = !!editingDeployment;
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const currentFlowProjectId = useFlowStore(
    (state) => state.currentFlow?.folder_id,
  );
  const resolvedProjectId =
    currentFlowProjectId ?? folderId ?? myCollectionId ?? undefined;

  // Edit mode: fetch existing attachments and deployment detail for LLM.
  const { data: attachmentsData, isLoading: isLoadingAttachments } =
    useGetDeploymentAttachments(
      { deploymentId: editingDeployment?.id ?? "" },
      { enabled: open && isEditMode && !!editingDeployment?.id },
    );
  const { data: deploymentDetail, isLoading: isLoadingDetail } =
    useGetDeployment(
      { deploymentId: editingDeployment?.id ?? "" },
      { enabled: open && isEditMode && !!editingDeployment?.id },
    );

  // Build initial maps from attachments for the stepper context.
  // Tool names and connection assignments come from the provider (wxO) via
  // the /flows endpoint, NOT from the Langflow database. This means:
  //
  // - If a user renames a tool in the wxO console, the new name appears
  //   here on the next edit. Langflow doesn't cache tool names locally.
  // - If a tool is deleted in wxO, provider_data will be null and the
  //   review page falls back to the Langflow flow name.
  // - If a connection is deleted in wxO but the tool still references it,
  //   the app_id will appear in connectionsByFlow. The backend will fail
  //   fast during the update if the caller tries to attach a new tool to
  //   that stale connection.
  const editInitialState = useMemo(() => {
    if (!isEditMode || !attachmentsData?.flow_versions) return null;

    const versionMap = new Map<
      string,
      { versionId: string; versionTag: string }
    >();
    const toolNames = new Map<string, string>();
    const connectionsByFlow = new Map<string, string[]>();

    for (const fv of attachmentsData.flow_versions) {
      versionMap.set(fv.flow_id, {
        versionId: fv.id,
        versionTag: `v${fv.version_number}`,
      });
      // Pre-populate tool names from the provider (may differ from flow name).
      const providerToolName = fv.provider_data?.tool_name;
      if (providerToolName) {
        toolNames.set(fv.flow_id, providerToolName);
      }
      // Pre-populate attached connections from existing tool assignments.
      const appIds = fv.provider_data?.app_ids;
      if (appIds && appIds.length > 0) {
        connectionsByFlow.set(fv.flow_id, appIds);
      }
    }

    const llm =
      typeof deploymentDetail?.provider_data?.llm === "string"
        ? (deploymentDetail.provider_data.llm as string)
        : "";

    return { versionMap, llm, toolNames, connectionsByFlow };
  }, [isEditMode, attachmentsData, deploymentDetail]);

  const isLoadingEditData =
    isEditMode && (isLoadingAttachments || isLoadingDetail);

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value && isDeploying) return;
        setOpen(value);
      }}
    >
      <DialogContent
        className="flex h-[85vh] w-[900px] !max-w-none flex-col gap-0 overflow-hidden border-none bg-transparent p-0 shadow-none"
        closeButtonClassName="top-5 right-4"
        overlayClassName="bg-black/30 dark:bg-black/50 backdrop-blur"
      >
        {isLoadingEditData ? (
          <div className="flex flex-1 items-center justify-center">
            <span className="text-sm text-muted-foreground">
              Loading deployment data...
            </span>
          </div>
        ) : (
          <DeploymentStepperProvider
            key={`${open}-${editingDeployment?.id ?? ""}-${initialProvider?.id ?? ""}-${initialInstance?.id ?? ""}`}
            initialState={{
              projectId: resolvedProjectId,
              initialFlowId,
              selectedVersionByFlow:
                initialVersionByFlow ?? editInitialState?.versionMap,
              initialProvider,
              initialInstance,
              initialStep: isEditMode
                ? 1
                : initialProvider && initialInstance
                  ? 2
                  : 1,
              editingDeployment: editingDeployment ?? undefined,
              initialLlm: editInitialState?.llm,
              initialToolNameByFlow: editInitialState?.toolNames,
              initialConnectionsByFlow: editInitialState?.connectionsByFlow,
            }}
          >
            <DeploymentStepperModalContent
              setOpen={setOpen}
              onTestDeployment={onTestDeployment}
              onDeployingChange={setIsDeploying}
            />
          </DeploymentStepperProvider>
        )}
      </DialogContent>
    </Dialog>
  );
}
