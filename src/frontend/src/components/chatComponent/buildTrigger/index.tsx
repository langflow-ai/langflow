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

  function handleBuild(flow) {
    setIsBuilding(true);

    // State to keep track of validity status of all chunks
    let allChunksValid = true;

    const apiUrl = `/build/${flow.id}`;

    // Post data to the server
    axios({
      method: "post",
      url: apiUrl,
      data: { data: flow },
      headers: { "Content-Type": "application/json" },
      onDownloadProgress: (progressEvent) => {
        const { currentTarget } = progressEvent.event;
        const { responseText } = currentTarget;
        // responseText is a string with \n\n delimiters

        // Get only the new data since the last read
        // by splitting the string and getting the one before the last \n\n

        const chunks = responseText.split("\n\n");

        // Process each chunk
        chunks.forEach((chunk: string) => {
          if (chunk !== "") {
            let valid = processChunk(chunk);
            console.log("Valid: ", valid);
            allChunksValid = allChunksValid && valid;
          }
        });
      },
    })
      .catch((err) => {
        console.error("Error:", err);
      })
      .finally(() => {
        // Set isBuilt to the value of allChunksValid
        setIsBuilt(allChunksValid);
        setIsBuilding(false);
      });
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
