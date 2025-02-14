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
import { ENABLE_WIDGET } from "@/customization/feature-flags";
import EmbedModal from "@/modals/EmbedModal/embed-modal";
import useAlertStore from "@/stores/alertStore";
import useAuthStore from "@/stores/authStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useEffect, useState } from "react";

export default function PublishDropdown() {
  const domain = window.location.origin;
  const [openEmbedModal, setOpenEmbedModal] = useState(false);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const flowId = currentFlow?.id;
  const flowName = currentFlow?.name;
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { mutateAsync } = usePatchUpdateFlow();
  const flows = useFlowsManagerStore((state) => state.flows);
  const setFlows = useFlowsManagerStore((state) => state.setFlows);
  const setCurrentFlow = useFlowStore((state) => state.setCurrentFlow);
  const isPublished = currentFlow?.access_type === "public";
  const hasIO = useFlowStore((state) => state.hasIO);
  const isAuth = useAuthStore((state) => !!state.autoLogin);

  useEffect(() => {
    console.log(currentFlow, "currentFlow");
    console.log(isPublished, "isPublished");
  }, [isPublished]);

  const handlePublishedSwitch = async (checked: boolean) => {
    mutateAsync(
      {
        id: flowId ?? "",
        access_type: checked ? "private" : "public",
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
          <Button variant="default" className="!h-8 !w-[95px] font-medium">
            Publish
            <IconComponent
              name="ChevronDown"
              className="icon-size font-medium"
            />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          forceMount
          sideOffset={10}
          alignOffset={-10}
          align="end"
          className="min-w-[300px] max-w-[400px]"
        >
          <ShadTooltipComponent
            styleClasses="truncate"
            side="left"
            content={
              hasIO
                ? encodeURI(`${domain}/playground/${flowId}`)
                : "Add a Chat Input or Chat Output to access your flow"
            }
          >
            <div className={!hasIO ? "cursor-not-allowed" : ""}>
              <DropdownMenuItem
                disabled={!hasIO}
                className="deploy-dropdown-item group"
                onClick={() => {
                  if (hasIO) {
                    if (isPublished) {
                      window.open(`${domain}/playground/${flowId}`, "_blank");
                    } else {
                      handlePublishedSwitch(isPublished).then(() => {
                        window.open(`${domain}/playground/${flowId}`, "_blank");
                      });
                    }
                  }
                }}
              >
                <div className="group-hover:bg-accent">
                  <IconComponent
                    name="Globe"
                    className={`${groupStyle} icon-size mr-2`}
                  />
                  <span>Standalone app</span>
                  <div
                    className={`icon-size ml-auto pb-6 pr-10 text-foreground`}
                  >
                    <Switch
                      className="scale-[85%]"
                      checked={isPublished}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handlePublishedSwitch(isPublished);
                      }}
                    />
                  </div>
                </div>
              </DropdownMenuItem>
            </div>
          </ShadTooltipComponent>
          <DropdownMenuItem className="deploy-dropdown-item group">
            <div className="group-hover:bg-accent">
              <IconComponent
                name="Code2"
                className={`${groupStyle} icon-size mr-2`}
              />
              <span>API access</span>
            </div>
          </DropdownMenuItem>
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
          <DropdownMenuItem className="deploy-dropdown-item group">
            <div className="group-hover:bg-accent">
              <IconComponent
                name="FileCode2"
                className={`${groupStyle} icon-size mr-2`}
              />
              <span>Langflow SDK</span>
              <IconComponent
                name="ExternalLink"
                className={`icon-size ml-auto mr-3 ${externalUrlStyle} text-foreground`}
              />
            </div>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
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
