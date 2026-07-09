import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
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
import type { FlowType } from "@/types/flow";
import { downloadFlow } from "@/utils/reactflowUtils";
import { gradientIsLight, gradients, swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import useDescriptionModal from "../../hooks/use-description-modal";
import { useGetTemplateStyle } from "../../utils/get-template-style";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const ListComponent = ({
  flowData,
  selected,
  setSelected,
  shiftPressed,
  view = "list",
}: {
  flowData: FlowType;
  selected: boolean;
  setSelected: (selected: boolean) => void;
  shiftPressed: boolean;
  view?: "grid" | "list";
}) => {
  const { t } = useTranslation();
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
          title: t("flow.deletedSuccessfully"),
        });
      })
      .catch((err) => {
        setErrorData({
          title: t("flow.errorDeleting"),
          list: [t("flow.errorDeletingRetry")],
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

  const gradientIndex =
    (flowData.gradient && !isNaN(parseInt(flowData.gradient))
      ? parseInt(flowData.gradient)
      : getNumberFromString(flowData.gradient ?? flowData.id)) %
    gradients.length;

  const handleExport = () => {
    if (flowData.is_component) {
      downloadFlow(flowData, flowData.name, flowData.description);
      setSuccessData({
        title: t("success.flowExported", { name: flowData.name }),
      });
    } else {
      setOpenExportModal(true);
    }
  };

  const [icon, setIcon] = useState<string>("");

  useEffect(() => {
    getIcon().then(setIcon);
  }, [getIcon]);

  if (view === "grid") {
    const isLight = gradientIsLight[gradientIndex];
    const textClass = isLight ? "text-black" : "text-white";
    const descClass = isLight ? "text-black/70" : "text-white/85";
    const btnClass = isLight
      ? "text-black/70 hover:bg-black/10 hover:text-black"
      : "text-white/90 hover:bg-white/20 hover:text-white";

    return (
      <>
        <Card
          key={flowData.id}
          draggable
          onDragStart={onDragStart}
          onClick={handleClick}
          className={cn(
            "relative aspect-[1.6/1] overflow-hidden rounded-lg border-none p-2.5",
            "shadow-md transition-shadow hover:shadow-lg",
            isComponent ? "cursor-default" : "cursor-pointer",
            gradients[gradientIndex],
            textClass,
          )}
          data-testid="list-card"
        >
          <div className="absolute right-2 top-2 z-20">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="iconSm"
                  data-testid="home-dropdown-menu"
                  className={cn("group", btnClass)}
                  onClick={(e) => e.stopPropagation()}
                >
                  <ForwardedIconComponent
                    name="Ellipsis"
                    aria-hidden="true"
                    className="h-4 w-4"
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

          <div className="relative z-10 flex h-full flex-col justify-end">
            <div data-testid="flow-name-div">
              <h3
                className="line-clamp-2 break-words text-sm font-semibold drop-shadow-sm"
                data-testid={`flow-name-${flowData.id}`}
              >
                {flowData.name}
              </h3>
            </div>
            <p
              className={cn("mt-1 line-clamp-2 break-words text-xs", descClass)}
              data-testid={`flow-description-${flowData.id}`}
            >
              {flowData.description || t("flow.noDescription")}
            </p>
          </div>
        </Card>
        {openDelete && (
          <DeleteConfirmationModal
            open={openDelete}
            setOpen={setOpenDelete}
            onConfirm={handleDelete}
            description={descriptionModal}
            note={
              !flowData.is_component ? t("deleteModal.noteMessageHistory") : ""
            }
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
  }

  return (
    <>
      <Card
        key={flowData.id}
        draggable
        onDragStart={onDragStart}
        onClick={handleClick}
        className={`flex flex-row bg-background ${
          isComponent ? "cursor-default" : "cursor-pointer"
        } group justify-between rounded-lg border-none px-4 py-3 shadow-none hover:bg-muted`}
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
              <div className="flex min-w-0 flex-shrink text-xs text-muted-foreground">
                <span className="truncate">
                  {t("mainPage.editedAgo", {
                    time: timeElapsed(flowData.updated_at, t),
                  })}
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
          note={
            !flowData.is_component ? t("deleteModal.noteMessageHistory") : ""
          }
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
