import { Transition } from "@headlessui/react";
import {
  Bars3CenterLeftIcon,
  ChatBubbleBottomCenterTextIcon,
} from "@heroicons/react/24/outline";
import { nodeColors } from "../../../utils";
import { PopUpContext } from "../../../contexts/popUpContext";
import { useContext } from "react";
import ChatModal from "../../../modals/chatModal";

export default function ChatTrigger({ open, setOpen }) {
  const { openPopUp } = useContext(PopUpContext);
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
          // style={{ backgroundColor: nodeColors["chat"] }}
          className="align-center flex h-12 w-12 justify-center rounded-full border bg-gradient-to-r from-blue-500 via-blue-600 to-blue-700 px-3 py-1 dark:border-gray-600"
        >
          <button
            onClick={() => {
              setOpen(true);
            }}
          >
            <div className="flex items-center  gap-3">
              <ChatBubbleBottomCenterTextIcon
                className="mt-1 h-6 w-6"
                style={{ color: "white" }}
              />
            </div>
          </button>
        </div>
      </div>
    </Transition>
  );
}
