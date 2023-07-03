import { Transition } from "@headlessui/react";
import { MessagesSquare } from "lucide-react";

import { alertContext } from "../../../contexts/alertContext";
import { useContext } from "react";

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
          <button onClick={handleClick} className={ "transition-all fixed bottom-4 right-4 flex justify-center items-center py-1 px-3 w-12 h-12 rounded-full shadow-md shadow-[#0000002a] hover:shadow-[#00000032] bg-[#E2E7EE] dark:border-gray-600 "+ (!isBuilt ? "cursor-not-allowed" : "cursor-pointer")}>
            <div className="flex gap-3">
              <MessagesSquare
                className={"h-6 w-6 transition-all " + (isBuilt ? "fill-[#5c8be1] stroke-1 stroke-[#5c8be1]" : "fill-[#a5bae0] stroke-1 stroke-[#a5bae0]")}
                style={{ color: "white" }}
                strokeWidth={1.5}
              />
            </div>
          </button>
    </Transition>
  );
}
