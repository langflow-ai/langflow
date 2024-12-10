import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useDragStart from "@/components/core/cardComponent/hooks/use-on-drag-start";
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
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useState } from "react";
import { useParams } from "react-router-dom";
import useDescriptionModal from "../../hooks/use-description-modal";
import { useGetTemplateStyle } from "../../utils/get-template-style";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const ListComponent = ({ flowData }: { flowData: FlowType }) => {
  const navigate = useCustomNavigate();

  const [openDelete, setOpenDelete] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { deleteFlow } = useDeleteFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { folderId } = useParams();
  const isComponent = flowData.is_component ?? false;
  const setFlowToCanvas = useFlowsManagerStore(
    (state) => state.setFlowToCanvas,
  );
  const { getIcon } = useGetTemplateStyle(flowData);

  const editFlowLink = `/flow/${flowData.id}${folderId ? `/folder/${folderId}` : ""}`;

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

  const { onDragStart } = useDragStart(flowData);

  const descriptionModal = useDescriptionModal([flowData?.id], "flow");

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
        className={`my-2 flex flex-row bg-background ${
          isComponent ? "cursor-default" : "cursor-pointer"
        } group justify-between rounded-lg border border-border p-4 hover:border-placeholder-foreground hover:shadow-sm`}
        data-testid="list-card"
      >
        {/* left side */}
        <div
          className={`flex min-w-0 ${
            isComponent ? "cursor-default" : "cursor-pointer"
          } items-center gap-4`}
        >
          {/* Icon */}
          <div
            className={cn(
              `item-center flex justify-center rounded-lg p-3`,
              swatchColors[swatchIndex],
            )}
          >
            <ForwardedIconComponent
              name={flowData?.icon || getIcon()}
              aria-hidden="true"
              className="flex h-5 w-5 items-center justify-center"
            />
          </div>

          <div className="flex min-w-0 flex-col justify-start">
            <div className="line-clamp-1 flex min-w-0 items-baseline truncate max-md:flex-col">
              <div className="text-md flex truncate pr-2 font-semibold max-md:w-full">
                <span className="truncate">{flowData.name}</span>
              </div>
              <div className="item-baseline flex text-xs text-muted-foreground">
                Edited {timeElapsed(flowData.updated_at)} ago
              </div>
            </div>
            <div className="overflow-hidden text-sm text-primary">
              <span className="block max-w-[110ch] truncate">
                {flowData.description}
              </span>
            </div>
          </div>
        </div>

        {/* right side */}
        <div className="ml-5 flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="iconMd"
                data-testid="home-dropdown-menu"
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
                handlePlaygroundClick={() => {
                  // handlePlaygroundClick();
                }}
              />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </Card>

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

export default ListComponent;
