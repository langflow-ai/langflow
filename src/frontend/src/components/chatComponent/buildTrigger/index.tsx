import { Transition } from "@headlessui/react";
import { useContext, useState } from "react";
import Loading from "../../../components/ui/loading";
import { useSSE } from "../../../contexts/SSEContext";
import { alertContext } from "../../../contexts/alertContext";
import { typesContext } from "../../../contexts/typesContext";
import { FlowType } from "../../../types/flow";

import { TabsContext } from "../../../contexts/tabsContext";
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
  const [verticesOrder, setVerticesOrder] = useState([]);
  const [buildResults, setBuildResults] = useState({});
  const [error, setError] = useState(null);

  async function handleBuild(flow: FlowType): Promise<void> {
    try {
      if (isBuilding) {
        return;
      }
      const errors = validateNodes(reactFlowInstance!);
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

      // Step 1: Get vertices order
      await getVerticesOrder(flow.id);

      // Step 2: Build each vertex in the order received
      console.log("verticesOrder", verticesOrder);
      const buildResults = [];
      for (let vertexId of verticesOrder) {
        const buildResponse = await fetch(
          `/api/v1/build/${flow.id}/vertices/${vertexId}`,
          {
            method: "POST",
          }
        );
        const buildData = await buildResponse.json();
        if (buildData.valid) {
          setProgress(
            (prevProgress) => prevProgress + 1 / verticesOrder.length
          );
        }

        buildResults.push(buildData.valid);
      }

      // Determine if all nodes are valid
      const allNodesValid = buildResults.every((result) => result);

      await enforceMinimumLoadingTime(startTime, minimumLoadingTime);
      setIsBuilt(allNodesValid);
      if (!allNodesValid) {
        setErrorData({
          title: "Oops! Looks like you missed something",
          list: [
            "Check components and retry. Hover over component status icon 🔴 to inspect.",
          ],
        });
      }
      if (errors.length === 0 && allNodesValid) {
        setSuccessData({
          title: "Flow is ready to run",
        });
      }
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsBuilding(false);
    }
  }

  // Function to get vertices order
  async function getVerticesOrder(flowId) {
    try {
      const response = await fetch(`/api/v1/build/${flowId}/vertices`);
      const data = await response.json();
      setVerticesOrder(data.ids);
    } catch (err) {
      setError(err.message);
    }
  }

  // Function to build a vertex and update the results
  async function buildVertex(flowId, vertexId) {
    try {
      const response = await fetch(
        `/api/v1/build/${flowId}/vertices/${vertexId}`,
        { method: "POST" }
      );
      const data = await response.json();
      setBuildResults((prevResults) => ({
        ...prevResults,
        [vertexId]: data,
      }));
    } catch (err) {
      setError(err.message);
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
