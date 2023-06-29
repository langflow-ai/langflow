import { Transition } from "@headlessui/react";
import { MessagesSquare } from "lucide-react";

import { alertContext } from "../../../contexts/alertContext";
import { useContext } from "react";
import ShadTooltip from "../../ShadTooltipComponent";

export default function ChatTrigger({ open, setOpen, isBuilt }) {
  const { setErrorData } = useContext(alertContext);

  function handleClick() {
    if (isBuilt) {
      setOpen(true);
    } else {
      setErrorData({
        title: "Flow not built",
        list: ["Please build the flow before chatting"],
      });
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
      <div className="absolute bottom-4 right-3">
        <div
          className="flex justify-center align-center py-1 px-3 w-12 h-12 rounded-full shadow-md shadow-round-btn-shadow hover:shadow-round-btn-shadow
          bg-border cursor-pointer"
          onClick={handleClick}
        >
          <button>
            <div className="flex gap-3">
              <MessagesSquare
                className="pth-6 w-6 fill-chat-trigger stroke-1 stroke-chat-trigger"
                style={{ color: "white" }}
                strokeWidth={1.5}
              />
            </div>
          </button>
        </div>
      </div>
    </Transition>
  );
}
