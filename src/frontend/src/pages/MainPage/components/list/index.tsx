import ForwardedIconComponent from "@/components/common/genericIconComponent";
import useDragStart from "@/components/core/cardComponent/hooks/use-on-drag-start";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import ExportModal from "@/modals/exportModal";
import FlowSettingsModal from "@/modals/flowSettingsModal";
import useAlertStore from "@/stores/alertStore";
import { FlowType } from "@/types/flow";
import { downloadFlow } from "@/utils/reactflowUtils";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import useDescriptionModal from "../../hooks/use-description-modal";
import { useGetTemplateStyle } from "../../utils/get-template-style";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const ListComponent = ({
  flowData,
  selected,
  setSelected,
  shiftPressed,
}: {
  flowData: FlowType;
  selected: boolean;
  setSelected: (selected: boolean) => void;
  shiftPressed: boolean;
}) => {
  const navigate = useCustomNavigate();
  const [openDelete, setOpenDelete] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { deleteFlow } = useDeleteFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const { folderId } = useParams();
  const [openSettings, setOpenSettings] = useState(false);
  const [openExportModal, setOpenExportModal] = useState(false);
  const isComponent = flowData.is_component ?? false;

  const { getIcon } = useGetTemplateStyle(flowData);

  const editFlowLink = `/flow/${flowData.id}${folderId ? `/folder/${folderId}` : ""}`;

  const handleClick = async () => {
    if (shiftPressed) {
      setSelected(!selected);
    } else {
      if (!isComponent) {
        navigate(editFlowLink);
      }
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

  const descriptionModal = useDescriptionModal(
    [flowData?.id],
    flowData.is_component ? "component" : "flow",
  );

  const swatchIndex =
    (flowData.gradient && !isNaN(parseInt(flowData.gradient))
      ? parseInt(flowData.gradient)
      : getNumberFromString(flowData.gradient ?? flowData.id)) %
    swatchColors.length;

  const handleExport = () => {
    if (flowData.is_component) {
      downloadFlow(flowData, flowData.name, flowData.description);
      setSuccessData({ title: `${flowData.name} exported successfully` });
    } else {
      setOpenExportModal(true);
    }
  };

  const [icon, setIcon] = useState<string>("");

  useEffect(() => {
    getIcon().then(setIcon);
  }, [getIcon]);

  return (
    <>
      <Card
        key={flowData.id}
        draggable
        onDragStart={onDragStart}
        onClick={handleClick}
        className={`bg-background flex flex-row ${
          isComponent ? "cursor-default" : "cursor-pointer"
        } group hover:bg-muted justify-between rounded-lg border-none px-4 py-3 shadow-none`}
        data-testid="list-card"
      >
        <div
          className={`flex min-w-0 ${
            isComponent ? "cursor-default" : "cursor-pointer"
          } items-center gap-4`}
        >
          <div className="group/checkbox relative flex items-center">
            <div
              className={cn(
                "z-20 flex w-0 items-center transition-all duration-300",
                selected && "w-10",
              )}
            >
              <Checkbox
                checked={selected}
                onCheckedChange={(checked) => setSelected(checked as boolean)}
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  "ml-2 transition-opacity focus-visible:ring-0",
                  !selected && "opacity-0 group-hover/checkbox:opacity-100",
                )}
                data-testid={`checkbox-${flowData.id}`}
              />
            </div>
            <div
              className={cn(
                `item-center flex justify-center rounded-lg p-1.5 transition-opacity duration-200`,
                swatchColors[swatchIndex],
                selected
                  ? "duration-300"
                  : "group-hover/checkbox:pointer-events-none group-hover/checkbox:opacity-0",
              )}
            >
              <ForwardedIconComponent
                name={flowData?.icon || icon}
                aria-hidden="true"
                className="flex h-5 w-5 items-center justify-center"
              />
            </div>
          </div>

          <div className="flex min-w-0 flex-col justify-start">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
              <div
                className="flex min-w-0 flex-shrink truncate text-sm font-semibold"
                data-testid={`flow-name-div`}
              >
                <span
                  className="truncate"
                  data-testid={`flow-name-${flowData.id}`}
                >
                  {flowData.name}
                </span>
              </div>
              <div className="text-muted-foreground flex min-w-0 flex-shrink text-xs">
                <span className="truncate">
                  Edited {timeElapsed(flowData.updated_at)} ago
                </span>
              </div>
            </div>
          </div>
        </div>

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
                  className="text-muted-foreground group-hover:text-foreground h-5 w-5"
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
                handleExport={handleExport}
                handleEdit={() => {
                  setOpenSettings(true);
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
          note={!flowData.is_component ? "and its message history" : ""}
        />
      )}
      <ExportModal
        open={openExportModal}
        setOpen={setOpenExportModal}
        flowData={flowData}
      />
      <FlowSettingsModal
        open={openSettings}
        setOpen={setOpenSettings}
        flowData={flowData}
      />
    </>
  );
};

export default ListComponent;
