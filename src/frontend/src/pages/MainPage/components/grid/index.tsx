import useDragStart from "@/components/cardComponent/hooks/use-on-drag-start";
import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useState } from "react";
import { useParams } from "react-router-dom";
import useDescriptionModal from "../../oldComponents/componentsComponent/hooks/use-description-modal";
import { useGetTemplateStyle } from "../../utils/get-template-style";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const GridComponent = ({ flowData }: { flowData: FlowType }) => {
  const navigate = useCustomNavigate();
  /* const [openPlayground, setOpenPlayground] = useState(false);
  const [loadingPlayground, setLoadingPlayground] = useState(false); */
  const [openDelete, setOpenDelete] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { deleteFlow } = useDeleteFlow();

  const setErrorData = useAlertStore((state) => state.setErrorData);
  /* const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow); */
  const { folderId } = useParams();
  const isComponent = flowData.is_component ?? false;
  const setFlowToCanvas = useFlowsManagerStore(
    (state) => state.setFlowToCanvas,
  );

  const { getIcon } = useGetTemplateStyle(flowData);

  const editFlowLink = `/flow/${flowData.id}${folderId ? `/folder/${folderId}` : ""}`;

  function hasPlayground(flow?: FlowType) {
    if (!flow) {
      return false;
    }
    const { inputs, outputs } = getInputsAndOutputs(flow?.data?.nodes ?? []);
    return inputs.length > 0 || outputs.length > 0;
  }

  /* const handlePlaygroundClick = () => {
    track("Playground Button Clicked", { flowId: flowData.id });
    setLoadingPlayground(true);

    if (flowData) {
      if (!hasPlayground(flowData)) {
        setErrorData({
          title: "Error",
          list: ["This flow doesn't have a playground."],
        });
        setLoadingPlayground(false);
        return;
      }
      setCurrentFlow(flowData);
      // setOpenPlayground(true);
      setLoadingPlayground(false);
    } else {
      setErrorData({
        title: "Error",
        list: ["Error getting flow data."],
      });
    }
  }; */

  const handleClick = async () => {
    if (!isComponent) {
      await setFlowToCanvas(flowData);
      navigate(editFlowLink);
    }
  };

  const handleDelete = () => {
    deleteFlow({ id: [flowData.id] })
      .then(() => {
        setSuccessData({
          title: "Selected items deleted successfully",
        });
      })
      .catch(() => {
        setErrorData({
          title: "Error deleting items",
          list: ["Please try again"],
        });
      });
  };

  const descriptionModal = useDescriptionModal([flowData?.id], "flow");

  const { onDragStart } = useDragStart(flowData);

  const swatchIndex =
    (flowData.gradient && !isNaN(parseInt(flowData.gradient))
      ? parseInt(flowData.gradient)
      : getNumberFromString(flowData.gradient ?? flowData.id)) %
    swatchColors.length;

  return (
    <>
      <Card
        key={flowData.id}
        draggable
        onDragStart={onDragStart}
        onClick={handleClick}
        className={`my-1 flex flex-col rounded-lg border border-border bg-background p-4 hover:border-placeholder-foreground hover:shadow-sm ${
          isComponent ? "cursor-default" : "cursor-pointer"
        }`}
      >
        <div className="flex w-full items-center gap-4">
          <div className={cn(`flex rounded-lg p-3`, swatchColors[swatchIndex])}>
            <ForwardedIconComponent
              name={getIcon()}
              aria-hidden="true"
              className="h-5 w-5"
            />
          </div>
          <div className="flex w-full min-w-0 items-center justify-between">
            <div className="flex min-w-0 flex-col">
              <div className="text-md truncate font-semibold">
                {flowData.name}
              </div>
              <div className="truncate text-xs text-muted-foreground">
                Edited {timeElapsed(flowData.updated_at)} ago
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  data-testid="home-dropdown-menu"
                  size="iconMd"
                  className="group"
                >
                  <ForwardedIconComponent
                    name="Ellipsis"
                    aria-hidden="true"
                    className="h-5 w-5 text-muted-foreground group-hover:text-foreground"
                  />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-[185px]"
                sideOffset={5}
                side="bottom"
              >
                <DropdownComponent
                  flowData={flowData}
                  setOpenDelete={setOpenDelete}
                />
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="line-clamp-2 h-full pt-5 text-sm text-primary">
          {flowData.description}
        </div>

        {/* <div className="flex justify-end pt-[24px]">
          {flowData.is_component ? (
            <></>
          ) : (
            <Button
              disabled={loadingPlayground || !hasPlayground(flowData)}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handlePlaygroundClick();
              }}
              variant="outline"
            >
              Playground
            </Button>
          )}
        </div> */}
      </Card>
      {/* {openPlayground && (
        <IOModal
          key={flowData.id}
          cleanOnClose={true}
          open={openPlayground}
          setOpen={setOpenPlayground}
        >
          <></>
        </IOModal>
      )} */}
      {openDelete && (
        <DeleteConfirmationModal
          open={openDelete}
          setOpen={setOpenDelete}
          onConfirm={handleDelete}
          description={descriptionModal}
        >
          <></>
        </DeleteConfirmationModal>
      )}
    </>
  );
};

export default GridComponent;
