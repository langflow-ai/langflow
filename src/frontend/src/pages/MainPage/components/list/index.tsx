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
import IOModal from "@/modals/IOModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const ListComponent = ({ flowData }: { flowData: FlowType }) => {
  const navigate = useCustomNavigate();
  const [openPlayground, setOpenPlayground] = useState(false);
  const [loadingPlayground, setLoadingPlayground] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const { folderId } = useParams();
  const isComponent = flowData.is_component ?? false;
  const setFlowToCanvas = useFlowsManagerStore(
    (state) => state.setFlowToCanvas,
  );

  const editFlowLink = `/flow/${flowData.id}${folderId ? `/folder/${folderId}` : ""}`;

  function hasPlayground(flow?: FlowType) {
    if (!flow) {
      return false;
    }
    const { inputs, outputs } = getInputsAndOutputs(flow?.data?.nodes ?? []);
    return inputs.length > 0 || outputs.length > 0;
  }

  const handlePlaygroundClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
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
      setOpenPlayground(true);
      setLoadingPlayground(false);
    } else {
      setErrorData({
        title: "Error",
        list: ["Error getting flow data."],
      });
    }
  };

  const handleClick = async () => {
    if (!isComponent) {
      await setFlowToCanvas(flowData);
      navigate(editFlowLink);
    }
  };

  return (
    <>
      <div
        key={flowData.id}
        className="my-2 flex justify-between rounded-lg border border-zinc-100 p-5 hover:border-zinc-200 hover:shadow-sm dark:border-zinc-800 dark:hover:border-zinc-600"
      >
        {/* left side */}
        <div
          className="flex cursor-pointer items-center gap-2"
          onClick={handleClick}
        >
          {/* Icon */}
          <div
            className={`item-center mr-3 flex justify-center rounded-lg border ${flowData.icon_bg_color || "bg-purple-300"} p-3`}
          >
            <ForwardedIconComponent
              name={flowData.icon || "circle-help"}
              aria-hidden="true"
              className="flex h-5 w-5 items-center justify-center dark:text-black"
            />
          </div>

          <div className="flex flex-col justify-start">
            <div className="flex items-baseline gap-2">
              <div className="text-lg font-semibold">{flowData.name}</div>
              <div className="item-baseline text-xs text-zinc-500 dark:text-zinc-300">
                Edited {timeElapsed(flowData.updated_at)} ago
              </div>
            </div>
            <div className="line-clamp-2 flex text-sm text-zinc-800 dark:text-white">
              {flowData.description}
            </div>
          </div>
        </div>

        {/* right side */}
        <div className="ml-5 flex items-center gap-2">
          <Button
            variant="outline"
            disabled={loadingPlayground || !hasPlayground(flowData)}
            onClick={handlePlaygroundClick}
          >
            Playground
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-10 w-10">
                <ForwardedIconComponent
                  name="ellipsis"
                  aria-hidden="true"
                  className="h-5 w-5"
                />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className="mr-[30px] w-[185px] bg-white dark:bg-black"
              sideOffset={5}
              side="bottom"
            >
              <DropdownComponent />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {openPlayground && (
        <IOModal
          key={flowData.id}
          cleanOnClose={true}
          open={openPlayground}
          setOpen={setOpenPlayground}
        >
          <></>
        </IOModal>
      )}
    </>
  );
};

export default ListComponent;
