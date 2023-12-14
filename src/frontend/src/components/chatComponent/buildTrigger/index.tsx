import { Transition } from "@headlessui/react";
import { useContext, useState } from "react";
import Loading from "../../../components/ui/loading";
import { alertContext } from "../../../contexts/alertContext";
import { FlowType } from "../../../types/flow";

import { flowManagerContext } from "../../../contexts/flowManagerContext";
import { FlowsContext } from "../../../contexts/flowsContext";
import { buildVertices } from "../../../utils/buildUtils";
import { parsedDataType } from "../../../types/components";
import { FlowsState } from "../../../types/tabs";
import { validateNodes } from "../../../utils/reactflowUtils";
import { classNames } from "../../../utils/utils";
import RadialProgressComponent from "../../RadialProgress";
import IconComponent from "../../genericIconComponent";

export default function BuildTrigger({
  open,
  flow,
  setIsBuilt,
}: {
  open: boolean;
  flow: FlowType;
  setIsBuilt: any;
  isBuilt: boolean;
}): JSX.Element {
  const { setTabsState } = useContext(FlowsContext);
  const { updateSSEData, isBuilding, setIsBuilding, sseData } = useSSE();
  const { reactFlowInstance } = useContext(typesContext);
  const { setTabsState, saveFlow } = useContext(FlowsContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const { addDataToFlowPool, reactFlowInstance, showPanel,isBuilding,setIsBuilding } =
    useContext(flowManagerContext);
  const [isIconTouched, setIsIconTouched] = useState(false);
  const eventClick = isBuilding ? "pointer-events-none" : "";
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  function handleBuildUpdate(data: any) {
    addDataToFlowPool(data.data[data.id], data.id);
  }

  async function handleBuild(flow: FlowType): Promise<void> {
    try {
      if (isBuilding) {
        return;
      }
      const errors = validateNodes(
        reactFlowInstance!.getNodes(),
        reactFlowInstance!.getEdges()
      );
      if (errors.length > 0) {
        setErrorData({
          title: "Oops! Looks like you missed something",
          list: errors,
        });
        return;
      }
      const minimumLoadingTime = 200; // in milliseconds
      const startTime = Date.now();
      setIsBuilding(true);
      await buildVertices({
        flow,
        onProgressUpdate: setProgress,
        onBuildComplete: handleBuildComplete,
        onBuildUpdate: handleBuildUpdate,
        onBuildError: (title, list) => {
          setErrorData({ title, list });
        },
      });

      await enforceMinimumLoadingTime(startTime, minimumLoadingTime);
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsBuilding(false);
    }
  }

  function handleBuildComplete(allNodesValid: boolean) {
    setIsBuilt(allNodesValid);
    if (allNodesValid) {
      setSuccessData({
        title: "Flow is ready to run",
      });
    }
  }

  async function enforceMinimumLoadingTime(
    startTime: number,
    minimumLoadingTime: number
  ) {
    const elapsedTime = Date.now() - startTime;
    const remainingTime = minimumLoadingTime - elapsedTime;

    if (remainingTime > 0) {
      return new Promise((resolve) => setTimeout(resolve, remainingTime));
    }
  }

  const handleMouseEnter = () => {
    setIsIconTouched(true);
  };

  const handleMouseLeave = () => {
    setIsIconTouched(false);
  };

  return (
    <Transition
      show={!open}
      appear={true}
      enter="transition ease-out duration-300"
      enterFrom="translate-y-96"
      enterTo="translate-y-0"
      leave="transition ease-in duration-300"
      leaveFrom="translate-y-0"
      leaveTo="translate-y-96"
    >
      <div
        className={classNames(
          "fixed right-4",
          showPanel ? "bottom-20" : "bottom-5"
        )}
      >
        <div
          className={`${eventClick} round-button-form`}
          onClick={() => {
            handleBuild(flow);
          }}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <button>
            <div className="round-button-div">
              {isBuilding && progress < 1 ? (
                // Render your loading animation here when isBuilding is true
                <RadialProgressComponent
                  // ! confirm below works
                  color={"text-build-trigger"}
                  value={progress}
                ></RadialProgressComponent>
              ) : isBuilding ? (
                <Loading
                  strokeWidth={1.5}
                  className="build-trigger-loading-icon"
                />
              ) : (
                <IconComponent
                  name="Play"
                  className="sh-6 w-6 fill-build-trigger stroke-build-trigger stroke-1"
                />
              )}
            </div>
          </button>
        </div>
      </div>
    </Transition>
  );
}
