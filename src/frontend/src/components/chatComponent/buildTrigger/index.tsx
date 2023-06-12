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

  const CHUNK_DELIMITER = "\n\n";

  async function handleBuild(flow: FlowType) {
    const minimumLoadingTime = 200; // in milliseconds
    const startTime = Date.now();
    setIsBuilding(true);

    try {
      const allChunksValid = await postDataToServer(`/build/${flow.id}`, flow);
      await enforceMinimumLoadingTime(startTime, minimumLoadingTime);
      setIsBuilt(allChunksValid);
    } catch (error) {
      console.error("Error:", error);
    } finally {
      setIsBuilding(false);
    }
  }

  async function postDataToServer(apiUrl: string, flow: FlowType) {
    let allChunksValid = true;

    await axios({
      method: "post",
      url: apiUrl,
      data: { data: flow },
      headers: { "Content-Type": "application/json" },
      onDownloadProgress: (progressEvent) => {
        const chunks =
          progressEvent.event.currentTarget.responseText.split(CHUNK_DELIMITER);
        chunks.forEach((chunk) => {
          if (chunk === "") {
            return;
          }
          const isValid = processChunk(chunk);
          allChunksValid = allChunksValid && isValid;
        });
      },
    });

    return allChunksValid;
  }

  function processChunk(chunk: string) {
    // Process each chunk of data here
    // Parse the chunk and update the context
    let parsedData = { valid: false, id: null };
    try {
      parsedData = JSON.parse(chunk.slice(6)); // Remove the "data: " part
      updateSSEData({ [parsedData.id]: parsedData });
    } catch (err) {
      console.log("Chunk is not valid JSON: ", chunk);
      console.log("Error parsing chunk: ", err);
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
