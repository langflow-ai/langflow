import { Transition } from "@headlessui/react";
import { useState } from "react";
import Loading from "../../../components/ui/loading";
import { FlowType } from "../../../types/flow";

import useAlertStore from "../../../stores/alertStore";
import useFlowStore from "../../../stores/flowStore";
import { validateNodes } from "../../../utils/reactflowUtils";
import RadialProgressComponent from "../../RadialProgress";
import IconComponent from "../../genericIconComponent";

export default function BuildTrigger({
  open,
  flow,
}: {
  open: boolean;
  flow: FlowType;
}): JSX.Element {
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const nodes = useFlowStore((state) => state.nodes);
  const edges = useFlowStore((state) => state.edges);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setFlowState = useFlowStore((state) => state.setFlowState);

  const eventClick = isBuilding ? "pointer-events-none" : "";
  const [progress, setProgress] = useState(0);

  async function handleBuild(flow: FlowType): Promise<void> {
    try {
      if (isBuilding) {
        return;
      }
      const errors = validateNodes(nodes, edges);
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

      await enforceMinimumLoadingTime(startTime, minimumLoadingTime);
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsBuilding(false);
    }
  }

  const checkInputAndOutput = useFlowStore(
    (state) => state.checkInputAndOutput
  );

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
        className={
          checkInputAndOutput()
            ? "fixed bottom-20 right-4"
            : "fixed bottom-4 right-4"
        }
      >
        <div
          className={`${eventClick} round-button-form`}
          onClick={() => {
            handleBuild(flow);
          }}
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
