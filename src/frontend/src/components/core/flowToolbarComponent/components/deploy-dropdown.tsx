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
import { CustomLink } from "@/customization/components/custom-link";
import { ENABLE_PUBLISH, ENABLE_WIDGET } from "@/customization/feature-flags";
import { customMcpOpen } from "@/customization/utils/custom-mcp-open";
import ApiModal from "@/modals/apiModal/new-api-modal";
import EmbedModal from "@/modals/EmbedModal/embed-modal";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { cn } from "@/utils/utils";
import { useState } from "react";
import { useHref } from "react-router-dom";

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
  const [openApiModal, setOpenApiModal] = useState(false);

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
              }),
            );
            setCurrentFlow(updatedFlow);
          } else {
            setErrorData({
              title: "Failed to save flow",
              list: ["Flows variable undefined"],
            });
          }
        },
        onError: (e) => {
          setErrorData({
            title: "Failed to save flow",
            list: [e.message],
          });
        },
      },
    );
  };

  // using js const instead of applies.css because of group tag
  const groupStyle = "text-muted-foreground group-hover:text-foreground";
  const externalUrlStyle =
    "opacity-0 transition-all duration-300 group-hover:translate-x-3 group-hover:opacity-100 group-focus-visible:translate-x-3 group-focus-visible:opacity-100";

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="md"
            className="!px-2.5 font-medium"
            data-testid="publish-button"
          >
            Share
            <IconComponent name="ChevronDown" className="!h-5 !w-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          forceMount
          sideOffset={10}
          alignOffset={-10}
          align="end"
          className="min-w-[300px] max-w-[400px]"
        >
          <DropdownMenuItem
            className="deploy-dropdown-item group"
            onClick={() => setOpenApiModal(true)}
          >
            <div
              className="group-hover:bg-accent"
              data-testid="api-access-item"
            >
              <IconComponent
                name="Code2"
                className={`${groupStyle} icon-size mr-2`}
              />
              <span>API access</span>
            </div>
          </DropdownMenuItem>
          <CustomLink
            className={cn("flex-1")}
            to={`/mcp/folder/${folderId}`}
            target={customMcpOpen()}
          >
            <DropdownMenuItem
              className="deploy-dropdown-item group"
              onClick={() => {}}
            >
              <div
                className="group-hover:bg-accent"
                data-testid="mcp-server-item"
              >
                <IconComponent
                  name="Mcp"
                  className={`${groupStyle} icon-size mr-2 fill-muted-foreground group-hover:fill-foreground`}
                />
                <span>MCP Server</span>
                <IconComponent
                  name="ExternalLink"
                  className={`${groupStyle} icon-size ml-auto hidden group-hover:block`}
                />
              </div>
            </DropdownMenuItem>
          </CustomLink>
          {ENABLE_WIDGET && (
            <DropdownMenuItem
              onClick={() => setOpenEmbedModal(true)}
              className="deploy-dropdown-item group"
            >
              <div className="group-hover:bg-accent">
                <IconComponent
                  name="Columns2"
                  className={`${groupStyle} icon-size mr-2`}
                />
                <span>Embed into site</span>
              </div>
            </DropdownMenuItem>
          )}

          {ENABLE_PUBLISH && (
            <ShadTooltipComponent
              styleClasses="truncate"
              side="left"
              content={
                hasIO
                  ? isPublished
                    ? encodeURI(`${domain}/playground/${flowId}`)
                    : "Activate to share a public version of this Playground"
                  : "Add a Chat Input or Chat Output to access your flow"
              }
            >
              <div
                className={cn(
                  !hasIO ? "cursor-not-allowed" : "",
                  "flex items-center",
                )}
                data-testid="shareable-playground"
              >
                <CustomLink
                  className={cn(
                    "flex-1",
                    !hasIO || !isPublished
                      ? "pointer-events-none cursor-default"
                      : "",
                  )}
                  to={`/playground/${flowId}`}
                  target="_blank"
                >
                  <DropdownMenuItem
                    disabled={!hasIO || !isPublished}
                    className="deploy-dropdown-item group flex-1"
                    onClick={() => {}}
                  >
                    <div className="group-hover:bg-accent">
                      <IconComponent
                        name="Globe"
                        className={`${groupStyle} icon-size mr-2`}
                      />
                      <span>Shareable Playground</span>
                    </div>
                  </DropdownMenuItem>
                </CustomLink>
                <div className={`z-50 mr-2 text-foreground`}>
                  <Switch
                    data-testid="publish-switch"
                    className="scale-[85%]"
                    checked={isPublished}
                    disabled={!hasIO}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handlePublishedSwitch(isPublished);
                    }}
                  />
                </div>
              </div>
            </ShadTooltipComponent>
          )}
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
    </>
  );
}
