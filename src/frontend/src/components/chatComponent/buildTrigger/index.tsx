import { Transition } from "@headlessui/react";
import { useContext, useState } from "react";
import Loading from "../../../components/ui/loading";
import { useSSE } from "../../../contexts/SSEContext";
import { alertContext } from "../../../contexts/alertContext";
import { typesContext } from "../../../contexts/typesContext";
import { FlowType } from "../../../types/flow";

import { TabsContext } from "../../../contexts/tabsContext";
import { buildVertices } from "../../../utils/buildUtils";
import { validateNodes } from "../../../utils/reactflowUtils";
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
  const { updateSSEData, isBuilding, setIsBuilding, sseData } = useSSE();
  const { reactFlowInstance } = useContext(typesContext);
  const { setTabsState } = useContext(TabsContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const [isIconTouched, setIsIconTouched] = useState(false);
  const eventClick = isBuilding ? "pointer-events-none" : "";
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

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
        onBuildUpdate: updateSSEData,
        onBuildComplete: handleBuildComplete,
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
    console.log(allNodesValid)
    setIsBuilt(allNodesValid);
    if (!allNodesValid) {
      setErrorData({
        title: "Oops! Looks like you missed something",
        list: [
          "Check components and retry. Hover over component status icon 🔴 to inspect.",
        ],
      });
    }
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
      <div className="fixed bottom-20 right-4">
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
                  name="Zap"
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
