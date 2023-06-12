import { useState, useContext } from "react";
import { Transition } from "@headlessui/react";
import { Bars3CenterLeftIcon } from "@heroicons/react/24/outline";
import { Zap } from "lucide-react";
import { nodeColors } from "../../../utils";
import { PopUpContext } from "../../../contexts/popUpContext";
import ChatModal from "../../../modals/chatModal";
import { FlowType } from "../../../types/flow";
import { postBuild } from "../../../controllers/API";
import Loading from "../../../components/ui/loading";
import { useSSE } from "../../../contexts/SSEContext";
import axios from "axios";

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
  const [isBuilding, setIsBuilding] = useState(false);

  const { updateSSEData } = useSSE();

  async function handleBuild(flow: FlowType) {
    const minimumLoadingTime = 200; // in milliseconds
    const startTime = Date.now();
    setIsBuilding(true);

    try {
      const allNodesValid = await streamNodeData(`/build/init`, flow);
      await enforceMinimumLoadingTime(startTime, minimumLoadingTime);
      setIsBuilt(allNodesValid);
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsBuilding(false);
    }
  }

  async function streamNodeData(apiUrl: string, flow: FlowType) {
    // Step 1: Make a POST request to send the flow data and receive a unique session ID
    const response = await axios.post(apiUrl, flow);
    const { flowId } = response.data;

    // Step 2: Use the session ID to establish an SSE connection using EventSource

    let validationResults = [];
    let finished = false;
    apiUrl = `/build/stream/${flowId}`;
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
          className="border flex justify-center align-center py-1 px-3 w-12 h-12 rounded-full bg-gradient-to-r from-blue-700 via-blue-600 to-blue-500 dark:border-gray-600 cursor-pointer"
          onClick={() => handleBuild(flow)}
        >
          <button>
            <div className="flex gap-3 items-center">
              {isBuilding ? (
                // Render your loading animation here when isBuilding is true
                <Loading style={{ color: "white" }} />
              ) : (
                <Zap className="h-6 w-6" style={{ color: "white" }} />
              )}
            </div>
          </button>
        </div>
      </div>
    </Transition>
  );
}
