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
      enterFrom="translate-x-96"
      enterTo="translate-y-0"
      leave="transition ease-in duration-300"
      leaveFrom="translate-x-0"
      leaveTo="translate-x-96"
    >

      <div className="absolute right-[100px] bottom-[620px]">
        <div
          className="
          rounded-full shadow-md hover:shadow-sm shadow-[#00000063] hover:shadow-[#00000063]
          flex justify-center items-center w-12 h-12 bg-blue-500 dark:border-gray-600 cursor-pointer"
          onClick={handleClick}
        >
          <button>
            <div className="flex gap-3">
              <MessagesSquare
                className="h-6 w-6  text-blue-100 fill-blue-100"
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
