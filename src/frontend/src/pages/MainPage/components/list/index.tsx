import ForwardedIconComponent from "@/components/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { track } from "@/customization/utils/analytics";
import IOModal from "@/modals/IOModal";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { getInputsAndOutputs } from "@/utils/storeUtils";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { timeElapsed } from "../../utils/time-elapse";
import DropdownComponent from "../dropdown";

const ListComponent = ({ flowData }: { flowData: FlowType }) => {
  const navigate = useNavigate();
  const [openPlayground, setOpenPlayground] = useState(false);
  const [loadingPlayground, setLoadingPlayground] = useState(false);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);

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

  return (
    <>
      <div
        key={flowData.id}
        className="my-2 flex justify-between rounded-lg border border-zinc-100 p-5 hover:border-zinc-200 hover:shadow-sm dark:border-zinc-800 dark:hover:border-zinc-600"
      >
        {/* left side */}
        <div
          className="flex cursor-pointer items-center gap-2"
          onClick={() => {
            navigate(`/flowData/${flowData.id}`);
          }}
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
                Edited {timeElapsed(flowData.updated_at)} ago by{" "}
                <span className="font-semibold">{flowData.user_id}</span>
              </div>
            </div>
            <div className="flex w-full text-sm text-zinc-800 dark:text-white">
              {flowData.description}
            </div>
          </div>
        </div>

        {/* right side */}
        <div className="flex items-center gap-2">
          <Button
            onClick={handlePlaygroundClick}
            className="border border-zinc-200 bg-white text-[black] hover:border-zinc-400 hover:bg-white hover:shadow-sm dark:border-zinc-600 dark:bg-transparent dark:text-white dark:hover:border-white"
          >
            Playground
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                unstyled
                className="h-10 w-10 rounded px-0 hover:bg-zinc-200 dark:hover:bg-zinc-800"
              >
                <ForwardedIconComponent
                  name="ellipsis"
                  aria-hidden="true"
                  className="mx-auto text-zinc-500 dark:text-zinc-300"
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
