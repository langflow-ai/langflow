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

  function handleBuild(flow: FlowType) {
    const minimumLoadingTime = 500; // in milliseconds
    const startTime = Date.now();

    setIsBuilding(true);

    postBuild(flow)
      .then((res) => {
        console.log(res);
        setIsBuilt(true);
      })
      .catch((err) => {
        console.log(err);
        setIsBuilt(false);
      })
      .finally(() => {
        const endTime = Date.now();
        const elapsedTime = endTime - startTime;

        if (elapsedTime < minimumLoadingTime) {
          const remainingTime = minimumLoadingTime - elapsedTime;
          setTimeout(() => {
            setIsBuilding(false);
          }, remainingTime);
        } else {
          setIsBuilding(false);
        }
      });
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
