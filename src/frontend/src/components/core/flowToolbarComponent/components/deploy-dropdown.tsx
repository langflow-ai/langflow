import { useState } from "react";
import { useHref } from "react-router-dom";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltipComponent from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import { usePatchUpdateFlow } from "@/controllers/API/queries/flows/use-patch-update-flow";
import { useDownloadYaml } from "@/controllers/API/queries/flows/use-download-yaml";
import { useCheckFlowPublished } from "@/controllers/API/queries/published-flows";
import { useGetFlowLatestStatus } from "@/controllers/API/queries/flow-versions";
import { CustomLink } from "@/customization/components/custom-link";
import { ENABLE_PUBLISH, ENABLE_WIDGET } from "@/customization/feature-flags";
import { customMcpOpen } from "@/customization/utils/custom-mcp-open";
import ApiModal from "@/modals/apiModal";
import EmbedModal from "@/modals/EmbedModal/embed-modal";
import ExportModal from "@/modals/exportModal";
import PublishFlowModal from "@/modals/publishFlowModal";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { cn } from "@/utils/utils";
import FlowSettingsModal from "@/modals/flowSettingsModal";

export default function PublishDropdown() {
  const location = useHref("/");
  const domain = window.location.origin + location;
  const [openEmbedModal, setOpenEmbedModal] = useState(false);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flowId = currentFlow?.id;
  const flowName = currentFlow?.name;
  const folderId = currentFlow?.folder_id;
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync } = usePatchUpdateFlow();
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const isPublished = currentFlow?.access_type === "PUBLIC";
  const hasIO = useFlowStore((state) => state.hasIO);
  const isAuth = useAuthStore((state) => !!state.autoLogin);
  const userData = useAuthStore((state) => state.userData);
  const [openApiModal, setOpenApiModal] = useState(false);
  const [publishAgent, setPublishModal] = useState(false);
  const [openExportModal, setOpenExportModal] = useState(false);
  const [openPublishFlowModal, setOpenPublishFlowModal] = useState(false);

  // Check if flow is published to marketplace
  const { data: publishCheck } = useCheckFlowPublished(flowId);

  // Check flow approval status for Publish to Marketplace button
  const { data: flowStatusData } = useGetFlowLatestStatus(flowId);
  const latestStatus = flowStatusData?.latest_status;
  const isUnderReview = latestStatus === "Submitted";
  const isApproved = latestStatus === "Approved";

  // Check if current user is the flow owner
  // Get user_id from flowStore (working state) as it has the complete flow data
  const flowUserId = useFlowStore((state) => state.currentFlow?.user_id);
  const isFlowOwner = flowUserId && userData?.id && flowUserId === userData.id;

  // Download YAML mutation
  const { mutate: downloadYaml, isPending: isDownloadingYaml } =
    useDownloadYaml({
      onSuccess: () => {
        // No need to show success message as the file download is self-evident
      },
      onError: (error) => {
        setErrorData({
          title: "Failed to download YAML",
          list: [(error as Error).message],
        });
      },
    });
  const isPublishedToMarketplace = publishCheck?.is_published;

  const handlePublishedSwitch = async (checked: boolean) => {
    mutateAsync(
      {
        id: flowId ?? "",
        access_type: checked ? "PRIVATE" : "PUBLIC",
      },
      {
        onSuccess: (updatedFlow) => {
          if (flows) {
            setFlows(
              flows.map((flow) => {
                if (flow.id === updatedFlow.id) {
                  return updatedFlow;
                }
                return flow;
              })
            );
            setCurrentFlow(updatedFlow);
          } else {
            // If flows array is not available, just update the current flow
            // This can happen when loading flows directly via URL
            setCurrentFlow(updatedFlow);
          }
        },
        onError: (e) => {
          setErrorData({
            title: "Failed to save flow",
            list: [e.message],
          });
        },
      }
    );
  };

  const handleExportYaml = () => {
    if (!flowId) {
      setErrorData({
        title: "Export failed",
        list: ["No flow selected"],
      });
      return;
    }
    downloadYaml({ flowId });
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="md"
            className="!px-2.5"
            data-testid="publish-button"
          >
            Share
            <IconComponent name="ChevronDown" className="!h-5 !w-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          forceMount
          sideOffset={7}
          alignOffset={-2}
          align="end"
          className="w-full min-w-[275px]"
        >
          {/* Publish to Marketplace - only show if user is flow owner */}
          {/* {isFlowOwner && (
            <DropdownMenuItem
              className="deploy-dropdown-item group"
              onClick={() => setOpenPublishFlowModal(true)}
              disabled={isUnderReview}
            >
              <IconComponent name="Upload" className={`icon-size mr-2`} />
              <span>
                {isPublishedToMarketplace
                  ? "Published to Marketplace"
                  : isApproved
                  ? "Publish to Marketplace (Approved)"
                  : "Publish to Marketplace"}
              </span>
            </DropdownMenuItem>
          )} */}
          <DropdownMenuItem
            className=""
            onClick={() => setOpenApiModal(true)}
            data-testid="api-access-item"
          >
            <IconComponent name="Code2" className={`icon-size mr-2`} />
            <span>API access</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            className=""
            onClick={() => setOpenExportModal(true)}
          >
            <IconComponent name="Download" className={`icon-size mr-2`} />
            <span>Export</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            className=""
            onClick={handleExportYaml}
            disabled={isDownloadingYaml || !flowId}
          >
            <IconComponent name="FileText" className={`icon-size mr-2`} />
            <span>
              {isDownloadingYaml ? "Downloading..." : "Export Specification"}
            </span>
          </DropdownMenuItem>
          <CustomLink
            className={cn("flex-1")}
            to={`/mcp/folder/${folderId}`}
            target={customMcpOpen()}
          >
            <DropdownMenuItem
              className=""
              onClick={() => {}}
              data-testid="mcp-server-item"
            >
              <IconComponent name="Mcp" className={`icon-size mr-2`} />
              <span>MCP Server</span>
              <IconComponent
                name="ExternalLink"
                className={`icon-size ml-auto hidden group-hover:block`}
              />
            </DropdownMenuItem>
          </CustomLink>
          {ENABLE_WIDGET && (
            <DropdownMenuItem
              onClick={() => setOpenEmbedModal(true)}
              className=""
            >
              <IconComponent name="Columns2" className={`icon-size mr-2`} />
              <span>Embed into site</span>
            </DropdownMenuItem>
          )}

          {/* Shareable Playground section has been removed */}
        </DropdownMenuContent>
      </DropdownMenu>
      <ApiModal open={openApiModal} setOpen={setOpenApiModal}>
        <></>
      </ApiModal>
      <EmbedModal
        open={openEmbedModal}
        setOpen={setOpenEmbedModal}
        flowId={flowId ?? ""}
        flowName={flowName ?? ""}
        isAuth={isAuth}
        tweaksBuildedObject={{}}
        activeTweaks={false}
      ></EmbedModal>
      <ExportModal open={openExportModal} setOpen={setOpenExportModal} />
      <FlowSettingsModal
        open={publishAgent}
        setOpen={setPublishModal}
        flowData={currentFlow}
        isPublishMode={true}
      />
      <PublishFlowModal
        open={openPublishFlowModal}
        setOpen={setOpenPublishFlowModal}
        flowId={flowId ?? ""}
        flowName={flowName ?? ""}
        existingPublishedData={publishCheck}
      />
    </>
  );
}
