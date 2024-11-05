import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useDeleteFlow from "@/hooks/flows/use-delete-flow";
import DeleteConfirmationModal from "@/modals/deleteConfirmationModal";
import IOModal from "@/modals/IOModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { useState } from "react";
import { useParams } from "react-router-dom";
import useDescriptionModal from "../../oldComponents/componentsComponent/hooks/use-description-modal";
import { getTemplateStyle } from "../../utils/get-template-style";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const ListComponent = ({ flowData }: { flowData: FlowType }) => {
  const navigate = useCustomNavigate();
  // const [openPlayground, setOpenPlayground] = useState(false);
  // const [loadingPlayground, setLoadingPlayground] = useState(false);
  const [openDelete, setOpenDelete] = useState(false);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const { deleteFlow } = useDeleteFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const { folderId } = useParams();
  const isComponent = flowData.is_component ?? false;
  const setFlowToCanvas = useFlowsManagerStore(
    (state) => state.setFlowToCanvas,
  );
  const { icon, icon_bg_color } = getTemplateStyle(flowData);

  const editFlowLink = `/flow/${flowData.id}${folderId ? `/folder/${folderId}` : ""}`;

  function hasPlayground(flow?: FlowType) {
    if (!flow) {
      return false;
    }
    const { inputs, outputs } = getInputsAndOutputs(flow?.data?.nodes ?? []);
    return inputs.length > 0 || outputs.length > 0;
  }

  // const handlePlaygroundClick = () => {
  //   track("Playground Button Clicked", { flowId: flowData.id });
  //   setLoadingPlayground(true);

  //   if (flowData) {
  //     if (!hasPlayground(flowData)) {
  //       setErrorData({
  //         title: "Error",
  //         list: ["This flow doesn't have a playground."],
  //       });
  //       setLoadingPlayground(false);
  //       return;
  //     }
  //     setCurrentFlow(flowData);
  //     setOpenPlayground(true);
  //     setLoadingPlayground(false);
  //   } else {
  //     setErrorData({
  //       title: "Error",
  //       list: ["Error getting flow data."],
  //     });
  //   }
  // };

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

  return (
    <>
      <div
        key={flowData.id}
        onClick={handleClick}
        className={`my-2 flex h-[110px] ${
          isComponent ? "cursor-default" : "cursor-pointer"
        } justify-between rounded-lg border border-zinc-100 p-5 shadow-sm hover:border-border dark:border-zinc-800 dark:hover:border-muted-foreground`}
      >
        {/* left side */}
        <div
          className={`flex min-w-0 ${
            isComponent ? "cursor-default" : "cursor-pointer"
          } items-center gap-2`}
        >
          {/* Icon */}
          <div
            className={`item-center mr-3 flex justify-center rounded-lg border ${flowData?.icon_bg_color || icon_bg_color} p-3`}
          >
            <ForwardedIconComponent
              name={flowData?.icon || icon}
              aria-hidden="true"
              className="flex h-5 w-5 items-center justify-center dark:text-black"
            />
          </div>

          <div className="flex min-w-0 flex-col justify-start">
            <div className="line-clamp-1 flex min-w-0 items-baseline truncate max-md:flex-col">
              <div className="text-md flex truncate pr-2 font-semibold max-md:w-full">
                <span className="truncate">{flowData.name}</span>
              </div>
              <div className="item-baseline flex text-xs text-zinc-500 dark:text-zinc-400">
                Edited {timeElapsed(flowData.updated_at)} ago
              </div>
            </div>
            <div className="line-clamp-2 flex text-sm text-zinc-800 truncate-doubleline dark:text-white">
              {flowData.description}
            </div>
          </div>
        </div>

        {/* right side */}
        <div className="ml-5 flex items-center gap-2">
          {/* {flowData.is_component ? (
            <></>
          ) : (
            <Button
              variant="outline"
              disabled={loadingPlayground || !hasPlayground(flowData)}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handlePlaygroundClick();
              }}
              className="hidden sm:block"
            >
              Playground
            </Button>
          )} */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                data-testid="home-dropdown-menu"
                className="group h-10 w-10 border-none dark:hover:bg-zinc-700"
              >
                <ForwardedIconComponent
                  name="ellipsis"
                  aria-hidden="true"
                  className="h-5 w-5 dark:text-zinc-400 dark:group-hover:text-white"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="mr-[30px] w-[185px] bg-white dark:bg-black"
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
      </div>
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

export default ListComponent;
