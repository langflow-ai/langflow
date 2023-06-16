import { useState, useContext } from "react";
import { Transition } from "@headlessui/react";
import { Zap } from "lucide-react";
import { validateNodes } from "../../../utils";
import { FlowType } from "../../../types/flow";
import Loading from "../../../components/ui/loading";
import { useSSE } from "../../../contexts/SSEContext";
import { typesContext } from "../../../contexts/typesContext";
import { alertContext } from "../../../contexts/alertContext";
import { postBuildInit } from "../../../controllers/API";

export default function BuildTrigger({
  open,
  flow,
  setIsBuilt,
  isBuilt,
}: {
  open: boolean;
  flow: FlowType;
  setIsBuilt: any;
  isBuilt: boolean;
}) {

  const { updateSSEData,isBuilding,setIsBuilding } = useSSE();
  const { reactFlowInstance } = useContext(typesContext);
  const { setErrorData } = useContext(alertContext);

  async function handleBuild(flow: FlowType) {
    try {
      if (isBuilding) {
        return;
      }
      const errors = validateNodes(reactFlowInstance);
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

      const allNodesValid = await streamNodeData(flow);
      await enforceMinimumLoadingTime(startTime, minimumLoadingTime);
      setIsBuilt(allNodesValid);
      if(!allNodesValid) {
        setErrorData({
          title: "Oops! Looks like you missed something",
          list: ["Check nodes and retry. Hover over 🔴 node for status."],
        });
      }
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsBuilding(false);
    }
  }

  async function streamNodeData(flow: FlowType) {
    // Step 1: Make a POST request to send the flow data and receive a unique session ID
    const response = await postBuildInit(flow);
    const { flowId } = response.data;

    // Step 2: Use the session ID to establish an SSE connection using EventSource
    let validationResults = [];
    let finished = false;
    const apiUrl = `/api/v1/build/stream/${flowId}`;
    const eventSource = new EventSource(apiUrl);

    eventSource.onmessage = (event) => {
      // If the event is parseable, return
      if (!event.data) {
        return;
      }
      const parsedData = JSON.parse(event.data);
      // if the event is the end of the stream, close the connection
      if (parsedData.end_of_stream) {
        eventSource.close();

        return;
      }
      // Otherwise, process the data
      const isValid = processStreamResult(parsedData);
      validationResults.push(isValid);
    };

    eventSource.onerror = (error) => {
      console.error("EventSource failed:", error);
      eventSource.close();
    };
    // Step 3: Wait for the stream to finish
    while (!finished) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      finished = validationResults.length === flow.data.nodes.length;
    }
    // Step 4: Return true if all nodes are valid, false otherwise
    return validationResults.every((result) => result);
  }

  function processStreamResult(parsedData) {
    // Process each chunk of data here
    // Parse the chunk and update the context
    try {
      updateSSEData({ [parsedData.id]: parsedData });
    } catch (err) {
      console.log("Error parsing stream data: ", err);
    }
    return parsedData.valid;
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
     <div className={`fixed right-4` + (isBuilt ? " bottom-20" : " bottom-4")}>
        <div
          className="flex justify-center align-center py-1 px-3 w-12 h-12 rounded-full shadow-md shadow-[#0000002a] hover:shadow-[#00000032]
           bg-[#E2E7EE] dark:border-gray-600 cursor-pointer"
          onClick={() => {
            handleBuild(flow);
          }}
        >
          <button>
            <div className="flex gap-3 items-center">
              {isBuilding ? (
                // Render your loading animation here when isBuilding is true
                <Loading strokeWidth={1.5} style={{ color: "white" }} />
              ) : (
                <Zap className="sh-6 w-6 fill-orange-400 stroke-1 stroke-orange-400"/>
              )}
            </div>
          </button>
        </div>
      </div>
    </Transition>
  );
}
